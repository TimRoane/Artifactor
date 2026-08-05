from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from artifactor.config import ArtifactorConfig, ModalityConfig
from artifactor.contracts import OmicsMatrix, ValidationIssue, ValidationResult

SCHEMA_VERSION = "1.0"


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".tsv", ".txt"}:
        return pd.read_csv(path, sep="\t")
    raise ValueError(f"unsupported table format {suffix!r}; use Parquet, CSV, or TSV")


def write_table(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    if "schema_version" not in out.columns:
        out.insert(0, "schema_version", SCHEMA_VERSION)
    out.to_parquet(path, index=False)


def write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_matrix(spec: ModalityConfig, sample_id_column: str = "sample_id") -> OmicsMatrix:
    frame = read_table(spec.path)
    if spec.orientation == "features_by_samples":
        feature_column = frame.columns[0]
        frame = frame.set_index(feature_column).T.rename_axis(sample_id_column).reset_index()
    if sample_id_column not in frame:
        raise ValueError(f"{spec.name}: missing sample identifier column {sample_id_column!r}")
    if frame[sample_id_column].duplicated().any():
        dupes = (
            frame.loc[frame[sample_id_column].duplicated(), sample_id_column].astype(str).tolist()
        )
        raise ValueError(f"{spec.name}: duplicate sample IDs: {dupes[:5]}")
    feature_names = [str(c) for c in frame.columns if c != sample_id_column]
    if len(feature_names) != len(set(feature_names)):
        raise ValueError(f"{spec.name}: duplicate feature names")
    try:
        values = (
            frame.drop(columns=[sample_id_column])
            .apply(pd.to_numeric, errors="raise")
            .to_numpy(float)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{spec.name}: all feature values must be numeric") from exc
    if np.isinf(values).any():
        raise ValueError(
            f"{spec.name}: infinite values are not supported; use explicit missing values"
        )
    if spec.transform == "log1p":
        if np.nanmin(values) < -1:
            raise ValueError(f"{spec.name}: log1p requires values >= -1")
        values = np.log1p(values)
    return OmicsMatrix(
        name=spec.name,
        sample_ids=tuple(frame[sample_id_column].astype(str)),
        feature_names=tuple(feature_names),
        values=values,
        missing_mask=np.isnan(values),
        kind=spec.kind,
    )


def align_matrix(matrix: OmicsMatrix, sample_ids: list[str]) -> OmicsMatrix:
    index = {sample: i for i, sample in enumerate(matrix.sample_ids)}
    keep = [sample for sample in sample_ids if sample in index]
    rows = [index[sample] for sample in keep]
    return OmicsMatrix(
        matrix.name,
        tuple(keep),
        matrix.feature_names,
        matrix.values[rows],
        matrix.missing_mask[rows],
        matrix.kind,
    )


def load_inputs(config: ArtifactorConfig) -> tuple[pd.DataFrame, dict[str, OmicsMatrix]]:
    manifest = read_table(config.manifest.path)
    sid = config.manifest.sample_id_column
    if sid not in manifest:
        raise ValueError(f"manifest missing required column {sid!r}")
    if manifest[sid].duplicated().any():
        raise ValueError("manifest sample IDs must be unique")
    manifest[sid] = manifest[sid].astype(str)
    matrices = {m.name: load_matrix(m, sid) for m in config.modalities}
    if config.analysis.sample_join == "intersection":
        samples = set(manifest[sid])
        for matrix in matrices.values():
            samples &= set(matrix.sample_ids)
        ordered = [x for x in manifest[sid] if x in samples]
    else:
        samples = set().union(*(set(m.sample_ids) for m in matrices.values()))
        ordered = [x for x in manifest[sid] if x in samples]
    if len(ordered) < 3:
        raise ValueError("fewer than three samples remain after sample alignment")
    manifest = manifest.set_index(sid).loc[ordered].reset_index()
    return manifest, {name: align_matrix(matrix, ordered) for name, matrix in matrices.items()}


def validate_inputs(
    config: ArtifactorConfig,
) -> tuple[ValidationResult, pd.DataFrame | None, dict[str, OmicsMatrix]]:
    issues: list[ValidationIssue] = []
    try:
        manifest, matrices = load_inputs(config)
    except (OSError, ValueError) as exc:
        return (
            ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        level="error",
                        code="input_invalid",
                        message=str(exc),
                        remediation="Check paths, IDs, orientation, and numeric values.",
                    )
                ],
            ),
            None,
            {},
        )
    declared = set(
        config.variables.biological + config.variables.technical + config.variables.protected
    )
    missing = sorted(declared - set(manifest.columns))
    if missing:
        issues.append(
            ValidationIssue(
                level="error",
                code="missing_covariates",
                message=f"manifest is missing declared covariates: {missing}",
                remediation="Add the columns or remove them from variables in config.",
            )
        )
    for name, matrix in matrices.items():
        if matrix.values.shape[1] < 2:
            issues.append(
                ValidationIssue(
                    level="error",
                    code="too_few_features",
                    message=f"{name} has fewer than two features",
                )
            )
        fraction = float(matrix.missing_mask.mean())
        if fraction > 0.5:
            issues.append(
                ValidationIssue(
                    level="warning",
                    code="high_missingness",
                    message=f"{name} is {fraction:.1%} missing",
                )
            )
    return (
        ValidationResult(
            valid=not any(i.level == "error" for i in issues),
            issues=issues,
            sample_count=len(manifest),
            modality_samples={k: len(v.sample_ids) for k, v in matrices.items()},
        ),
        manifest,
        matrices,
    )
