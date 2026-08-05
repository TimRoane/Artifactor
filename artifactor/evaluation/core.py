from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, r2_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.preprocessing import LabelEncoder

from artifactor.config import ArtifactorConfig
from artifactor.contracts import OmicsMatrix
from artifactor.diagnostics import robust_matrix


def _predictability(matrix: OmicsMatrix, target: pd.Series, folds: int, seed: int) -> float:
    x, _, _ = robust_matrix(matrix, max_features=min(200, matrix.values.shape[1]))
    if pd.api.types.is_numeric_dtype(target):
        y = pd.to_numeric(target).fillna(target.median()).to_numpy(float)
        splitter = KFold(min(folds, len(y)), shuffle=True, random_state=seed)
        prediction = cross_val_predict(Ridge(alpha=10), x, y, cv=splitter)
        return max(0.0, float(r2_score(y, prediction)))
    y = LabelEncoder().fit_transform(target.astype(str))
    counts = np.bincount(y)
    n_splits = min(folds, int(counts.min()))
    if n_splits < 2:
        return 0.0
    splitter = StratifiedKFold(n_splits, shuffle=True, random_state=seed)
    prediction = cross_val_predict(LogisticRegression(max_iter=500), x, y, cv=splitter)
    return float(balanced_accuracy_score(y, prediction))


def _mapped_concordance(
    matrices: dict[str, OmicsMatrix], feature_map: pd.DataFrame | None = None
) -> float:
    if len(matrices) < 2:
        return float("nan")
    left, right = list(matrices.values())[:2]
    if feature_map is not None and feature_map.shape[1] >= 2:
        pairs = [
            (str(left_name), str(right_name))
            for left_name, right_name in feature_map.iloc[:, :2].itertuples(index=False, name=None)
            if str(left_name) in left.feature_names and str(right_name) in right.feature_names
        ]
    else:
        pairs = [
            (name, name) for name in sorted(set(left.feature_names) & set(right.feature_names))
        ]
    if not pairs:
        return float("nan")
    li = [left.feature_names.index(x) for x, _ in pairs]
    ri = [right.feature_names.index(y) for _, y in pairs]
    correlations = []
    for a, b in zip(li, ri, strict=True):
        valid = np.isfinite(left.values[:, a]) & np.isfinite(right.values[:, b])
        if valid.sum() >= 3:
            correlations.append(np.corrcoef(left.values[valid, a], right.values[valid, b])[0, 1])
    return float(np.nanmedian(correlations)) if correlations else float("nan")


def evaluate(
    corrections: dict[str, dict[str, OmicsMatrix]],
    metadata: pd.DataFrame,
    config: ArtifactorConfig,
    feature_map: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    rows = []
    raw_scores: dict[str, tuple[list[float], list[float]]] = {}
    for method, matrices in corrections.items():
        technical: list[float] = []
        biological: list[float] = []
        for matrix in matrices.values():
            technical.extend(
                _predictability(
                    matrix,
                    metadata[v],
                    config.analysis.cross_validation_folds,
                    config.project.random_seed,
                )
                for v in config.variables.technical
            )
            biological.extend(
                _predictability(
                    matrix,
                    metadata[v],
                    config.analysis.cross_validation_folds,
                    config.project.random_seed,
                )
                for v in config.variables.biological
            )
        rows.append(
            {
                "method": method,
                "technical_predictability": float(np.mean(technical)) if technical else 0.0,
                "biological_retention": float(np.mean(biological)) if biological else 1.0,
                "cross_modal_concordance": _mapped_concordance(matrices, feature_map),
            }
        )
        raw_scores[method] = (technical, biological)
    metrics = pd.DataFrame(rows)
    baseline = metrics.loc[metrics.method == "none"].iloc[0]
    metrics["technical_removal"] = 1 - metrics.technical_predictability / max(
        float(baseline.technical_predictability), 1e-12
    )
    metrics["biological_loss"] = 1 - metrics.biological_retention / max(
        float(baseline.biological_retention), 1e-12
    )
    eligible = metrics[(metrics.biological_loss <= 0.05) & (metrics.technical_removal >= 0.05)]
    if eligible.empty:
        selected = "none"
        rationale = "No eligible correction materially reduced technical predictability while preserving declared biology."
    else:
        selected = str(
            eligible.sort_values(["technical_removal", "biological_loss"], ascending=[False, True])
            .iloc[0]
            .method
        )
        rationale = f"{selected} lies on the preservation/removal frontier and maximizes technical removal under the 5% biological-loss guardrail."
    recommendation: dict[str, object] = {
        "method": selected,
        "rationale": rationale,
        "policy": {"maximum_biological_loss": 0.05, "minimum_technical_removal": 0.05},
    }
    rng = np.random.default_rng(config.project.random_seed)
    bootstrap_rows = []
    for method, (technical, biological) in raw_scores.items():
        for iteration in range(config.analysis.bootstrap_iterations):
            tech_draw = rng.choice(technical, len(technical), replace=True) if technical else [0.0]
            bio_draw = (
                rng.choice(biological, len(biological), replace=True) if biological else [1.0]
            )
            bootstrap_rows.append(
                {
                    "method": method,
                    "iteration": iteration,
                    "technical_predictability": float(np.mean(tech_draw)),
                    "biological_retention": float(np.mean(bio_draw)),
                }
            )
    bootstrap = pd.DataFrame(bootstrap_rows)
    if not bootstrap.empty:
        intervals = (
            bootstrap.groupby("method")
            .agg(
                technical_lower=("technical_predictability", lambda x: x.quantile(0.025)),
                technical_upper=("technical_predictability", lambda x: x.quantile(0.975)),
                biological_lower=("biological_retention", lambda x: x.quantile(0.025)),
                biological_upper=("biological_retention", lambda x: x.quantile(0.975)),
            )
            .reset_index()
        )
        metrics = metrics.merge(intervals, on="method", how="left")
    return metrics, bootstrap, recommendation
