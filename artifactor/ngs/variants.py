# mypy: ignore-errors
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import binomtest
from statsmodels.stats.multitest import multipletests

from artifactor.config import ArtifactorConfig
from artifactor.design import encoded_design

from .io import NGSInputs


@dataclass
class VariantResults:
    model_results: pd.DataFrame
    callable_status: pd.DataFrame
    context_summary: pd.DataFrame
    strand_bias: pd.DataFrame
    orientation_bias: pd.DataFrame
    read_support: pd.DataFrame
    ffpe_evidence: pd.DataFrame
    control_recovery: pd.DataFrame
    replicate_agreement: pd.DataFrame


def _read_support_diagnostics(callable_status: pd.DataFrame, config: ArtifactorConfig) -> pd.DataFrame:
    diagnostic = (
        (callable_status.callability_status == "callable")
        & (callable_status.alt_count >= config.ngs.minimum_alt_count_for_diagnostics)
        & (callable_status.observed_vaf <= config.ngs.low_vaf_threshold)
    )
    rows = []
    for metric in (
        "read_position_mean",
        "base_quality_mean",
        "mapping_quality_mean",
        "insert_size_mean",
    ):
        if metric not in callable_status or callable_status[metric].notna().sum() < 4:
            rows.append(
                {
                    "metric": metric,
                    "low_vaf_event_mean": None,
                    "background_mean": None,
                    "standardized_difference": None,
                    "event_support": 0,
                    "background_support": 0,
                    "applicability_status": "not_applicable",
                    "exclusion_reason": "optional_upstream_summary_not_supplied",
                }
            )
            continue
        event = pd.to_numeric(callable_status.loc[diagnostic, metric], errors="coerce").dropna()
        background = pd.to_numeric(callable_status.loc[~diagnostic, metric], errors="coerce").dropna()
        pooled = np.sqrt((event.var(ddof=1) + background.var(ddof=1)) / 2)
        rows.append(
            {
                "metric": metric,
                "low_vaf_event_mean": float(event.mean()) if len(event) else None,
                "background_mean": float(background.mean()) if len(background) else None,
                "standardized_difference": float((event.mean() - background.mean()) / pooled)
                if len(event) > 1 and len(background) > 1 and pooled > 0
                else None,
                "event_support": int(len(event)),
                "background_support": int(len(background)),
                "applicability_status": "available"
                if len(event) > 1 and len(background) > 1
                else "not_applicable",
                "exclusion_reason": None
                if len(event) > 1 and len(background) > 1
                else "insufficient_low_vaf_or_background_support",
            }
        )
    return pd.DataFrame(rows)


def _canonical_substitution(reference: str, alternate: str) -> str:
    complement = {"A": "T", "T": "A", "C": "G", "G": "C"}
    reference, alternate = reference.upper(), alternate.upper()
    if reference in {"A", "G"}:
        reference, alternate = (
            complement.get(reference, reference),
            complement.get(alternate, alternate),
        )
    return f"{reference}>{alternate}"


def _callable_status(inputs: NGSInputs, config: ArtifactorConfig) -> pd.DataFrame:
    frame = inputs.allele_counts.copy()
    frame["observed_vaf"] = np.where(
        frame.total_depth > 0, frame.alt_count / frame.total_depth, np.nan
    )
    frame["callability_status"] = np.where(
        frame.total_depth >= config.ngs.minimum_total_depth, "callable", "insufficient_depth"
    )
    frame["minimum_total_depth"] = config.ngs.minimum_total_depth
    frame["minimum_alt_count_for_diagnostics"] = config.ngs.minimum_alt_count_for_diagnostics
    frame["applicability_status"] = np.where(
        frame.callability_status == "callable", "available", "not_applicable"
    )
    frame["exclusion_reason"] = np.where(
        frame.callability_status == "callable", None, "depth_below_configured_minimum"
    )
    return frame


