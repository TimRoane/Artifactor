# mypy: ignore-errors
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, r2_score
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.preprocessing import LabelEncoder

from artifactor.config import ArtifactorConfig
from artifactor.contracts import OmicsMatrix
from artifactor.diagnostics import robust_matrix
from artifactor.evaluation.metrics import METRIC_REGISTRY


def _train_test_matrix(
    values: np.ndarray, train: np.ndarray, test: np.ndarray, limit: int = 200
) -> tuple[np.ndarray, np.ndarray]:
    train_values = values[train].copy()
    test_values = values[test].copy()
    medians = np.nanmedian(train_values, axis=0)
    train_values = np.where(np.isnan(train_values), medians, train_values)
    test_values = np.where(np.isnan(test_values), medians, test_values)
    variance = np.var(train_values, axis=0)
    keep = np.isfinite(variance) & (variance > 1e-12)
    indices = np.flatnonzero(keep)
    if len(indices) > limit:
        indices = indices[np.argsort(variance[indices])[-limit:]]
    center = np.median(train_values[:, indices], axis=0)
    mad = np.median(np.abs(train_values[:, indices] - center), axis=0) * 1.4826
    std = np.std(train_values[:, indices], axis=0, ddof=1)
    scale = np.where(mad > 1e-12, mad, np.maximum(std, 1e-12))
    return (train_values[:, indices] - center) / scale, (test_values[:, indices] - center) / scale


