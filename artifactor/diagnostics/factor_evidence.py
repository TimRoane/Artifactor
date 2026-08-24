# mypy: ignore-errors
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from artifactor.config import ArtifactorConfig
from artifactor.contracts import FactorSummary, OmicsMatrix
from artifactor.diagnostics.core import robust_matrix


def _blocks(
    matrices: dict[str, OmicsMatrix], config: ArtifactorConfig
) -> dict[str, tuple[np.ndarray, tuple[str, ...]]]:
    specs = {item.name: item for item in config.modalities}
    result: dict[str, tuple[np.ndarray, tuple[str, ...]]] = {}
    joint: list[np.ndarray] = []
    joint_features: list[str] = []
    for name, matrix in matrices.items():
        values, features, _ = robust_matrix(matrix, specs[name].max_features)
        result[name] = (values, features)
        joint.append(values / max(np.linalg.norm(values), 1e-12))
        joint_features.extend(f"{name}:{feature}" for feature in features)
    result["block_pca"] = (np.concatenate(joint, axis=1), tuple(joint_features))
    return result


def factor_stability(
    matrices: dict[str, OmicsMatrix], loadings: pd.DataFrame, config: ArtifactorConfig
) -> dict[tuple[str, str], float]:
    iterations = config.analysis.factor_stability_bootstraps
    if iterations == 0:
        return {
            (str(r.modality), str(r.factor)): 1.0
            for r in loadings[["modality", "factor"]].drop_duplicates().itertuples()
        }
    rng = np.random.default_rng(config.project.random_seed)
    result: dict[tuple[str, str], float] = {}
    for modality, (values, features) in _blocks(matrices, config).items():
        base = (
            loadings[loadings.modality == modality]
            .pivot(index="feature", columns="factor", values="loading")
            .reindex(features)
        )
        factor_names = list(base.columns)
        base_values = base.to_numpy(float)
        similarities = np.zeros((iterations, len(factor_names)))
        for iteration in range(iterations):
            rows = rng.integers(0, values.shape[0], values.shape[0])
            model = PCA(
                n_components=min(len(factor_names), values.shape[0] - 1, values.shape[1]),
                svd_solver="randomized",
                random_state=config.project.random_seed + iteration,
            ).fit(values[rows])
            boot = model.components_.T
            cross = np.abs(base_values.T @ boot)
            denom = (
                np.linalg.norm(base_values, axis=0)[:, None] * np.linalg.norm(boot, axis=0)[None, :]
            )
            similarities[iteration] = np.max(cross / np.maximum(denom, 1e-12), axis=1)
        for index, factor in enumerate(factor_names):
            result[(modality, str(factor))] = float(np.mean(similarities[:, index]))
    return result


def build_factor_artifacts(
    matrices: dict[str, OmicsMatrix],
    factors: pd.DataFrame,
    loadings: pd.DataFrame,
    scores: dict[str, np.ndarray],
    associations: pd.DataFrame,
    metadata: pd.DataFrame,
    config: ArtifactorConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stability = factor_stability(matrices, loadings, config)
    summaries: list[dict[str, object]] = []
    contributions: list[dict[str, object]] = []
    for row in factors.itertuples():
        subset = associations[
            (associations.modality == row.modality) & (associations.factor == row.factor)
        ]
        biological = subset[subset.role.isin(["biological", "protected"])].sort_values(
            "effect_size", ascending=False
        )
        technical = subset[subset.role == "technical"].sort_values("effect_size", ascending=False)
        stable = stability.get((str(row.modality), str(row.factor)), 0.0)
        strongest = float(subset.effect_size.max()) if not subset.empty else 0.0
        confidence = (
            "high"
            if strongest >= 0.5 and stable >= 0.8
            else "moderate"
            if strongest >= 0.2 and stable >= 0.6
            else "low"
        )
        model = FactorSummary(
            modality=str(row.modality),
            factor=str(row.factor),
            variance_explained=float(row.explained_variance_ratio),
            classification=str(row.classification),
            classification_confidence=confidence,
            leading_biological_variable=str(biological.iloc[0].variable)
            if not biological.empty
            else None,
            leading_biological_effect_size=float(biological.iloc[0].effect_size)
            if not biological.empty
            else None,
            leading_technical_variable=str(technical.iloc[0].variable)
            if not technical.empty
            else None,
            leading_technical_effect_size=float(technical.iloc[0].effect_size)
            if not technical.empty
            else None,
            stability=stable,
            n_samples=len(metadata),
        )
        summaries.append(model.model_dump())
        for column in factors.columns:
            if column.startswith("contribution_") and pd.notna(getattr(row, column)):
                contributions.append(
                    {
                        "factor": str(row.factor),
                        "source_modality": column.removeprefix("contribution_"),
                        "contribution": float(getattr(row, column)),
                    }
                )
    score_rows: list[dict[str, object]] = []
    sid = config.manifest.sample_id_column
    metadata_columns = list(
        dict.fromkeys(
            config.variables.biological + config.variables.technical + config.variables.protected
        )
    )
    for modality, values in scores.items():
        for sample_index, sample in enumerate(metadata[sid].astype(str)):
            for component in range(values.shape[1]):
                item: dict[str, object] = {
                    "modality": modality,
                    "sample_id": sample,
                    "factor": f"PC{component + 1}",
                    "score": float(values[sample_index, component]),
                }
                item.update(
                    {column: metadata.iloc[sample_index][column] for column in metadata_columns}
                )
                score_rows.append(item)
    return (
        pd.DataFrame(summaries),
        pd.DataFrame(score_rows),
        loadings.copy(),
        pd.DataFrame(contributions),
    )


def visualization_sample(
    scores: pd.DataFrame, config: ArtifactorConfig
) -> tuple[pd.DataFrame, str]:
    limit = config.report.browser_embedding_limit
    metadata_columns = [
        c
        for c in scores.columns
        if c not in {"modality", "factor", "score", "schema_version", "sample_id"}
    ]
    samples = scores[["sample_id", *metadata_columns]].drop_duplicates("sample_id")
    if len(samples) <= limit:
        return scores.copy(), f"all {len(samples)} samples; no downsampling"
    strata = list(dict.fromkeys(config.variables.biological + config.variables.technical))
    per_group = (
        max(1, limit // max(1, samples.groupby(strata, dropna=False).ngroups)) if strata else limit
    )
    selected = (
        samples.groupby(strata, dropna=False, group_keys=False).head(per_group).head(limit)
        if strata
        else samples.head(limit)
    )
    return scores[
        scores.sample_id.isin(set(selected.sample_id))
    ].copy(), f"stratified deterministic {limit}-sample limit by {strata}"
