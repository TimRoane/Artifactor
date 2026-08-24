from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field

from artifactor.config import load_config
from artifactor.design import audit_design
from artifactor.io import read_table, validate_inputs, write_json

Orientation = Literal["samples_by_features", "features_by_samples"]
ModalityKind = Literal[
    "rna_continuous", "proteomics_continuous", "generic_continuous", "genomic_continuous"
]


class MatrixInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    orientation: Orientation
    matrix_sample_id_column: str | None
    sample_count: int = Field(ge=0)
    feature_count: int = Field(ge=0)
    matched_samples: int = Field(ge=0)
    metadata_only_samples: int = Field(ge=0)
    matrix_only_samples: int = Field(ge=0)
    numeric_fraction: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class InputInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "4.1"
    metadata_sample_id_column: str
    metadata_rows: int = Field(ge=0)
    metadata_columns: list[str]
    matrices: list[MatrixInspection]
    suggested_biological: list[str]
    suggested_technical: list[str]
    suggested_protected: list[str]
    suggested_identifier: list[str]
    suggested_ignore: list[str]
    warnings: list[str] = Field(default_factory=list)


TECHNICAL_WORDS = {
    "batch", "plate", "lane", "lot", "center", "centre", "site", "instrument",
    "operator", "run", "flowcell", "chip", "processing", "extraction", "library",
    "rin", "quality", "qc",
}
BIOLOGICAL_WORDS = {
    "condition", "treatment", "disease", "phenotype", "tissue", "group", "sex",
    "gender", "age", "stage", "timepoint", "response", "genotype", "case_control",
}
ID_WORDS = {"sample_id", "sample", "sampleid", "id", "specimen_id", "subject_id"}


def _tokens(value: str) -> set[str]:
    return set(re.split(r"[^a-z0-9]+", value.lower()))


def infer_sample_id(metadata: pd.DataFrame, matrices: dict[str, pd.DataFrame]) -> str:
    best: tuple[float, str] | None = None
    matrix_sets: list[set[str]] = []
    for frame in matrices.values():
        if len(frame.columns):
            matrix_sets.append(set(frame.iloc[:, 0].dropna().astype(str)))
            matrix_sets.append(set(map(str, frame.columns[1:])))
    for column in metadata.columns:
        values = metadata[column].dropna().astype(str)
        if values.empty or values.duplicated().any():
            continue
        overlap = max(
            (len(set(values) & candidates) / max(1, len(values)) for candidates in matrix_sets),
            default=0.0,
        )
        name_bonus = 0.25 if str(column).lower() in ID_WORDS else 0.0
        score = overlap + name_bonus
        if best is None or score > best[0]:
            best = (score, str(column))
    if best is None or best[0] < 0.5:
        raise ValueError(
            "Could not identify a unique metadata sample-ID column that overlaps the matrix. "
            "Choose the sample-ID column explicitly."
        )
    return best[1]


def suggest_roles(metadata: pd.DataFrame, sample_id_column: str) -> dict[str, list[str]]:
    biological: list[str] = []
    technical: list[str] = []
    identifier: list[str] = []
    ignore: list[str] = []
    for column in map(str, metadata.columns):
        if column == sample_id_column:
            continue
        tokens = _tokens(column)
        if column.lower() in ID_WORDS or tokens == {"subject", "id"}:
            identifier.append(column)
        elif tokens & TECHNICAL_WORDS:
            technical.append(column)
        elif tokens & BIOLOGICAL_WORDS:
            biological.append(column)
        else:
            ignore.append(column)
    return {
        "biological": biological,
        "technical": technical,
        "protected": biological.copy(),
        "identifier": identifier,
        "ignore": ignore,
    }