def fold_level_metrics(
    corrections: dict[str, dict[str, OmicsMatrix]], metadata: pd.DataFrame, config: ArtifactorConfig
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    roles = [("technical", variable) for variable in config.variables.technical] + [
        ("biological", variable) for variable in config.variables.biological
    ]
    for method, matrices in corrections.items():
        for modality, matrix in matrices.items():
            for role, variable in roles:
                target = metadata[variable]
                if pd.api.types.is_numeric_dtype(target):
                    y = pd.to_numeric(target).fillna(target.median()).to_numpy(float)
                    splitter = KFold(
                        min(config.analysis.cross_validation_folds, len(y)),
                        shuffle=True,
                        random_state=config.project.random_seed,
                    )
                    splits = splitter.split(y)
                    categorical = False
                else:
                    y = LabelEncoder().fit_transform(target.astype(str))
                    counts = np.bincount(y)
                    folds = min(config.analysis.cross_validation_folds, int(counts.min()))
                    if folds < 2:
                        continue
                    splitter = StratifiedKFold(
                        folds, shuffle=True, random_state=config.project.random_seed
                    )
                    splits = splitter.split(matrix.values, y)
                    categorical = True
                for fold, (train, test) in enumerate(splits):
                    x_train, x_test = _train_test_matrix(matrix.values, train, test)
                    if categorical:
                        model = LogisticRegression(max_iter=500).fit(x_train, y[train])
                        value = float(balanced_accuracy_score(y[test], model.predict(x_test)))
                    else:
                        model = Ridge(alpha=10).fit(x_train, y[train])
                        value = max(0.0, float(r2_score(y[test], model.predict(x_test))))
                    metric_id = (
                        "technical_predictability"
                        if role == "technical"
                        else "biological_retention"
                    )
                    rows.append(
                        {
                            "method": method,
                            "modality": modality,
                            "variable": variable,
                            "role": role,
                            "metric_id": metric_id,
                            "metric_family": role,
                            "value": value,
                            "direction": METRIC_REGISTRY[metric_id].direction,
                            "repeat_id": 0,
                            "fold_id": fold,
                            "n_train": len(train),
                            "n_test": len(test),
                            "eligible": True,
                            "ineligibility_reason": None,
                            "evaluation_strategy": "resampled_prediction_on_fixed_corrected_representation",
                        }
                    )
    return pd.DataFrame(rows)


def method_eligibility(
    metrics: pd.DataFrame,
    statuses: dict[str, str],
    recommendation: dict[str, object],
    config: ArtifactorConfig,
) -> pd.DataFrame:
    rows = []
    valid = metrics.copy()
    candidates = (
        valid[
            (valid.method != "none")
            & (valid.biological_loss <= 0.05)
            & (valid.technical_removal >= 0.05)
        ]
        if not valid.empty
        else valid
    )
    frontier: set[str] = set()
    for candidate in candidates.itertuples():
        dominated = any(
            (other.technical_removal >= candidate.technical_removal)
            and (other.biological_loss <= candidate.biological_loss)
            and (
                (other.technical_removal > candidate.technical_removal)
                or (other.biological_loss < candidate.biological_loss)
            )
            for other in candidates.itertuples()
        )
        if not dominated:
            frontier.add(str(candidate.method))
    for method in config.corrections.methods:
        status = statuses.get(method, "ineligible")
        metric = valid[valid.method == method]
        reasons = []
        if status != "eligible":
            reasons.append(status)
        if not metric.empty:
            row = metric.iloc[0]
            if row.biological_loss > 0.05:
                reasons.append("biological_loss_exceeds_guardrail")
            baseline_concordance = float(
                valid[valid.method == "none"].iloc[0].cross_modal_concordance
            )
            if (
                np.isfinite(baseline_concordance)
                and baseline_concordance != 0
                and float(row.cross_modal_concordance)
                < baseline_concordance * (1 - config.analysis.cross_modal_loss_guardrail)
            ):
                reasons.append("cross_modal_concordance_loss_exceeds_guardrail")
            if method != "none" and row.technical_removal < 0.05:
                reasons.append("technical_improvement_not_material")
        rows.append(
            {
                "method": method,
                "display_name": {
                    "none": "No correction",
                    "residualize": "Covariate-aware residualization",
                    "combat": "ComBat-style location/scale harmonization",
                }.get(method, method),
                "eligible": not reasons,
                "ineligibility_reason": "; ".join(reasons) or None,
                "pareto_frontier": method in frontier,
                "selected": method == recommendation.get("method"),
                "selection_reason": recommendation.get("rationale")
                if method == recommendation.get("method")
                else None,
            }
        )
    return pd.DataFrame(rows)


def _effect(values: np.ndarray, variable: pd.Series) -> np.ndarray:
    filled = np.where(np.isnan(values), np.nanmedian(values, axis=0), values)
    if pd.api.types.is_numeric_dtype(variable):
        x = pd.to_numeric(variable).fillna(variable.median()).to_numpy(float)
        x = x - x.mean()
        return x @ filled / max(float(x @ x), 1e-12)
    labels = variable.astype(str)
    levels = list(labels.unique())
    if len(levels) < 2:
        return np.zeros(filled.shape[1])
    group_means = np.vstack([filled[labels == level].mean(axis=0) for level in levels])
    return group_means.max(axis=0) - group_means.min(axis=0)


def effect_retention(
    corrections: dict[str, dict[str, OmicsMatrix]], metadata: pd.DataFrame, config: ArtifactorConfig
) -> pd.DataFrame:
    if "none" not in corrections:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for modality, baseline in corrections["none"].items():
        for variable in dict.fromkeys(config.variables.protected):
            before = _effect(baseline.values, metadata[variable])
            for method, matrices in corrections.items():
                after = _effect(matrices[modality].values, metadata[variable])
                for index, feature in enumerate(baseline.feature_names):
                    denominator = abs(float(before[index]))
                    rows.append(
                        {
                            "method": method,
                            "modality": modality,
                            "variable": variable,
                            "feature": feature,
                            "effect_before": float(before[index]),
                            "effect_after": float(after[index]),
                            "direction_agreement": bool(
                                np.sign(before[index]) == np.sign(after[index])
                            ),
                            "magnitude_retention": abs(float(after[index])) / denominator
                            if denominator > 1e-8
                            else None,
                        }
                    )
    return pd.DataFrame(rows)


def correction_visualization(
    corrections: dict[str, dict[str, OmicsMatrix]], metadata: pd.DataFrame, config: ArtifactorConfig
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    metadata_columns = list(
        dict.fromkeys(
            config.variables.biological + config.variables.technical + config.variables.protected
        )
    )
    sid = config.manifest.sample_id_column
    for method, matrices in corrections.items():
        for modality, matrix in matrices.items():
            values, _, _ = robust_matrix(matrix, max_features=min(500, matrix.values.shape[1]))
            components = PCA(
                n_components=2, svd_solver="randomized", random_state=config.project.random_seed
            ).fit_transform(values)
            for index, sample in enumerate(metadata[sid].astype(str)):
                row: dict[str, object] = {
                    "method": method,
                    "modality": modality,
                    "sample_id": sample,
                    "pc1": float(components[index, 0]),
                    "pc2": float(components[index, 1]),
                }
                row.update({column: metadata.iloc[index][column] for column in metadata_columns})
                rows.append(row)
    return pd.DataFrame(rows)