def _variant_models(
    inputs: NGSInputs, config: ArtifactorConfig, callable_status: pd.DataFrame
) -> pd.DataFrame:
    metadata = inputs.manifest
    variables = list(
        dict.fromkeys(
            config.variables.biological + config.variables.protected + config.variables.technical
        )
    )
    design, names = encoded_design(metadata, variables)
    sample_index = {
        sample: index
        for index, sample in enumerate(metadata[config.manifest.sample_id_column].astype(str))
    }
    technical_indices = [
        index
        for index, name in enumerate(names)
        if any(
            name == variable or name.startswith(f"{variable}_")
            for variable in config.variables.technical
        )
    ]
    biological_indices = [
        index
        for index, name in enumerate(names)
        if any(
            name == variable or name.startswith(f"{variable}_")
            for variable in dict.fromkeys(config.variables.biological + config.variables.protected)
        )
    ]
    rows = []
    for variant, group in callable_status.groupby("variant_id"):
        group = group[group.callability_status == "callable"]
        indices = np.array([sample_index[str(item)] for item in group.sample_id])
        if (
            len(group) <= design.shape[1] + 2
            or group.alt_count.sum() < config.ngs.minimum_alt_count_for_diagnostics * 2
        ):
            rows.append(
                {
                    "variant_id": str(variant),
                    "model_type": "binomial_glm",
                    "model_expected_alt_fraction": None,
                    "overdispersion": None,
                    "biological_effect": None,
                    "technical_effect": None,
                    "biological_variable": None,
                    "technical_variable": None,
                    "callable_support": int(len(group)),
                    "median_depth": float(group.total_depth.median()) if len(group) else None,
                    "classification": "insufficient",
                    "model_status": "insufficient_information",
                    "applicability_status": "not_applicable",
                    "exclusion_reason": "sparse_alt_support_or_depth",
                }
            )
            continue
        try:
            proportion = group.alt_count.to_numpy(float) / group.total_depth.to_numpy(float)
            model = sm.GLM(
                proportion,
                design[indices],
                family=sm.families.Binomial(),
                var_weights=group.total_depth.to_numpy(float),
            ).fit(maxiter=100, disp=0)
            params = np.asarray(model.params)
            pvalues = np.asarray(model.pvalues)
            bio_index = max(biological_indices, key=lambda item: abs(params[item]), default=None)
            tech_index = max(technical_indices, key=lambda item: abs(params[item]), default=None)
            pearson = float(np.sum(model.resid_pearson**2) / max(model.df_resid, 1))
            model_type = (
                "quasi_binomial_overdispersion"
                if config.ngs.use_beta_binomial and pearson > 1.2
                else "binomial_glm"
            )
            rows.append(
                {
                    "variant_id": str(variant),
                    "model_type": model_type,
                    "model_expected_alt_fraction": float(
                        np.average(model.fittedvalues, weights=group.total_depth)
                    ),
                    "overdispersion": max(0.0, pearson - 1.0),
                    "biological_effect": float(params[bio_index]) if bio_index is not None else 0.0,
                    "technical_effect": float(params[tech_index])
                    if tech_index is not None
                    else 0.0,
                    "biological_variable": names[bio_index] if bio_index is not None else None,
                    "technical_variable": names[tech_index] if tech_index is not None else None,
                    "biological_p_value": float(pvalues[bio_index])
                    if bio_index is not None
                    else 1.0,
                    "technical_p_value": float(pvalues[tech_index])
                    if tech_index is not None
                    else 1.0,
                    "callable_support": int(len(group)),
                    "median_depth": float(group.total_depth.median()),
                    "classification": "unclassified",
                    "model_status": "fit",
                    "applicability_status": "available",
                    "exclusion_reason": None,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "variant_id": str(variant),
                    "model_type": "binomial_glm",
                    "model_expected_alt_fraction": None,
                    "overdispersion": None,
                    "biological_effect": None,
                    "technical_effect": None,
                    "biological_variable": None,
                    "technical_variable": None,
                    "callable_support": int(len(group)),
                    "median_depth": float(group.total_depth.median()),
                    "classification": "insufficient",
                    "model_status": "model_failure",
                    "applicability_status": "not_applicable",
                    "exclusion_reason": type(exc).__name__,
                }
            )
    results = pd.DataFrame(rows)
    fitted = results.model_status == "fit"
    if fitted.any():
        results.loc[fitted, "biological_q_value"] = multipletests(
            results.loc[fitted, "biological_p_value"].astype(float), method="fdr_bh"
        )[1]
        results.loc[fitted, "technical_q_value"] = multipletests(
            results.loc[fitted, "technical_p_value"].astype(float), method="fdr_bh"
        )[1]
        biological = (
            fitted
            & (results.biological_q_value <= 0.05)
            & (results.biological_effect.abs() >= 0.25)
        )
        technical = (
            fitted & (results.technical_q_value <= 0.05) & (results.technical_effect.abs() >= 0.25)
        )
        results.loc[fitted & biological & technical, "classification"] = "mixed"
        results.loc[fitted & biological & ~technical, "classification"] = "biological"
        results.loc[fitted & ~biological & technical, "classification"] = "technical"
        results.loc[fitted & ~biological & ~technical, "classification"] = "unexplained"
    return results