def inspect_frames(
    metadata: pd.DataFrame,
    matrices: dict[str, pd.DataFrame],
    sample_id_column: str | None = None,
) -> InputInspection:
    if metadata.empty:
        raise ValueError("metadata has no rows")
    if not matrices:
        raise ValueError("at least one measurement matrix is required")
    metadata.columns = metadata.columns.astype(str)
    matrix_frames = {name: frame.rename(columns=str) for name, frame in matrices.items()}
    sample_id = sample_id_column or infer_sample_id(metadata, matrix_frames)
    if sample_id not in metadata:
        raise ValueError(f"metadata sample-ID column {sample_id!r} does not exist")
    if metadata[sample_id].isna().any() or metadata[sample_id].astype(str).duplicated().any():
        raise ValueError("metadata sample IDs must be present and unique")
    metadata_ids = set(metadata[sample_id].astype(str))
    inspected: list[MatrixInspection] = []
    warnings: list[str] = []
    for name, frame in matrix_frames.items():
        if frame.empty or len(frame.columns) < 2:
            raise ValueError(f"{name}: matrix must contain an identifier and at least one feature")
        first_column = str(frame.columns[0])
        row_ids = set(frame.iloc[:, 0].dropna().astype(str))
        column_ids = set(map(str, frame.columns[1:]))
        row_overlap = len(metadata_ids & row_ids) / max(1, len(metadata_ids))
        column_overlap = len(metadata_ids & column_ids) / max(1, len(metadata_ids))
        orientation: Orientation = (
            "samples_by_features" if row_overlap >= column_overlap else "features_by_samples"
        )
        matrix_ids = row_ids if orientation == "samples_by_features" else column_ids
        values = (
            frame.iloc[:, 1:]
            if orientation == "samples_by_features"
            else frame.set_index(first_column)
        )
        numeric = values.apply(pd.to_numeric, errors="coerce")
        numeric_fraction = float(numeric.notna().sum().sum() / max(1, values.size))
        item_warnings: list[str] = []
        if max(row_overlap, column_overlap) < 0.5:
            item_warnings.append("Fewer than half of metadata sample IDs overlap this matrix.")
        if numeric_fraction < 0.95:
            item_warnings.append("Some measurement cells are non-numeric and require review.")
        inspected.append(
            MatrixInspection(
                name=name,
                orientation=orientation,
                matrix_sample_id_column=first_column if orientation == "samples_by_features" else None,
                sample_count=len(matrix_ids),
                feature_count=(len(frame.columns) - 1 if orientation == "samples_by_features" else len(frame)),
                matched_samples=len(metadata_ids & matrix_ids),
                metadata_only_samples=len(metadata_ids - matrix_ids),
                matrix_only_samples=len(matrix_ids - metadata_ids),
                numeric_fraction=numeric_fraction,
                warnings=item_warnings,
            )
        )
    roles = suggest_roles(metadata, sample_id)
    if not roles["biological"]:
        warnings.append("No biological variable was inferred; choose at least one variable to preserve.")
    if not roles["technical"]:
        warnings.append("No technical variable was inferred; choose at least one variable to investigate.")
    return InputInspection(
        metadata_sample_id_column=sample_id,
        metadata_rows=len(metadata),
        metadata_columns=list(metadata.columns),
        matrices=inspected,
        suggested_biological=roles["biological"],
        suggested_technical=roles["technical"],
        suggested_protected=roles["protected"],
        suggested_identifier=roles["identifier"],
        suggested_ignore=roles["ignore"],
        warnings=warnings,
    )


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return cleaned or "artifactor-project"


def infer_modality_kind(name: str) -> ModalityKind:
    lowered = name.lower()
    if any(token in lowered for token in ("rna", "transcript", "expression")):
        return "rna_continuous"
    if any(token in lowered for token in ("protein", "proteom")):
        return "proteomics_continuous"
    if any(token in lowered for token in ("genomic", "methyl", "copy_number")):
        return "genomic_continuous"
    return "generic_continuous"


def create_project_from_frames(
    project_dir: Path,
    project_name: str,
    metadata: pd.DataFrame,
    matrices: dict[str, pd.DataFrame],
    sample_id_column: str | None = None,
    biological: list[str] | None = None,
    technical: list[str] | None = None,
    protected: list[str] | None = None,
    identifier: list[str] | None = None,
    kinds: dict[str, ModalityKind] | None = None,
    budget: Literal["quick", "standard", "full"] = "quick",
) -> Path:
    if project_dir.exists() and any(project_dir.iterdir()):
        raise ValueError(f"project directory is not empty: {project_dir}")
    inspection = inspect_frames(metadata.copy(), matrices, sample_id_column)
    roles = suggest_roles(metadata, inspection.metadata_sample_id_column)
    selected_biological = list(biological if biological is not None else roles["biological"])
    selected_technical = list(technical if technical is not None else roles["technical"])
    selected_protected = list(protected if protected is not None else selected_biological)
    selected_identifier = list(identifier if identifier is not None else roles["identifier"])
    available = set(map(str, metadata.columns)) - {inspection.metadata_sample_id_column}
    declared = set(
        selected_biological + selected_technical + selected_protected + selected_identifier
    )
    if not declared <= available:
        raise ValueError(f"unknown metadata role columns: {sorted(declared - available)}")
    if set(selected_biological) & set(selected_technical):
        raise ValueError("a variable cannot be both biological and technical")
    if set(selected_identifier) & set(selected_biological + selected_technical):
        raise ValueError("identifier columns cannot also be biological or technical variables")
    project_dir.mkdir(parents=True, exist_ok=True)
    input_dir = project_dir / "inputs"
    input_dir.mkdir()
    normalized_metadata = metadata.copy().rename(
        columns={inspection.metadata_sample_id_column: "sample_id"}
    )
    normalized_metadata["sample_id"] = normalized_metadata["sample_id"].astype(str)
    normalized_metadata.to_parquet(input_dir / "metadata.parquet", index=False)
    modality_configs: list[dict[str, object]] = []
    setup_matrices: list[dict[str, object]] = []
    used_names: set[str] = set()
    by_name = {item.name: item for item in inspection.matrices}
    for position, (source_name, frame) in enumerate(matrices.items(), start=1):
        modality_name = _safe_name(Path(source_name).stem)
        if modality_name in used_names:
            modality_name = f"{modality_name}-{position}"
        used_names.add(modality_name)
        detail = by_name[source_name]
        normalized = frame.copy()
        if detail.orientation == "samples_by_features":
            if detail.matrix_sample_id_column is None:
                raise ValueError(f"{source_name}: matrix sample-ID column is unresolved")
            normalized = normalized.rename(columns={detail.matrix_sample_id_column: "sample_id"})
            normalized["sample_id"] = normalized["sample_id"].astype(str)
        destination = input_dir / f"{modality_name}.parquet"
        normalized.to_parquet(destination, index=False)
        kind = (kinds or {}).get(source_name, infer_modality_kind(source_name))
        modality_configs.append(
            {
                "name": modality_name,
                "kind": kind,
                "path": f"inputs/{destination.name}",
                "orientation": detail.orientation,
                "transform": "none",
            }
        )
        setup_matrices.append(
            {
                "source_name": source_name,
                "normalized_path": str(destination.relative_to(project_dir)),
                **detail.model_dump(mode="json"),
                "kind": kind,
            }
        )
    ignored = sorted(
        available
        - set(selected_biological)
        - set(selected_technical)
        - set(selected_identifier)
    )
    config = {
        "project": {
            "name": _safe_name(project_name),
            "output_dir": "results",
            "random_seed": 20260807,
        },
        "manifest": {"path": "inputs/metadata.parquet", "sample_id_column": "sample_id"},
        "variables": {
            "biological": selected_biological,
            "technical": selected_technical,
            "protected": selected_protected,
            "identifier": selected_identifier,
            "ignore": ignored,
            "controls": [],
        },
        "modalities": modality_configs,
        "analysis": {"analysis_budget": budget},
        "corrections": {
            "methods": ["none", "residualize", "combat"],
            "refuse_if_rank_deficient": True,
            "maximum_confounding_score": 0.85,
        },
        "report": {
            "title": f"Artifactor — {project_name}",
            "include_interactive_plots": True,
        },
    }
    config_path = project_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    write_json(
        {
            "schema_version": "4.1",
            "project_name": project_name,
            "created_by": "artifactor_onboarding",
            "role_suggestions_require_human_confirmation": biological is None or technical is None,
            "metadata_original_sample_id_column": inspection.metadata_sample_id_column,
            "matrices": setup_matrices,
            "selected_roles": config["variables"],
            "input_inspection": inspection.model_dump(mode="json"),
        },
        project_dir / "project_setup.json",
    )
    preflight_project(config_path)
    return config_path


