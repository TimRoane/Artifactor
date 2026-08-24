from __future__ import annotations

from artifactor.config import ArtifactorConfig
from artifactor.contracts import MeasurementFamily, ModalityCapability, ValidationIssue

_DIAGNOSTICS = [
    "missingness",
    "outliers",
    "robust_pca",
    "metadata_association",
    "variance_attribution",
]
_CONTINUOUS_CORRECTIONS = ["none", "residualize", "combat"]


def _capability(
    kind: str,
    display: str,
    family: MeasurementFamily,
    corrections: list[str],
    transforms: list[str],
    representations: list[str] | None = None,
    immutable: list[str] | None = None,
) -> ModalityCapability:
    return ModalityCapability(
        kind=kind,
        display_name=display,
        measurement_family=family,
        accepted_input_formats=["parquet", "csv", "tsv"],
        supported_transforms=transforms,
        supported_diagnostics=_DIAGNOSTICS
        if family
        in {MeasurementFamily.CONTINUOUS, MeasurementFamily.COUNT, MeasurementFamily.FRACTION}
        else ["missingness", "descriptive_summary"],
        supported_corrections=corrections,
        supported_representations=representations or [],
        fit_transform_behavior="Training-fitted parameters are persisted and applied without using held-out outcomes."
        if representations
        else None,
        immutable_observations=immutable or [],
        protected_semantics="Declared protected variables may represent real biology and are never removed implicitly.",
        missingness_semantics="Missing values remain missing in saved corrected representations.",
        upstream_provenance_requirements=["assay_version", "processing_pipeline_version"]
        if "genomic" in kind or family != MeasurementFamily.CONTINUOUS
        else [],
    )


