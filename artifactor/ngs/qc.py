# mypy: ignore-errors
from __future__ import annotations

import numpy as np
import pandas as pd

from artifactor.config import ArtifactorConfig
from artifactor.design import association_score

from .io import NGSInputs


def sample_qc_evidence(
    inputs: NGSInputs, config: ArtifactorConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sid = config.manifest.sample_id_column
    frame = inputs.manifest.merge(inputs.sample_qc, left_on=sid, right_on="sample_id", how="left")
    metric_columns = [column for column in inputs.sample_qc.columns if column != "sample_id"]
    summary_rows: list[dict[str, object]] = []
    association_rows: list[dict[str, object]] = []
    for metric in metric_columns:
        values = pd.to_numeric(frame[metric], errors="coerce")
        median = float(values.median())
        mad = float(np.nanmedian(np.abs(values - median)) * 1.4826)
        robust_z = (values - median) / max(mad, 1e-12)
        for index, sample in enumerate(frame[sid].astype(str)):
            status = (
                "missing_metric"
                if pd.isna(values.iloc[index])
                else "statistical_outlier"
                if abs(robust_z.iloc[index]) > 3.5
                else "within_robust_range"
            )
            if (
                metric in {"mean_target_depth", "median_target_depth", "callable_target_fraction"}
                and pd.notna(values.iloc[index])
                and values.iloc[index]
                < (
                    config.ngs.minimum_total_depth
                    if "depth" in metric
                    else config.ngs.minimum_callable_target_fraction
                )
            ):
                status = "low_exposure_sample"
            summary_rows.append(
                {
                    "sample_id": sample,
                    "metric_id": metric,
                    "value": None if pd.isna(values.iloc[index]) else float(values.iloc[index]),
                    "robust_z": None
                    if pd.isna(robust_z.iloc[index])
                    else float(robust_z.iloc[index]),
                    "status": status,
                    "applicability_status": "available"
                    if pd.notna(values.iloc[index])
                    else "unavailable",
                    "exclusion_reason": None
                    if pd.notna(values.iloc[index])
                    else "metric_not_supplied",
                }
            )
        for variable in dict.fromkeys(
            config.variables.biological + config.variables.technical + config.variables.protected
        ):
            if variable not in frame:
                continue
            effect = association_score(frame[variable], values)
            association_rows.append(
                {
                    "metric_id": metric,
                    "variable": variable,
                    "role": "technical"
                    if variable in config.variables.technical
                    else "protected"
                    if variable in config.variables.protected
                    else "biological",
                    "effect_size": float(effect),
                    "association_method": "absolute_spearman"
                    if pd.api.types.is_numeric_dtype(frame[variable])
                    else "eta_squared_or_bias_corrected_cramers_v",
                    "sample_support": int((values.notna() & frame[variable].notna()).sum()),
                    "applicability_status": "available",
                    "exclusion_reason": None,
                }
            )
    return pd.DataFrame(summary_rows), pd.DataFrame(association_rows)


def callability_evidence(inputs: NGSInputs, config: ArtifactorConfig) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    coverage = inputs.coverage
    for sample, group in coverage.groupby("sample_id"):
        observed = int(group.target_id.nunique())
        expected = int(
            inputs.target_annotations.loc[
                inputs.target_annotations.panel_version.astype(str)
                == str(
                    inputs.manifest.set_index(config.manifest.sample_id_column).loc[
                        str(sample), config.ngs.panel_version_column
                    ]
                ),
                "target_id",
            ].nunique()
        )
        rows.append(
            {
                "entity_type": "sample",
                "entity_id": str(sample),
                "observed_count": observed,
                "expected_count": expected,
                "callable_fraction": float((group.raw_count > 0).sum() / max(expected, 1)),
                "median_depth": float(group.mean_depth.median()) if "mean_depth" in group else None,
                "callability_status": "callable"
                if observed / max(expected, 1) >= config.ngs.minimum_callable_target_fraction
                else "low_callability",
                "structural_absence_count": max(0, inputs.summary.target_count - expected),
                "applicability_status": "available",
                "exclusion_reason": None,
            }
        )
    variants = inputs.allele_counts.assign(
        callable=inputs.allele_counts.total_depth >= config.ngs.minimum_total_depth
    )
    for sample, group in variants.groupby("sample_id"):
        rows.append(
            {
                "entity_type": "sample_variant_opportunity",
                "entity_id": str(sample),
                "observed_count": int(group.callable.sum()),
                "expected_count": int(len(group)),
                "callable_fraction": float(group.callable.mean()),
                "median_depth": float(group.total_depth.median()),
                "callability_status": "callable"
                if group.callable.mean() >= config.ngs.minimum_callable_target_fraction
                else "low_callability",
                "structural_absence_count": 0,
                "applicability_status": "available",
                "exclusion_reason": None,
            }
        )
    for target, group in coverage.groupby("target_id"):
        rows.append(
            {
                "entity_type": "target",
                "entity_id": str(target),
                "observed_count": int(len(group)),
                "expected_count": inputs.summary.sample_count,
                "callable_fraction": float((group.raw_count > 0).mean()),
                "median_depth": float(group.mean_depth.median()) if "mean_depth" in group else None,
                "callability_status": "callable"
                if (group.raw_count > 0).mean() >= config.ngs.minimum_callable_target_fraction
                else "low_callability",
                "structural_absence_count": int(inputs.summary.sample_count - len(group)),
                "applicability_status": "available",
                "exclusion_reason": None,
            }
        )
    return pd.DataFrame(rows)


def detection_opportunity(inputs: NGSInputs, config: ArtifactorConfig) -> pd.DataFrame:
    allele = inputs.allele_counts.copy()
    allele["callable"] = allele.total_depth >= config.ngs.minimum_total_depth
    allele = allele.merge(inputs.manifest, on="sample_id", how="left")
    rows = []
    for variable in dict.fromkeys(config.variables.biological + config.variables.technical):
        if variable not in allele:
            continue
        for level, group in allele.groupby(variable, dropna=False):
            rows.append(
                {
                    "variable": variable,
                    "level": str(level),
                    "sample_count": int(group.sample_id.nunique()),
                    "median_total_depth": float(group.total_depth.median()),
                    "monitored_locus_callable_fraction": float(group.callable.mean()),
                    "low_depth_fraction": float((~group.callable).mean()),
                    "interpretation": "detection opportunity is adequate"
                    if group.callable.mean() >= config.ngs.minimum_callable_target_fraction
                    else "detection opportunity is limited; absence cannot be interpreted as a negative event",
                    "applicability_status": "available",
                    "exclusion_reason": None,
                }
            )
    return pd.DataFrame(rows)