def initialize_project(
    project_dir: Path,
    project_name: str,
    metadata_path: Path,
    matrix_paths: list[Path],
    sample_id_column: str | None = None,
    biological: list[str] | None = None,
    technical: list[str] | None = None,
    protected: list[str] | None = None,
    identifier: list[str] | None = None,
    kinds: dict[str, ModalityKind] | None = None,
    budget: Literal["quick", "standard", "full"] = "quick",
) -> Path:
    metadata = read_table(metadata_path)
    matrices = {path.name: read_table(path) for path in matrix_paths}
    return create_project_from_frames(
        project_dir,
        project_name,
        metadata,
        matrices,
        sample_id_column,
        biological,
        technical,
        protected,
        identifier,
        kinds,
        budget,
    )


def preflight_project(config_path: Path) -> dict[str, object]:
    config = load_config(config_path)
    validation, metadata, _ = validate_inputs(config)
    result: dict[str, object] = {
        "schema_version": "4.1",
        "valid": validation.valid,
        "sample_count": validation.sample_count,
        "modality_samples": validation.modality_samples,
        "issues": [item.model_dump(mode="json") for item in validation.issues],
        "design_status": "not_evaluated",
        "correction_eligible": False,
        "design_reason": "Input validation must pass first.",
    }
    if validation.valid and metadata is not None:
        pairs, eligibility, diagnostics = audit_design(metadata, config)
        flagged = (
            pairs[pairs["identifiability_status"] != "separable"].to_dict("records")
            if not pairs.empty
            else []
        )
        if eligibility.reasons:
            design_reason = "; ".join(eligibility.reasons)
        elif flagged:
            labels = ", ".join(
                f"{item['biological_variable']} vs {item['technical_variable']} "
                f"({item['identifiability_status']})"
                for item in flagged
            )
            design_reason = (
                "Correction remains eligible, but review limited biological/technical overlap: "
                + labels
            )
        else:
            design_reason = "Biological and technical variables are sufficiently separable."
        result.update(
            {
                "design_status": eligibility.status,
                "correction_eligible": eligibility.eligible,
                "design_reason": design_reason,
                "design_diagnostics": diagnostics,
                "flagged_variable_pairs": flagged,
            }
        )
        if not config.variables.biological or not config.variables.technical:
            result["issues"] = [
                *result["issues"],  # type: ignore[misc]
                {
                    "level": "warning",
                    "code": "roles_incomplete",
                    "message": "Choose at least one biological and one technical variable for a useful artifact analysis.",
                    "remediation": "Edit variable roles in config.yaml or recreate the project in the guided setup.",
                },
            ]
    write_json(result, config_path.parent / "preflight.json")
    return result
