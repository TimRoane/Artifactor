# mypy: ignore-errors
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from artifactor.config import ArtifactorConfig
from artifactor.contracts import GroundTruthRow, GroundTruthSummary, OmicsMatrix


def validate_ground_truth(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.rename(columns={"feature": "feature_id"}).copy()
    required = set(GroundTruthRow.model_fields)
    missing = sorted(required - set(normalized.columns))
    if missing:
        raise ValueError(f"ground-truth artifact is missing required columns: {missing}")
    for row in normalized.to_dict("records"):
        GroundTruthRow.model_validate(row)
    if normalized.duplicated(["modality", "feature_id"]).any():
        raise ValueError("ground-truth modality/feature rows must be unique")
    return normalized


def _slope(values: np.ndarray, variable: pd.Series) -> np.ndarray:
    filled = np.where(np.isnan(values), np.nanmedian(values, axis=0), values)
    if pd.api.types.is_numeric_dtype(variable):
        x = pd.to_numeric(variable).fillna(variable.median()).to_numpy(float)
    else:
        x = pd.Categorical(variable.astype(str)).codes.astype(float)
    x -= x.mean()
    return x @ filled / max(float(x @ x), 1e-12)


def _classification(row: pd.Series, threshold: float) -> str:
    biological = float(row.get("partial_r2_biological", 0.0) or 0.0) >= threshold
    technical = float(row.get("partial_r2_technical", 0.0) or 0.0) >= threshold
    if biological and technical:
        return "mixed"
    if biological:
        return "biological"
    if technical:
        return "technical"
    return "null"


def _truth_class(row: pd.Series) -> str:
    for name in ("biological", "technical", "mixed", "null"):
        if bool(row[f"is_{name}"]):
            return name
    raise ValueError("invalid ground-truth classification flags")


def _binary_metrics(expected: pd.Series, predicted: pd.Series) -> tuple[float, float, float]:
    tp = int((expected & predicted).sum())
    fp = int((~expected & predicted).sum())
    fn = int((expected & ~predicted).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return precision, recall, f1


def ground_truth_audit(
    truth: pd.DataFrame,
    variance: pd.DataFrame,
    matrices: dict[str, OmicsMatrix],
    metadata: pd.DataFrame,
    config: ArtifactorConfig,
    threshold: float = 0.05,
) -> tuple[pd.DataFrame, dict[str, object], pd.DataFrame]:
    truth = validate_ground_truth(truth)
    recovery = truth.merge(
        variance, left_on=["modality", "feature_id"], right_on=["modality", "feature"], how="left"
    )
    recovery["truth_class"] = recovery.apply(_truth_class, axis=1)
    recovery["predicted_class"] = recovery.apply(_classification, axis=1, threshold=threshold)
    estimates: list[dict[str, object]] = []
    for modality, matrix in matrices.items():
        subset = truth[truth.modality == modality]
        by_variable: dict[str, np.ndarray] = {}
        for variable in subset.technical_variable.dropna().unique():
            by_variable[str(variable)] = _slope(matrix.values, metadata[str(variable)])
        biological_variable = (
            config.variables.biological[0] if config.variables.biological else None
        )
        biological_estimate = (
            _slope(matrix.values, metadata[biological_variable])
            if biological_variable
            else np.zeros(matrix.values.shape[1])
        )
        feature_index = {feature: index for index, feature in enumerate(matrix.feature_names)}
        for row in subset.itertuples():
            index = feature_index[str(row.feature_id)]
            technical_estimate = (
                float(by_variable[str(row.technical_variable)][index])
                if row.technical_variable
                else 0.0
            )
            estimates.append(
                {
                    "modality": modality,
                    "feature_id": str(row.feature_id),
                    "technical_variable": row.technical_variable,
                    "injected_technical_effect": float(row.technical_effect_size),
                    "estimated_technical_effect": technical_estimate,
                    "injected_biological_effect": float(row.biological_effect_size),
                    "estimated_biological_effect": float(biological_estimate[index]),
                }
            )
    injected = pd.DataFrame(estimates)
    recovery = recovery.merge(
        injected, on=["modality", "feature_id", "technical_variable"], how="left"
    )
    truth_bio = recovery.truth_class.isin(["biological", "mixed"])
    pred_bio = recovery.predicted_class.isin(["biological", "mixed"])
    truth_tech = recovery.truth_class.isin(["technical", "mixed"])
    pred_tech = recovery.predicted_class.isin(["technical", "mixed"])
    bio_precision, bio_recall, bio_f1 = _binary_metrics(truth_bio, pred_bio)
    tech_precision, tech_recall, tech_f1 = _binary_metrics(truth_tech, pred_tech)
    null = recovery.truth_class == "null"
    false_positive_rate = float((pred_tech & null).sum() / max(int(null.sum()), 1))
    affected = injected.injected_technical_effect != 0
    rmse = (
        float(
            np.sqrt(
                np.mean(
                    (
                        injected.loc[affected, "estimated_technical_effect"]
                        - injected.loc[affected, "injected_technical_effect"]
                    )
                    ** 2
                )
            )
        )
        if affected.any()
        else 0.0
    )
    correlation = (
        float(
            injected.loc[affected, ["injected_technical_effect", "estimated_technical_effect"]]
            .corr()
            .iloc[0, 1]
        )
        if affected.sum() >= 2
        else None
    )
    summary_model = GroundTruthSummary(
        supplied=True,
        biological_precision=bio_precision,
        biological_recall=bio_recall,
        technical_precision=tech_precision,
        technical_recall=tech_recall,
        false_positive_rate_null=false_positive_rate,
        effect_rmse=rmse,
    )
    by_modality = []
    for modality, group in recovery.groupby("modality"):
        expected = group.truth_class.isin(["technical", "mixed"])
        predicted = group.predicted_class.isin(["technical", "mixed"])
        precision, recall, f1 = _binary_metrics(expected, predicted)
        by_modality.append(
            {
                "modality": modality,
                "technical_precision": precision,
                "technical_recall": recall,
                "technical_f1": f1,
            }
        )
    summary: dict[str, object] = summary_model.model_dump(mode="json") | {
        "biological_f1": bio_f1,
        "technical_f1": tech_f1,
        "technical_effect_correlation": correlation
        if correlation is None or math.isfinite(correlation)
        else None,
        "classification_threshold": threshold,
        "by_modality": by_modality,
    }
    return recovery, summary, injected