CAPABILITIES: dict[str, ModalityCapability] = {
    "rna_continuous": _capability(
        "rna_continuous",
        "Continuous RNA expression",
        MeasurementFamily.CONTINUOUS,
        _CONTINUOUS_CORRECTIONS,
        ["none", "log1p"],
    ),
    "proteomics_continuous": _capability(
        "proteomics_continuous",
        "Continuous protein abundance",
        MeasurementFamily.CONTINUOUS,
        _CONTINUOUS_CORRECTIONS,
        ["none", "log1p"],
    ),
    "generic_continuous": _capability(
        "generic_continuous",
        "Generic continuous measurements",
        MeasurementFamily.CONTINUOUS,
        _CONTINUOUS_CORRECTIONS,
        ["none", "log1p"],
    ),
    "genomic_continuous": _capability(
        "genomic_continuous",
        "Generic continuous genomic summary",
        MeasurementFamily.CONTINUOUS,
        _CONTINUOUS_CORRECTIONS,
        ["none", "log1p"],
    ),
    "rna_counts": _capability(
        "rna_counts", "RNA count matrix", MeasurementFamily.COUNT, ["none"], ["log1p"]
    ),
    "count_matrix": _capability(
        "count_matrix", "Generic count matrix", MeasurementFamily.COUNT, ["none"], ["log1p"]
    ),
    "fraction_matrix": _capability(
        "fraction_matrix", "Fraction measurements", MeasurementFamily.FRACTION, ["none"], ["none"]
    ),
    "variant_binary": _capability(
        "variant_binary", "Binary variant calls", MeasurementFamily.BINARY, ["none"], ["none"]
    ),
    "segment_matrix": _capability(
        "segment_matrix", "Segment measurements", MeasurementFamily.SEGMENT, ["none"], ["none"]
    ),
    "sparse_event": _capability(
        "sparse_event",
        "Sparse event measurements",
        MeasurementFamily.SPARSE_EVENT,
        ["none"],
        ["none"],
    ),
    "targeted_ngs_coverage": ModalityCapability(
        kind="targeted_ngs_coverage",
        display_name="Targeted-NGS target coverage counts",
        measurement_family=MeasurementFamily.COUNT,
        accepted_input_formats=["parquet", "csv", "tsv"],
        required_metadata=["reference_build", "panel_version", "pipeline_version"],
        supported_transforms=["none"],
        supported_diagnostics=[
            "sample_qc",
            "callability",
            "count_aware_factors",
            "target_attribution",
            "gc_behavior",
        ],
        supported_corrections=["none"],
        supported_representations=[
            "raw_offset",
            "median_ratio",
            "gc_normalized",
            "nb_technical_residual",
        ],
        fit_transform_behavior="Count-aware exploratory representations use exposure/length offsets and a documented fixed-representation evaluation; grouped prediction preprocessing is resampled and raw counts are never overwritten.",
        immutable_observations=["raw_count", "callable_bases"],
        protected_semantics="Declared biological and protected terms remain in count-model expectations and are never removed implicitly.",
        missingness_semantics="A missing sample-target row is not assayed or unavailable; it is never converted to a zero count.",
        feature_annotation_requirements=[
            "target_id",
            "panel_version",
            "target_length",
            "reference_build",
        ],
        upstream_provenance_requirements=["reference_build", "panel_version", "pipeline_version"],
    ),
    "targeted_ngs_allele_counts": ModalityCapability(
        kind="targeted_ngs_allele_counts",
        display_name="Targeted-NGS allele-supporting counts",
        measurement_family=MeasurementFamily.FRACTION,
        accepted_input_formats=["parquet", "csv", "tsv"],
        required_metadata=["reference_build", "panel_version", "pipeline_version"],
        supported_transforms=["none"],
        supported_diagnostics=[
            "depth_callability",
            "beta_binomial_association",
            "sequence_context",
            "strand_bias",
            "orientation_bias",
            "truth_control_recovery",
        ],
        supported_corrections=["none"],
        supported_representations=["observed_counts", "model_expected_alt_fraction"],
        fit_transform_behavior="Modeled expected allele fractions are separate diagnostic outputs; observations and call states are immutable.",
        immutable_observations=["ref_count", "alt_count", "total_depth", "existing_call_state"],
        protected_semantics="Biological, control-truth, ancestry, purity, and other protected terms are retained in allele-count models.",
        missingness_semantics="Insufficient depth and unassayed loci are distinct from observed zero alternate support.",
        feature_annotation_requirements=[
            "variant_id",
            "reference_build",
            "reference_allele",
            "alternate_allele",
        ],
        upstream_provenance_requirements=[
            "reference_build",
            "panel_version",
            "pipeline_version",
            "variant_caller_version",
        ],
    ),
}


def capability_for(kind: str) -> ModalityCapability:
    try:
        return CAPABILITIES[kind]
    except KeyError as exc:
        raise ValueError(
            f"unknown modality kind {kind!r}; run `artifactor capabilities` for supported kinds"
        ) from exc


def capability_issues(config: ArtifactorConfig) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    requested = set(config.corrections.methods)
    for modality in config.modalities:
        suffix = modality.path.suffix.lower()
        if suffix in {".fastq", ".fq", ".bam", ".cram", ".vcf", ".bcf", ".gz"}:
            issues.append(
                ValidationIssue(
                    level="error",
                    code="unsupported_genomic_input",
                    message=f"{modality.name} uses {suffix}. Artifactor v0.3.0 accepts analysis-ready tables, not FASTQ, BAM, CRAM, or VCF inputs.",
                    remediation="Create a supported analysis-ready summary matrix or use an upstream genomics pipeline.",
                )
            )
            continue
        capability = capability_for(modality.kind)
        invalid = sorted(requested - set(capability.supported_corrections))
        if invalid:
            issues.append(
                ValidationIssue(
                    level="error",
                    code="unsupported_modality_correction",
                    message=f"{modality.name} uses {capability.measurement_family.value} measurements. Continuous {', '.join(invalid)} correction is not valid for this modality.",
                    remediation="Use diagnostic-only analysis with corrections.methods: [none], or install a future measurement-family-aware plugin.",
                )
            )
    return issues


def capability_rows(modality: str | None = None) -> list[dict[str, object]]:
    selected = [capability_for(modality)] if modality else list(CAPABILITIES.values())
    return [item.model_dump(mode="json") for item in selected]
