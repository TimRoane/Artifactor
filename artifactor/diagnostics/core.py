from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.decomposition import PCA

from artifactor.config import ArtifactorConfig
from artifactor.contracts import OmicsMatrix
from artifactor.design import encoded_design


def bh_adjust(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = np.minimum.accumulate((ranked * len(values) / np.arange(1, len(values) + 1))[::-1])[
        ::-1
    ]
    result = np.empty_like(adjusted)
    result[order] = np.minimum(1.0, adjusted)
    return result


def robust_matrix(
    matrix: OmicsMatrix, max_features: int | None = None
) -> tuple[np.ndarray, tuple[str, ...], np.ndarray]:
    values = matrix.values.copy()
    medians = np.nanmedian(values, axis=0)
    imputed = np.where(np.isnan(values), medians, values)
    centered = imputed - medians
    mad = np.median(np.abs(centered), axis=0) * 1.4826
    std = np.std(imputed, axis=0, ddof=1)
    scale = np.where(mad > 1e-12, mad, std)
    keep = np.isfinite(scale) & (scale > 1e-12)
    original_variance = np.var(imputed[:, keep], axis=0)
    standardized = centered[:, keep] / scale[keep]
    features = np.asarray(matrix.feature_names)[keep]
    if max_features and standardized.shape[1] > max_features:
        order = np.argsort(original_variance)[-max_features:]
        standardized = standardized[:, order]
        features = features[order]
    return standardized, tuple(features), matrix.missing_mask[:, keep]


def _pca(
    name: str, values: np.ndarray, features: tuple[str, ...], components: int, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    count = min(components, values.shape[0] - 1, values.shape[1])
    model = PCA(n_components=count, svd_solver="randomized", random_state=seed)
    scores = model.fit_transform(values)
    loadings = model.components_.T
    for index in range(count):
        pivot = int(np.argmax(np.abs(loadings[:, index])))
        if loadings[pivot, index] < 0:
            loadings[:, index] *= -1
            scores[:, index] *= -1
    factors = pd.DataFrame(
        {
            "modality": name,
            "factor": [f"PC{i + 1}" for i in range(count)],
            "explained_variance_ratio": model.explained_variance_ratio_,
        }
    )
    loading_rows = [
        {
            "modality": name,
            "factor": f"PC{i + 1}",
            "feature": feature,
            "loading": float(loadings[j, i]),
        }
        for i in range(count)
        for j, feature in enumerate(features)
    ]
    return factors, pd.DataFrame(loading_rows), scores


def latent_diagnostics(
    matrices: dict[str, OmicsMatrix], config: ArtifactorConfig
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, np.ndarray], dict[str, tuple[str, ...]]]:
    factors, loadings, scores, selected = [], [], {}, {}
    blocks = []
    block_ranges: dict[str, tuple[int, int]] = {}
    cursor = 0
    by_name = {m.name: m for m in config.modalities}
    for name, matrix in matrices.items():
        values, features, _ = robust_matrix(matrix, by_name[name].max_features)
        factor, loading, score = _pca(
            name, values, features, config.analysis.latent_components, config.project.random_seed
        )
        factors.append(factor)
        loadings.append(loading)
        scores[name] = score
        selected[name] = features
        block = values / max(np.linalg.norm(values), 1e-12)
        blocks.append(block)
        block_ranges[name] = (cursor, cursor + block.shape[1])
        cursor += block.shape[1]
    joint_values = np.concatenate(blocks, axis=1)
    joint_features = tuple(
        f"{name}:{feature}" for name, feats in selected.items() for feature in feats
    )
    jf, jl, js = _pca(
        "block_pca",
        joint_values,
        joint_features,
        config.analysis.latent_components,
        config.project.random_seed,
    )
    joint_load = (
        jl.pivot(index="feature", columns="factor", values="loading")
        .loc[list(joint_features)]
        .to_numpy()
    )
    for i, factor in enumerate(jf["factor"]):
        squares = joint_load[:, i] ** 2
        total = squares.sum()
        for name, (start, end) in block_ranges.items():
            jf.loc[jf["factor"] == factor, f"contribution_{name}"] = (
                squares[start:end].sum() / total
            )
    factors.append(jf)
    loadings.append(jl)
    scores["block_pca"] = js
    return (
        pd.concat(factors, ignore_index=True),
        pd.concat(loadings, ignore_index=True),
        scores,
        selected,
    )


def _effect(values: pd.Series, score: np.ndarray) -> tuple[str, float, float]:
    valid = values.notna().to_numpy() & np.isfinite(score)
    values, score = values[valid], score[valid]
    if pd.api.types.is_numeric_dtype(values):
        effect, p = spearmanr(values, score)
        return "continuous", abs(float(effect)), float(p)
    groups = values.astype(str)
    grand = score.mean()
    total = float(((score - grand) ** 2).sum())
    between = sum(
        len(score[groups == group]) * float(score[groups == group].mean() - grand) ** 2
        for group in groups.unique()
    )
    effect = between / total if total else 0.0
    return ("binary" if groups.nunique() == 2 else "categorical"), effect, 1.0


def associations(
    scores: dict[str, np.ndarray], metadata: pd.DataFrame, config: ArtifactorConfig
) -> pd.DataFrame:
    rng = np.random.default_rng(config.project.random_seed)
    roles = (
        {v: "biological" for v in config.variables.biological}
        | {v: "technical" for v in config.variables.technical}
        | {v: "protected" for v in config.variables.protected}
    )
    rows = []
    for modality, matrix in scores.items():
        for factor_index in range(matrix.shape[1]):
            score = matrix[:, factor_index]
            for variable, role in roles.items():
                variable_type, effect, analytic_p = _effect(metadata[variable], score)
                if config.analysis.permutations:
                    null = [
                        _effect(metadata[variable], rng.permutation(score))[1]
                        for _ in range(config.analysis.permutations)
                    ]
                    p_value = (1 + sum(x >= effect for x in null)) / (1 + len(null))
                else:
                    p_value = analytic_p
                row = {
                    "modality": modality,
                    "factor": f"PC{factor_index + 1}",
                    "variable": variable,
                    "role": role,
                    "variable_type": variable_type,
                    "effect_size": effect,
                    "p_value": p_value,
                    "n": int(metadata[variable].notna().sum()),
                }
                if variable_type == "binary":
                    groups = metadata[variable].astype(str)
                    vals = [score[groups == level] for level in groups.unique()]
                    pooled = np.sqrt((np.var(vals[0], ddof=1) + np.var(vals[1], ddof=1)) / 2)
                    row["standardized_mean_difference"] = (
                        float((np.mean(vals[1]) - np.mean(vals[0])) / pooled) if pooled else 0.0
                    )
                rows.append(row)
    result = pd.DataFrame(rows)
    result["q_value"] = result.groupby(["modality", "variable"])["p_value"].transform(
        lambda x: bh_adjust(x.to_numpy())
    )
    return result


def variance_partition(
    matrix: OmicsMatrix, metadata: pd.DataFrame, config: ArtifactorConfig
) -> pd.DataFrame:
    biological = list(dict.fromkeys(config.variables.biological + config.variables.protected))
    technical = config.variables.technical
    reduced, _ = encoded_design(metadata, biological)
    full, _ = encoded_design(metadata, biological + technical)
    values = matrix.values
    complete = ~np.isnan(values).any(axis=0)
    output = []
    if complete.any():
        y = values[:, complete]
        reduced_fit = reduced @ np.linalg.lstsq(reduced, y, rcond=None)[0]
        full_fit = full @ np.linalg.lstsq(full, y, rcond=None)[0]
        sse_reduced = ((y - reduced_fit) ** 2).sum(axis=0)
        sse_full = ((y - full_fit) ** 2).sum(axis=0)
        raw = np.divide(
            sse_reduced - sse_full, sse_reduced, out=np.zeros_like(sse_full), where=sse_reduced > 0
        )
        partial_by_variable: dict[str, np.ndarray] = {}
        for variable in technical:
            dropped, _ = encoded_design(
                metadata, biological + [v for v in technical if v != variable]
            )
            dropped_fit = dropped @ np.linalg.lstsq(dropped, y, rcond=None)[0]
            dropped_sse = ((y - dropped_fit) ** 2).sum(axis=0)
            partial_by_variable[variable] = np.maximum(
                0.0,
                np.divide(
                    dropped_sse - sse_full,
                    dropped_sse,
                    out=np.zeros_like(sse_full),
                    where=dropped_sse > 0,
                ),
            )
        for feature_index, (feature, value) in enumerate(
            zip(np.asarray(matrix.feature_names)[complete], raw, strict=True)
        ):
            row = {
                "modality": matrix.name,
                "feature": feature,
                "partial_r2_technical_raw": value,
                "partial_r2_technical": max(0.0, float(value)),
                "negative_clamped": bool(value < 0),
                "insufficient_observations": False,
            }
            row.update(
                {
                    f"partial_r2_{variable}": float(values[feature_index])
                    for variable, values in partial_by_variable.items()
                }
            )
            output.append(row)
    for feature in np.asarray(matrix.feature_names)[~complete]:
        output.append(
            {
                "modality": matrix.name,
                "feature": feature,
                "partial_r2_technical_raw": np.nan,
                "partial_r2_technical": np.nan,
                "negative_clamped": False,
                "insufficient_observations": True,
            }
        )
    return pd.DataFrame(output)


def outliers(matrix: OmicsMatrix) -> pd.DataFrame:
    values, _, _ = robust_matrix(matrix)
    distance = np.sqrt(np.mean(values**2, axis=1))
    median, mad = np.median(distance), np.median(np.abs(distance - np.median(distance))) * 1.4826
    robust_z = (distance - median) / max(mad, 1e-12)
    return pd.DataFrame(
        {
            "modality": matrix.name,
            "sample_id": matrix.sample_ids,
            "robust_distance": distance,
            "robust_z": robust_z,
            "is_outlier": robust_z > 4,
        }
    )
