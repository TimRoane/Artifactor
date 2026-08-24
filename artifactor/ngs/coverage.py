# mypy: ignore-errors
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, r2_score
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
from statsmodels.stats.multitest import multipletests

from artifactor.config import ArtifactorConfig
from artifactor.contracts import DesignSummary
from artifactor.design import association_score, encoded_design

from .io import NGSInputs


@dataclass
class CoverageResults:
    model_results: pd.DataFrame
    factor_scores: pd.DataFrame
    factor_loadings: pd.DataFrame
    factor_associations: pd.DataFrame
    gc_curves: pd.DataFrame
    representation_metrics: pd.DataFrame
    representation_eligibility: pd.DataFrame
    target_effect_retention: pd.DataFrame
    recommendation: dict[str, object]
    representations: dict[str, pd.DataFrame]


def _coverage_matrix(
    inputs: NGSInputs, config: ArtifactorConfig
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    sid = config.manifest.sample_id_column
    samples = inputs.manifest[sid].astype(str).to_numpy()
    targets = inputs.common_targets.target_id.astype(str).to_numpy()
    wide = (
        inputs.coverage[inputs.coverage.target_id.astype(str).isin(set(targets))]
        .pivot(index="sample_id", columns="target_id", values="raw_count")
        .reindex(index=samples, columns=targets)
    )
    if wide.isna().any().any():
        raise ValueError(
            "common-target coverage contains missing observations; structural absence must remain outside the common universe"
        )
    annotation = inputs.common_targets.set_index("target_id").reindex(targets)
    lengths = annotation.target_length.to_numpy(float)
    qc = inputs.sample_qc.set_index("sample_id").reindex(samples)
    exposure_column = (
        "usable_fragments"
        if "usable_fragments" in qc and qc.usable_fragments.notna().all()
        else "total_reads"
    )
    exposure = pd.to_numeric(qc[exposure_column]).to_numpy(float)
    if np.any(exposure <= 0) or np.any(lengths <= 0):
        raise ValueError("coverage offsets require positive exposure and effective target length")
    return wide, samples, targets, exposure


def _offset_normalized(counts: np.ndarray, exposure: np.ndarray, lengths: np.ndarray) -> np.ndarray:
    opportunity = (exposure / np.median(exposure))[:, None] * (lengths / np.median(lengths))[
        None, :
    ]
    return np.log1p(counts / opportunity)


def _median_ratio(counts: np.ndarray, lengths: np.ndarray) -> np.ndarray:
    positive = counts > 0
    log_values = np.where(positive, np.log(np.maximum(counts, 1)), np.nan)
    geometric = np.exp(np.nanmean(log_values, axis=0))
    usable = np.isfinite(geometric) & (geometric > 0)
    ratios = counts[:, usable] / geometric[usable]
    ratios[ratios <= 0] = np.nan
    size_factors = np.nanmedian(ratios, axis=1)
    size_factors = np.where(np.isfinite(size_factors) & (size_factors > 0), size_factors, 1.0)
    return np.log1p(counts / size_factors[:, None] / (lengths / np.median(lengths))[None, :])


def _gc_normalize(
    values: np.ndarray, gc: np.ndarray, samples: np.ndarray
) -> tuple[np.ndarray, pd.DataFrame]:
    adjusted = np.zeros_like(values)
    rows = []
    grid = np.linspace(float(np.nanmin(gc)), float(np.nanmax(gc)), 25)
    for index, sample in enumerate(samples):
        coefficients = np.polyfit(gc, values[index], 2)
        fitted = np.polyval(coefficients, gc)
        adjusted[index] = values[index] - fitted + np.mean(fitted)
        for gc_value in grid:
            rows.append(
                {
                    "sample_id": str(sample),
                    "gc_fraction": float(gc_value),
                    "fitted_log_coverage": float(np.polyval(coefficients, gc_value)),
                    "curve_model": "quadratic_within_sample",
                    "applicability_status": "available",
                    "exclusion_reason": None,
                }
            )
    return adjusted, pd.DataFrame(rows)


def _fit_target_models(
    counts: np.ndarray,
    exposure: np.ndarray,
    lengths: np.ndarray,
    targets: np.ndarray,
    metadata: pd.DataFrame,
    config: ArtifactorConfig,
    raw_values: np.ndarray,
) -> tuple[pd.DataFrame, np.ndarray]:
    variables = list(
        dict.fromkeys(
            config.variables.biological + config.variables.protected + config.variables.technical
        )
    )
    design, names = encoded_design(metadata, variables)
    offset = np.log(
        (exposure / np.median(exposure))[:, None] * (lengths / np.median(lengths))[None, :]
    )
    means = counts.mean(axis=0)
    variances = counts.var(axis=0, ddof=1)
    raw_dispersion = np.maximum((variances - means) / np.maximum(means**2, 1e-12), 0.01)
    center = float(np.median(raw_dispersion[np.isfinite(raw_dispersion)]))
    dispersions = 0.5 * raw_dispersion + 0.5 * center
    rows: list[dict[str, object]] = []
    technical_residual = raw_values.copy()
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
            for variable in config.variables.biological
        )
    ]
    for target_index, target in enumerate(targets):
        y = counts[:, target_index]
        support = np.isfinite(y) & np.isfinite(offset[:, target_index])
        if support.sum() <= design.shape[1] + 2 or y[support].sum() == 0:
            rows.append(
                {
                    "target_id": str(target),
                    "model_type": "negative_binomial_glm",
                    "dispersion": float(dispersions[target_index]),
                    "biological_effect": None,
                    "technical_effect": None,
                    "biological_variable": None,
                    "technical_variable": None,
                    "biological_p_value": None,
                    "technical_p_value": None,
                    "sample_support": int(support.sum()),
                    "callability_fraction": float((y[support] > 0).mean()),
                    "classification": "insufficient",
                    "model_status": "insufficient_information",
                    "applicability_status": "not_applicable",
                    "exclusion_reason": "inadequate_nonzero_support",
                }
            )
            continue
        try:
            model = sm.GLM(
                y[support],
                design[support],
                family=sm.families.NegativeBinomial(alpha=float(dispersions[target_index])),
                offset=offset[support, target_index],
            ).fit(maxiter=100, disp=0)
            params = np.asarray(model.params)
            pvalues = np.asarray(model.pvalues)
            bio_index = max(biological_indices, key=lambda item: abs(params[item]), default=None)
            tech_index = max(technical_indices, key=lambda item: abs(params[item]), default=None)
            bio_effect = float(params[bio_index]) if bio_index is not None else 0.0
            tech_effect = float(params[tech_index]) if tech_index is not None else 0.0
            bio_p = float(pvalues[bio_index]) if bio_index is not None else 1.0
            tech_p = float(pvalues[tech_index]) if tech_index is not None else 1.0
            if technical_indices:
                technical_residual[:, target_index] = (
                    raw_values[:, target_index]
                    - design[:, technical_indices] @ params[technical_indices]
                )
            rows.append(
                {
                    "target_id": str(target),
                    "model_type": "negative_binomial_glm",
                    "dispersion": float(dispersions[target_index]),
                    "biological_effect": bio_effect,
                    "technical_effect": tech_effect,
                    "biological_variable": names[bio_index] if bio_index is not None else None,
                    "technical_variable": names[tech_index] if tech_index is not None else None,
                    "biological_standard_error": float(model.bse[bio_index])
                    if bio_index is not None
                    else None,
                    "technical_standard_error": float(model.bse[tech_index])
                    if tech_index is not None
                    else None,
                    "biological_p_value": bio_p,
                    "technical_p_value": tech_p,
                    "partial_deviance_biological": abs(bio_effect)
                    / max(abs(bio_effect) + abs(tech_effect), 1e-12),
                    "partial_deviance_technical": abs(tech_effect)
                    / max(abs(bio_effect) + abs(tech_effect), 1e-12),
                    "sample_support": int(support.sum()),
                    "callability_fraction": float((y[support] > 0).mean()),
                    "classification": "unclassified",
                    "model_status": "fit",
                    "applicability_status": "available",
                    "exclusion_reason": None,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "target_id": str(target),
                    "model_type": "negative_binomial_glm",
                    "dispersion": float(dispersions[target_index]),
                    "biological_effect": None,
                    "technical_effect": None,
                    "biological_variable": None,
                    "technical_variable": None,
                    "biological_p_value": None,
                    "technical_p_value": None,
                    "sample_support": int(support.sum()),
                    "callability_fraction": float((y[support] > 0).mean()),
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
            fitted & (results.biological_q_value <= 0.05) & (results.biological_effect.abs() >= 0.2)
        )
        technical = (
            fitted & (results.technical_q_value <= 0.01) & (results.technical_effect.abs() >= 0.4)
        )
        results.loc[fitted & biological & technical, "classification"] = "mixed"
        results.loc[fitted & biological & ~technical, "classification"] = "biological"
        results.loc[fitted & ~biological & technical, "classification"] = "technical"
        results.loc[fitted & ~biological & ~technical, "classification"] = "unexplained"
    return results, technical_residual


def _factor_artifacts(
    values: np.ndarray,
    samples: np.ndarray,
    targets: np.ndarray,
    metadata: pd.DataFrame,
    config: ArtifactorConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scaled = StandardScaler().fit_transform(values)
    components = min(config.analysis.latent_components, scaled.shape[0] - 1, scaled.shape[1])
    model = PCA(
        n_components=components, svd_solver="randomized", random_state=config.project.random_seed
    ).fit(scaled)
    scores = model.transform(scaled)
    score_rows = []
    metadata_columns = list(
        dict.fromkeys(
            config.variables.biological
            + config.variables.technical
            + config.variables.protected
            + config.variables.controls
        )
    )
    for sample_index, sample in enumerate(samples):
        for factor_index in range(components):
            row = {
                "sample_id": str(sample),
                "factor": f"PC{factor_index + 1}",
                "score": float(scores[sample_index, factor_index]),
                "variance_explained": float(model.explained_variance_ratio_[factor_index]),
                "representation": "raw_offset_count_aware",
                "exploratory": True,
                "applicability_status": "available",
                "exclusion_reason": None,
            }
            row.update(
                {
                    column: metadata.iloc[sample_index][column]
                    for column in metadata_columns
                    if column in metadata
                }
            )
            score_rows.append(row)
    loading_rows = [
        {
            "target_id": str(target),
            "factor": f"PC{factor + 1}",
            "loading": float(model.components_[factor, target_index]),
            "representation": "raw_offset_count_aware",
            "applicability_status": "available",
            "exclusion_reason": None,
        }
        for factor in range(components)
        for target_index, target in enumerate(targets)
    ]
    association_rows = []
    for factor_index in range(components):
        factor_values = pd.Series(scores[:, factor_index])
        for variable in dict.fromkeys(
            config.variables.biological + config.variables.technical + config.variables.protected
        ):
            association_rows.append(
                {
                    "factor": f"PC{factor_index + 1}",
                    "variable": variable,
                    "role": "technical"
                    if variable in config.variables.technical
                    else "protected"
                    if variable in config.variables.protected
                    else "biological",
                    "effect_size": float(association_score(metadata[variable], factor_values)),
                    "association_method": "measurement_type_aware_effect_size",
                    "applicability_status": "available",
                    "exclusion_reason": None,
                }
            )
    return pd.DataFrame(score_rows), pd.DataFrame(loading_rows), pd.DataFrame(association_rows)


def _predictability(
    values: np.ndarray,
    target: pd.Series,
    groups: pd.Series,
    folds: int,
    seed: int,
) -> float:
    components = min(8, values.shape[0] - 1, values.shape[1])
    group_values = groups.fillna(pd.Series(target.index, index=target.index).map(str)).astype(str)
    n_groups = group_values.nunique()
    n_splits = min(folds, n_groups)
    if n_splits < 2:
        return 0.0
    if pd.api.types.is_numeric_dtype(target):
        y = pd.to_numeric(target).fillna(target.median()).to_numpy(float)
        splitter = GroupKFold(n_splits).split(values, y, group_values)
        estimator = lambda: Ridge(alpha=10)  # noqa: E731
        categorical = False
    else:
        y = LabelEncoder().fit_transform(target.astype(str))
        count = np.bincount(y)
        n_splits = min(n_splits, int(count.min()))
        if n_splits < 2:
            return 0.0
        splitter = StratifiedGroupKFold(n_splits, shuffle=True, random_state=seed).split(
            values, y, group_values
        )
        estimator = lambda: LogisticRegression(max_iter=500)  # noqa: E731
        categorical = True
    prediction = np.zeros_like(y, dtype=int if categorical else float)
    for train, test in splitter:
        scaler = StandardScaler().fit(values[train])
        scaled_train = scaler.transform(values[train])
        scaled_test = scaler.transform(values[test])
        fold_components = min(components, len(train) - 1)
        projector = PCA(
            n_components=fold_components, svd_solver="randomized", random_state=seed
        ).fit(scaled_train)
        model = estimator().fit(projector.transform(scaled_train), y[train])
        prediction[test] = model.predict(projector.transform(scaled_test))
    if not categorical:
        return max(0.0, float(r2_score(y, prediction)))
    score = float(balanced_accuracy_score(y, prediction))
    chance = 1.0 / max(len(count), 1)
    return max(0.0, (score - chance) / max(1.0 - chance, 1e-12))


def _evaluate_representations(
    representations: dict[str, np.ndarray],
    metadata: pd.DataFrame,
    config: ArtifactorConfig,
    design: DesignSummary,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    rows = []
    group_column = config.evaluation.group_column
    groups = (
        metadata[group_column]
        if group_column and group_column in metadata
        else pd.Series(metadata.index.map(str), index=metadata.index)
    )
    for name, values in representations.items():
        technical = [
            _predictability(
                values,
                metadata[variable],
                groups,
                config.evaluation.cross_validation_folds,
                config.project.random_seed,
            )
            for variable in config.variables.technical
        ]
        biological = [
            _predictability(
                values,
                metadata[variable],
                groups,
                config.evaluation.cross_validation_folds,
                config.project.random_seed,
            )
            for variable in config.variables.biological
        ]
        replicate_values = []
        if "replicate_group" in metadata:
            for _, group in metadata.dropna(subset=["replicate_group"]).groupby("replicate_group"):
                indices = group.index.to_numpy()
                for pair_index in range(len(indices) - 1):
                    replicate_values.append(
                        float(
                            np.corrcoef(
                                values[indices[pair_index]], values[indices[pair_index + 1]]
                            )[0, 1]
                        )
                    )
        rows.append(
            {
                "representation": name,
                "technical_predictability": float(np.mean(technical)) if technical else 0.0,
                "biological_predictability": float(np.mean(biological)) if biological else 1.0,
                "evaluation_strategy": "grouped_resampled_prediction_on_fixed_unsupervised_or_declared-covariate_representation",
                "group_column": group_column or "sample_id",
                "exploratory": name != "raw_offset",
                "replicate_agreement": float(np.nanmedian(replicate_values))
                if replicate_values
                else None,
                "applicability_status": "available",
                "exclusion_reason": None,
            }
        )
    summary = pd.DataFrame(rows)
    baseline = summary[summary.representation == "raw_offset"].iloc[0]
    summary["technical_removal"] = 1 - summary.technical_predictability / max(
        float(baseline.technical_predictability), config.analysis.technical_baseline_tolerance
    )
    summary["biological_loss"] = 1 - summary.biological_predictability / max(
        float(baseline.biological_predictability), config.analysis.technical_baseline_tolerance
    )
    baseline_replicate = baseline.replicate_agreement
    summary["replicate_loss"] = (
        0.0
        if pd.isna(baseline_replicate)
        else 1 - summary.replicate_agreement / max(float(baseline_replicate), 1e-8)
    )
    eligibility_rows = []
    candidates = []
    for row in summary.itertuples():
        reasons = []
        if row.representation != "raw_offset" and not design.correction_permitted:
            reasons.append("design_gate_refused_mitigation")
        if row.biological_loss > config.coverage_analysis.maximum_biological_loss:
            reasons.append("protected_biological_loss_exceeds_guardrail")
        if (
            row.representation != "raw_offset"
            and row.technical_removal < config.coverage_analysis.minimum_technical_removal
        ):
            reasons.append("technical_improvement_not_material")
        if (
            pd.notna(row.replicate_loss)
            and row.replicate_loss > config.coverage_analysis.maximum_replicate_loss
        ):
            reasons.append("replicate_agreement_loss_exceeds_guardrail")
        eligible = not reasons
        if eligible and row.representation != "raw_offset":
            candidates.append(row)
        eligibility_rows.append(
            {
                "representation": row.representation,
                "eligible": eligible,
                "ineligibility_reason": "; ".join(reasons) or None,
                "supported_measurement_family": "count",
                "required_design_status": "separable_or_weak_overlap",
                "intended_use": "exploratory coverage visualization and discovery",
                "raw_observations_overwritten": False,
                "applicability_status": "available",
                "exclusion_reason": None,
            }
        )
    if candidates:
        selected_row = sorted(
            candidates, key=lambda item: (-item.technical_removal, item.biological_loss)
        )[0]
        selected = str(selected_row.representation)
        rationale = f"{selected} is the strongest eligible exploratory count-aware representation under technical-removal and protected-biology guardrails. Original coverage counts remain unchanged."
    else:
        selected = "raw_offset"
        rationale = "No exploratory coverage mitigation is scientifically eligible; retain the offset-aware baseline. Original coverage counts remain unchanged."
    eligibility = pd.DataFrame(eligibility_rows)
    eligibility["selected"] = eligibility.representation == selected
    recommendation = {
        "method": selected,
        "representation": selected,
        "diagnostic_only": selected == "raw_offset",
        "rationale": rationale,
        "original_observations_unchanged": True,
        "policy": {
            "maximum_biological_loss": config.coverage_analysis.maximum_biological_loss,
            "minimum_technical_removal": config.coverage_analysis.minimum_technical_removal,
        },
    }
    return summary, eligibility, recommendation


def analyze_coverage(
    inputs: NGSInputs, config: ArtifactorConfig, design: DesignSummary
) -> CoverageResults:
    wide, samples, targets, exposure = _coverage_matrix(inputs, config)
    counts = wide.to_numpy(float)
    annotations = (
        inputs.common_targets.drop_duplicates("target_id").set_index("target_id").reindex(targets)
    )
    lengths = annotations.target_length.to_numpy(float)
    gc = annotations.gc_fraction.fillna(annotations.gc_fraction.median()).to_numpy(float)
    raw = _offset_normalized(counts, exposure, lengths)
    median_ratio = _median_ratio(counts, lengths)
    gc_values, gc_curves = _gc_normalize(raw, gc, samples)
    model_results, technical_residual = _fit_target_models(
        counts, exposure, lengths, targets, inputs.manifest, config, raw
    )
    representations_array = {
        "raw_offset": raw,
        "median_ratio": median_ratio,
        "gc_normalized": gc_values,
        "nb_technical_residual": technical_residual,
    }
    representations_array = {
        name: values
        for name, values in representations_array.items()
        if name in config.coverage_analysis.candidates
    }
    scores, loadings, associations = _factor_artifacts(
        raw, samples, targets, inputs.manifest, config
    )
    metrics, eligibility, recommendation = _evaluate_representations(
        representations_array, inputs.manifest, config, design
    )
    representation_frames = {}
    for name, values in representations_array.items():
        frame = pd.DataFrame(values, columns=targets)
        frame.insert(0, "sample_id", samples)
        representation_frames[name] = frame
    retention_rows = []
    baseline_effect = model_results.set_index("target_id").biological_effect
    for name, values in representations_array.items():
        condition = (
            pd.Categorical(inputs.manifest[config.variables.biological[0]]).codes.astype(float)
            if config.variables.biological
            else np.zeros(len(samples))
        )
        centered = condition - condition.mean()
        effects = centered @ values / max(float(centered @ centered), 1e-12)
        for index, target in enumerate(targets):
            before = baseline_effect.get(str(target))
            retention_rows.append(
                {
                    "representation": name,
                    "target_id": str(target),
                    "biological_effect_before": None if pd.isna(before) else float(before),
                    "biological_effect_after": float(effects[index]),
                    "direction_agreement": None
                    if pd.isna(before)
                    else bool(np.sign(before) == np.sign(effects[index])),
                    "magnitude_retention": None
                    if pd.isna(before) or abs(before) < 1e-8
                    else abs(float(effects[index])) / abs(float(before)),
                    "applicability_status": "available",
                    "exclusion_reason": None,
                }
            )
    return CoverageResults(
        model_results,
        scores,
        loadings,
        associations,
        gc_curves,
        metrics,
        eligibility,
        pd.DataFrame(retention_rows),
        recommendation,
        representation_frames,
    )
