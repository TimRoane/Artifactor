from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "3.0"


class StrictNGSModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SampleQCRow(StrictNGSModel):
    sample_id: str
    total_reads: int | None = Field(default=None, ge=0)
    mapped_reads: int | None = Field(default=None, ge=0)
    usable_fragments: int | None = Field(default=None, ge=0)
    mean_target_depth: float | None = Field(default=None, ge=0)
    median_target_depth: float | None = Field(default=None, ge=0)
    coverage_uniformity: float | None = Field(default=None, ge=0, le=1)
    duplicate_rate: float | None = Field(default=None, ge=0, le=1)
    on_target_rate: float | None = Field(default=None, ge=0, le=1)
    insert_size_median: float | None = Field(default=None, ge=0)
    gc_bias_score: float | None = None
    contamination_estimate: float | None = Field(default=None, ge=0, le=1)
    callable_target_fraction: float | None = Field(default=None, ge=0, le=1)


class TargetCoverageRow(StrictNGSModel):
    sample_id: str
    target_id: str
    raw_count: int = Field(ge=0)
    callable_bases: int | None = Field(default=None, ge=1)
    mean_depth: float | None = Field(default=None, ge=0)
    median_depth: float | None = Field(default=None, ge=0)


class TargetAnnotationRow(StrictNGSModel):
    target_id: str
    panel_version: str
    chromosome: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    gene: str | None = None
    transcript: str | None = None
    exon: str | None = None
    target_length: int = Field(gt=0)
    gc_fraction: float | None = Field(default=None, ge=0, le=1)
    mappability: float | None = Field(default=None, ge=0, le=1)
    expected_copy_number_class: str | None = None
    reference_build: str

    @model_validator(mode="after")
    def coordinates_are_ordered(self) -> TargetAnnotationRow:
        if self.end <= self.start:
            raise ValueError("target annotation end must be greater than start")
        return self


class VariantAlleleCountRow(StrictNGSModel):
    sample_id: str
    variant_id: str
    ref_count: int | None = Field(default=None, ge=0)
    alt_count: int = Field(ge=0)
    total_depth: int | None = Field(default=None, ge=0)
    ref_forward: int | None = Field(default=None, ge=0)
    ref_reverse: int | None = Field(default=None, ge=0)
    alt_forward: int | None = Field(default=None, ge=0)
    alt_reverse: int | None = Field(default=None, ge=0)
    alt_f1r2: int | None = Field(default=None, ge=0)
    alt_f2r1: int | None = Field(default=None, ge=0)
    base_quality_mean: float | None = Field(default=None, ge=0)
    mapping_quality_mean: float | None = Field(default=None, ge=0)
    read_position_mean: float | None = Field(default=None, ge=0, le=1)
    insert_size_mean: float | None = Field(default=None, ge=0)
    existing_call_state: str | None = None

    @model_validator(mode="after")
    def counts_are_consistent(self) -> VariantAlleleCountRow:
        depth = (
            self.total_depth
            if self.total_depth is not None
            else (self.ref_count or 0) + self.alt_count
        )
        if self.alt_count > depth:
            raise ValueError("alt_count cannot exceed total_depth")
        if self.ref_count is not None and self.ref_count + self.alt_count > depth:
            raise ValueError("ref_count + alt_count cannot exceed total_depth")
        if (
            self.alt_forward is not None
            and self.alt_reverse is not None
            and self.alt_forward + self.alt_reverse > self.alt_count
        ):
            raise ValueError("strand-specific alternate counts cannot exceed alt_count")
        if (
            self.alt_f1r2 is not None
            and self.alt_f2r1 is not None
            and self.alt_f1r2 + self.alt_f2r1 > self.alt_count
        ):
            raise ValueError("orientation-specific alternate counts cannot exceed alt_count")
        return self


class VariantAnnotationRow(StrictNGSModel):
    variant_id: str
    reference_build: str
    chromosome: str
    position: int = Field(gt=0)
    reference_allele: str
    alternate_allele: str
    gene: str | None = None
    variant_class: str
    trinucleotide_context: str | None = None
    expected_control_state: str | None = None
    lod_bin: str | None = None


class KnownTruthRow(StrictNGSModel):
    sample_id: str
    variant_id: str
    truth_state: Literal["positive", "negative", "unknown"]
    expected_vaf: float | None = Field(default=None, ge=0, le=1)
    truth_source: Literal[
        "simulator", "reference_material", "orthogonal_confirmation", "declared_comparator"
    ]
    confidence_region: str | None = None


class NGSValidationSummary(StrictNGSModel):
    schema_version: str = SCHEMA_VERSION
    valid: bool
    status: Literal["valid", "invalid", "valid_with_warnings"]
    reference_build: str
    sample_count: int = Field(ge=0)
    target_count: int = Field(ge=0)
    variant_count: int = Field(ge=0)
    panel_versions: list[str]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    input_checksums: dict[str, str]
    immutable_columns: list[str]