def _context_summary(
    inputs: NGSInputs, config: ArtifactorConfig, callable_status: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = callable_status.merge(inputs.variant_annotations, on="variant_id", how="left").merge(
        inputs.manifest, on="sample_id", how="left"
    )
    frame["canonical_substitution"] = [
        _canonical_substitution(r, a)
        for r, a in zip(frame.reference_allele, frame.alternate_allele, strict=True)
    ]
    frame["vaf_bin"] = pd.cut(
        frame.observed_vaf,
        [-0.001, 0.01, config.ngs.low_vaf_threshold, 0.2, 1.0],
        labels=["<=1%", "low", "intermediate", "high"],
    )
    frame["depth_bin"] = pd.cut(
        frame.total_depth,
        [-1, config.ngs.minimum_total_depth - 1, 250, 500, np.inf],
        labels=["insufficient", "100-250", "250-500", ">500"],
    )
    frame["diagnostic_event"] = (
        (frame.alt_count >= config.ngs.minimum_alt_count_for_diagnostics)
        & (frame.observed_vaf <= config.ngs.low_vaf_threshold)
        & (frame.callability_status == "callable")
    )
    group_columns = ["canonical_substitution", "trinucleotide_context", "vaf_bin", "depth_bin"]
    for variable in ("ffpe_status", *config.variables.technical):
        if variable in frame and variable not in group_columns:
            group_columns.append(variable)
    summary = (
        frame.groupby(group_columns, observed=True, dropna=False)
        .agg(
            event_count=("diagnostic_event", "sum"),
            observation_count=("variant_id", "size"),
            median_alt_count=("alt_count", "median"),
            median_total_depth=("total_depth", "median"),
            mean_observed_vaf=("observed_vaf", "mean"),
        )
        .reset_index()
    )
    summary["event_rate"] = summary.event_count / summary.observation_count
    summary["applicability_status"] = "available"
    summary["exclusion_reason"] = None
    ffpe_rows = []
    if "ffpe_status" in frame:
        candidates = frame[
            frame.canonical_substitution.isin(["C>T"]) & (frame.callability_status == "callable")
        ]
        if not candidates.empty and candidates.ffpe_status.nunique() >= 2:
            event = candidates.diagnostic_event.astype(int).to_numpy()
            ffpe_indicator = (
                (candidates.ffpe_status.astype(str).str.upper() == "FFPE").astype(int).to_numpy()
            )
            x = np.column_stack(
                [
                    np.ones(len(candidates)),
                    ffpe_indicator,
                    np.log1p(candidates.total_depth.to_numpy(float)),
                ]
            )
            try:
                fit = sm.GLM(event, x, family=sm.families.Binomial()).fit()
                ffpe_rows.append(
                    {
                        "hypothesis": "low_VAF_C>T_G>A_damage_pattern",
                        "variable": "ffpe_status",
                        "effect_log_odds": float(fit.params[1]),
                        "odds_ratio": float(np.exp(fit.params[1])),
                        "p_value": float(fit.pvalues[1]),
                        "depth_adjusted": True,
                        "event_count": int(event.sum()),
                        "observation_count": int(len(event)),
                        "interpretation": "consistent with a damage-related hypothesis"
                        if fit.params[1] > 0 and fit.pvalues[1] < 0.05
                        else "no supported FFPE-associated excess at the configured threshold",
                        "applicability_status": "available",
                        "exclusion_reason": None,
                    }
                )
            except Exception as exc:
                ffpe_rows.append(
                    {
                        "hypothesis": "low_VAF_C>T_G>A_damage_pattern",
                        "variable": "ffpe_status",
                        "effect_log_odds": None,
                        "odds_ratio": None,
                        "p_value": None,
                        "depth_adjusted": True,
                        "event_count": int(event.sum()),
                        "observation_count": int(len(event)),
                        "interpretation": "insufficient information",
                        "applicability_status": "not_applicable",
                        "exclusion_reason": type(exc).__name__,
                    }
                )
    return summary, pd.DataFrame(ffpe_rows)


def _bias_results(frame: pd.DataFrame, forward: str, reverse: str, label: str) -> pd.DataFrame:
    if forward not in frame or reverse not in frame or frame[[forward, reverse]].isna().any().any():
        return pd.DataFrame(
            [
                {
                    "variant_id": None,
                    "diagnostic": label,
                    "effect_size": None,
                    "p_value": None,
                    "support": 0,
                    "applicability_status": "unavailable",
                    "exclusion_reason": f"complete_{label}_counts_not_supplied",
                }
            ]
        )
    rows = []
    for variant, group in frame.groupby("variant_id"):
        left = int(group[forward].sum())
        right = int(group[reverse].sum())
        support = left + right
        if support < 10:
            rows.append(
                {
                    "variant_id": str(variant),
                    "diagnostic": label,
                    "effect_size": None,
                    "p_value": None,
                    "support": support,
                    "applicability_status": "not_applicable",
                    "exclusion_reason": "low_alt_support",
                }
            )
        else:
            rows.append(
                {
                    "variant_id": str(variant),
                    "diagnostic": label,
                    "effect_size": abs(left - right) / support,
                    "p_value": float(binomtest(left, support, 0.5).pvalue),
                    "support": support,
                    "applicability_status": "available",
                    "exclusion_reason": None,
                }
            )
    results = pd.DataFrame(rows)
    valid = results.p_value.notna()
    if valid.any():
        results.loc[valid, "q_value"] = multipletests(
            results.loc[valid, "p_value"].astype(float), method="fdr_bh"
        )[1]
    return results


def _control_recovery(inputs: NGSInputs, callable_status: pd.DataFrame) -> pd.DataFrame:
    if inputs.known_truth is None:
        return pd.DataFrame(
            [
                {
                    "truth_source": None,
                    "truth_state": None,
                    "depth_bin": None,
                    "expected_vaf_bin": None,
                    "observation_count": 0,
                    "callable_count": 0,
                    "recovered_count": 0,
                    "recovery_rate": None,
                    "applicability_status": "unavailable",
                    "exclusion_reason": "known_truth_not_supplied",
                }
            ]
        )
    frame = inputs.known_truth.merge(
        callable_status[
            [
                "sample_id",
                "variant_id",
                "alt_count",
                "total_depth",
                "observed_vaf",
                "callability_status",
                "existing_call_state",
            ]
        ],
        on=["sample_id", "variant_id"],
        how="left",
    )
    frame["depth_bin"] = pd.cut(
        frame.total_depth,
        [-1, 99, 249, 499, np.inf],
        labels=["<100", "100-249", "250-499", ">=500"],
    )
    frame["expected_vaf_bin"] = pd.cut(
        frame.expected_vaf.fillna(0),
        [-0.001, 0.01, 0.05, 0.2, 1.0],
        labels=["<=1%", "1-5%", "5-20%", ">20%"],
    )
    frame["recovered"] = np.where(
        frame.truth_state == "positive",
        frame.existing_call_state == "called",
        frame.existing_call_state != "called",
    )
    results = (
        frame.groupby(
            ["truth_source", "truth_state", "depth_bin", "expected_vaf_bin"],
            observed=True,
            dropna=False,
        )
        .agg(
            observation_count=("variant_id", "size"),
            callable_count=("callability_status", lambda x: int((x == "callable").sum())),
            recovered_count=("recovered", "sum"),
            median_alt_count=("alt_count", "median"),
            median_total_depth=("total_depth", "median"),
        )
        .reset_index()
    )
    results["recovery_rate"] = results.recovered_count / results.observation_count
    results["applicability_status"] = "available"
    results["exclusion_reason"] = None
    return results


def _replicate_agreement(
    inputs: NGSInputs, callable_status: pd.DataFrame, config: ArtifactorConfig
) -> pd.DataFrame:
    if "replicate_group" not in inputs.manifest:
        return pd.DataFrame(
            [
                {
                    "replicate_group": None,
                    "sample_a": None,
                    "sample_b": None,
                    "vaf_correlation": None,
                    "depth_correlation": None,
                    "call_state_agreement": None,
                    "applicability_status": "unavailable",
                    "exclusion_reason": "replicate_group_not_supplied",
                }
            ]
        )
    groups = inputs.manifest.dropna(subset=["replicate_group"]).groupby("replicate_group")
    rows = []
    for group_name, samples in groups:
        ids = samples[config.manifest.sample_id_column].astype(str).tolist()
        for left_index in range(len(ids) - 1):
            left, right = ids[left_index], ids[left_index + 1]
            a = callable_status[callable_status.sample_id.astype(str) == left].set_index(
                "variant_id"
            )
            b = callable_status[callable_status.sample_id.astype(str) == right].set_index(
                "variant_id"
            )
            common = a.index.intersection(b.index)
            if len(common) < 3:
                continue
            rows.append(
                {
                    "replicate_group": str(group_name),
                    "sample_a": left,
                    "sample_b": right,
                    "vaf_correlation": float(
                        a.loc[common, "observed_vaf"].corr(b.loc[common, "observed_vaf"])
                    ),
                    "depth_correlation": float(
                        a.loc[common, "total_depth"].corr(b.loc[common, "total_depth"])
                    ),
                    "call_state_agreement": float(
                        (
                            a.loc[common, "existing_call_state"].to_numpy()
                            == b.loc[common, "existing_call_state"].to_numpy()
                        ).mean()
                    ),
                    "applicability_status": "available",
                    "exclusion_reason": None,
                }
            )
    return (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(
            [
                {
                    "replicate_group": None,
                    "sample_a": None,
                    "sample_b": None,
                    "vaf_correlation": None,
                    "depth_correlation": None,
                    "call_state_agreement": None,
                    "applicability_status": "not_applicable",
                    "exclusion_reason": "no_adequate_replicate_pairs",
                }
            ]
        )
    )


def analyze_variants(inputs: NGSInputs, config: ArtifactorConfig) -> VariantResults:
    callable_status = _callable_status(inputs, config)
    models = _variant_models(inputs, config, callable_status)
    context, ffpe = _context_summary(inputs, config, callable_status)
    strand = (
        _bias_results(inputs.allele_counts, "alt_forward", "alt_reverse", "strand_bias")
        if config.allele_analysis.strand_bias != "disabled"
        else pd.DataFrame()
    )
    orientation = (
        _bias_results(inputs.allele_counts, "alt_f1r2", "alt_f2r1", "orientation_bias")
        if config.allele_analysis.orientation_bias != "disabled"
        else pd.DataFrame()
    )
    read_support = _read_support_diagnostics(callable_status, config)
    controls = _control_recovery(inputs, callable_status)
    replicates = _replicate_agreement(inputs, callable_status, config)
    return VariantResults(
        models,
        callable_status,
        context,
        strand,
        orientation,
        read_support,
        ffpe,
        controls,
        replicates,
    )
