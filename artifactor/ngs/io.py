# mypy: ignore-errors
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from artifactor.config import ArtifactorConfig, ModalityConfig
from artifactor.contracts import (
    KnownTruthRow,
    NGSValidationSummary,
    SampleQCRow,
    TargetAnnotationRow,
    TargetCoverageRow,
    ValidationIssue,
    ValidationResult,
    VariantAlleleCountRow,
    VariantAnnotationRow,
)
from artifactor.io import checksum, read_table


@dataclass(frozen=True)
class NGSInputs:
    manifest: pd.DataFrame
    sample_qc: pd.DataFrame
    coverage: pd.DataFrame
    target_annotations: pd.DataFrame
    allele_counts: pd.DataFrame
    variant_annotations: pd.DataFrame
    known_truth: pd.DataFrame | None
    common_targets: pd.DataFrame
    summary: NGSValidationSummary
    original_checksums: dict[str, str]


def _spec(config: ArtifactorConfig, kind: str) -> ModalityConfig:
    matches = [item for item in config.modalities if item.kind == kind]
    if len(matches) != 1:
        raise ValueError(f"targeted-NGS analysis requires exactly one {kind} modality")
    return matches[0]


def _require(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def _integer_nonnegative(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    for column in columns:
        if column not in frame:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        supplied = frame[column].notna()
        if (
            values[supplied].isna().any()
            or (values[supplied] < 0).any()
            or not np.allclose(values[supplied], np.floor(values[supplied]))
        ):
            raise ValueError(f"{label}.{column} must contain non-negative integers")


def _unique(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    if frame.duplicated(columns).any():
        examples = (
            frame.loc[frame.duplicated(columns, keep=False), columns].head(3).to_dict("records")
        )
        raise ValueError(f"{label} contains duplicate {columns} rows: {examples}")


def _validate_rows(frame: pd.DataFrame, model: type, label: str, limit: int | None = None) -> None:
    records = (
        frame.head(limit).replace({np.nan: None}).to_dict("records")
        if limit
        else frame.replace({np.nan: None}).to_dict("records")
    )
    for index, row in enumerate(records):
        try:
            model.model_validate(row)
        except Exception as exc:
            raise ValueError(f"{label} row {index} failed schema validation: {exc}") from exc


def load_and_validate_ngs(config: ArtifactorConfig) -> NGSInputs:
    if config.ngs is None:
        raise ValueError("targeted-NGS analysis requires an ngs configuration section")
    from artifactor.modalities import capability_issues

    capability_errors = [issue for issue in capability_issues(config) if issue.level == "error"]
    if capability_errors:
        raise ValueError("; ".join(issue.message for issue in capability_errors))
    coverage_spec = _spec(config, "targeted_ngs_coverage")
    allele_spec = _spec(config, "targeted_ngs_allele_counts")
    paths = {
        "manifest": config.manifest.path,
        "coverage": coverage_spec.path,
        "target_annotations": coverage_spec.annotations,
        "sample_qc": coverage_spec.sample_qc,
        "allele_counts": allele_spec.path,
        "variant_annotations": allele_spec.annotations,
    }
    if allele_spec.truth:
        paths["known_truth"] = allele_spec.truth
    if any(path is None for path in paths.values()):
        raise ValueError("all targeted-NGS table paths must be configured")
    original_checksums = {name: checksum(path) for name, path in paths.items() if path is not None}
    manifest = read_table(config.manifest.path)
    coverage = read_table(coverage_spec.path)
    target_annotations = read_table(coverage_spec.annotations)
    sample_qc = read_table(coverage_spec.sample_qc)
    allele_counts = read_table(allele_spec.path)
    variant_annotations = read_table(allele_spec.annotations)
    known_truth = read_table(allele_spec.truth) if allele_spec.truth else None

    sid = config.manifest.sample_id_column
    _require(manifest, {sid}, "manifest")
    _unique(manifest, [sid], "manifest")
    _require(coverage, {"sample_id", "target_id", "raw_count"}, "coverage")
    _unique(coverage, ["sample_id", "target_id"], "coverage")
    _integer_nonnegative(coverage, ["raw_count", "callable_bases"], "coverage")
    _require(
        target_annotations,
        {
            "target_id",
            "panel_version",
            "chromosome",
            "start",
            "end",
            "target_length",
            "reference_build",
        },
        "target annotations",
    )
    _unique(target_annotations, ["target_id", "panel_version"], "target annotations")
    _require(sample_qc, {"sample_id"}, "sample QC")
    _unique(sample_qc, ["sample_id"], "sample QC")
    _require(allele_counts, {"sample_id", "variant_id", "alt_count"}, "allele counts")
    if "total_depth" not in allele_counts and "ref_count" not in allele_counts:
        raise ValueError("allele counts require total_depth or ref_count")
    if "total_depth" not in allele_counts:
        allele_counts["total_depth"] = allele_counts.ref_count + allele_counts.alt_count
    if "ref_count" not in allele_counts:
        allele_counts["ref_count"] = allele_counts.total_depth - allele_counts.alt_count
    _unique(allele_counts, ["sample_id", "variant_id"], "allele counts")
    _integer_nonnegative(
        allele_counts,
        [
            "ref_count",
            "alt_count",
            "total_depth",
            "ref_forward",
            "ref_reverse",
            "alt_forward",
            "alt_reverse",
            "alt_f1r2",
            "alt_f2r1",
        ],
        "allele counts",
    )
    if (allele_counts.alt_count > allele_counts.total_depth).any() or (
        (allele_counts.ref_count + allele_counts.alt_count) > allele_counts.total_depth
    ).any():
        raise ValueError("allele counts are inconsistent with total_depth")
    for left, right, total, label in (
        ("alt_forward", "alt_reverse", "alt_count", "strand"),
        ("alt_f1r2", "alt_f2r1", "alt_count", "orientation"),
    ):
        if (
            left in allele_counts
            and right in allele_counts
            and (
                (allele_counts[left].fillna(0) + allele_counts[right].fillna(0))
                > allele_counts[total]
            ).any()
        ):
            raise ValueError(f"impossible {label} alternate-count totals")
    _require(
        variant_annotations,
        {
            "variant_id",
            "reference_build",
            "chromosome",
            "position",
            "reference_allele",
            "alternate_allele",
            "variant_class",
        },
        "variant annotations",
    )
    _unique(variant_annotations, ["variant_id"], "variant annotations")

    samples = set(manifest[sid].astype(str))
    unknown_coverage = set(coverage.sample_id.astype(str)) - samples
    unknown_alleles = set(allele_counts.sample_id.astype(str)) - samples
    if unknown_coverage or unknown_alleles:
        raise ValueError(
            f"NGS tables contain sample IDs absent from manifest: {sorted(unknown_coverage | unknown_alleles)[:5]}"
        )
    if set(coverage.target_id.astype(str)) - set(target_annotations.target_id.astype(str)):
        raise ValueError("coverage contains target IDs absent from target annotations")
    if set(allele_counts.variant_id.astype(str)) - set(variant_annotations.variant_id.astype(str)):
        raise ValueError("allele counts contain variant IDs absent from variant annotations")
    builds = set(target_annotations.reference_build.dropna().astype(str)) | set(
        variant_annotations.reference_build.dropna().astype(str)
    )
    if builds != {config.ngs.reference_build}:
        raise ValueError(
            f"reference-build mismatch: configured {config.ngs.reference_build}, observed {sorted(builds)}"
        )
    panel_column = config.ngs.panel_version_column
    if panel_column not in manifest:
        raise ValueError(f"manifest is missing configured panel-version column {panel_column!r}")
    panels = sorted(manifest[panel_column].dropna().astype(str).unique())
    annotation_panels = set(target_annotations.panel_version.astype(str))
    if set(panels) - annotation_panels:
        raise ValueError("manifest panel versions are absent from target annotations")
    common_ids = (
        set.intersection(
            *(
                set(
                    target_annotations.loc[
                        target_annotations.panel_version.astype(str) == panel, "target_id"
                    ].astype(str)
                )
                for panel in panels
            )
        )
        if panels
        else set()
    )
    common_targets = (
        target_annotations[target_annotations.target_id.astype(str).isin(common_ids)]
        .drop_duplicates("target_id")
        .copy()
    )
    common_targets["applicability_status"] = "common_across_panels"
    common_targets["exclusion_reason"] = None

    if known_truth is not None:
        _require(
            known_truth, {"sample_id", "variant_id", "truth_state", "truth_source"}, "known truth"
        )
        _unique(known_truth, ["sample_id", "variant_id", "truth_source"], "known truth")
        if set(known_truth.sample_id.astype(str)) - samples or set(
            known_truth.variant_id.astype(str)
        ) - set(variant_annotations.variant_id.astype(str)):
            raise ValueError("known-truth rows must resolve to valid sample-variant pairs")

    # Full vector checks above protect large tables; Pydantic validates their typed row contracts.
    _validate_rows(sample_qc, SampleQCRow, "sample QC")
    _validate_rows(coverage, TargetCoverageRow, "coverage", limit=1000)
    _validate_rows(target_annotations, TargetAnnotationRow, "target annotations")
    _validate_rows(allele_counts, VariantAlleleCountRow, "allele counts", limit=1000)
    _validate_rows(variant_annotations, VariantAnnotationRow, "variant annotations")
    if known_truth is not None:
        _validate_rows(known_truth, KnownTruthRow, "known truth", limit=1000)

    warnings: list[str] = []
    for column in ("pipeline_version", "reference_build", panel_column):
        if column not in manifest or manifest[column].isna().any():
            message = f"critical upstream provenance {column!r} is incomplete"
            if config.ngs.require_pipeline_version and column == "pipeline_version":
                raise ValueError(message)
            warnings.append(message)
    summary = NGSValidationSummary(
        valid=True,
        status="valid_with_warnings" if warnings else "valid",
        reference_build=config.ngs.reference_build,
        sample_count=len(manifest),
        target_count=target_annotations.target_id.nunique(),
        variant_count=variant_annotations.variant_id.nunique(),
        panel_versions=panels,
        warnings=warnings,
        input_checksums=original_checksums,
        immutable_columns=[
            "raw_count",
            "callable_bases",
            "ref_count",
            "alt_count",
            "total_depth",
            "existing_call_state",
        ],
    )
    return NGSInputs(
        manifest,
        sample_qc,
        coverage,
        target_annotations,
        allele_counts,
        variant_annotations,
        known_truth,
        common_targets,
        summary,
        original_checksums,
    )


def validate_ngs_inputs(config: ArtifactorConfig) -> tuple[ValidationResult, NGSInputs | None]:
    try:
        inputs = load_and_validate_ngs(config)
    except (OSError, ValueError) as exc:
        return ValidationResult(
            valid=False,
            issues=[
                ValidationIssue(
                    level="error",
                    code="invalid_targeted_ngs_input",
                    message=str(exc),
                    remediation="Correct the analysis-ready NGS tables or configuration; original observations were not modified.",
                )
            ],
        ), None
    issues = [
        ValidationIssue(
            level="warning",
            code="ngs_provenance_warning",
            message=warning,
            remediation="Supply complete upstream assay provenance.",
        )
        for warning in inputs.summary.warnings
    ]
    return ValidationResult(valid=True, issues=issues), inputs
