from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MeasurementFamily(StrEnum):
    CONTINUOUS = "continuous"
    COUNT = "count"
    FRACTION = "fraction"
    BINARY = "binary"
    SEGMENT = "segment"
    SPARSE_EVENT = "sparse_event"


class ModalityCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "2.0"
    kind: str
    display_name: str
    measurement_family: MeasurementFamily
    accepted_input_formats: list[str] = Field(min_length=1)
    required_metadata: list[str] = Field(default_factory=list)
    supported_transforms: list[str] = Field(min_length=1)
    supported_diagnostics: list[str] = Field(min_length=1)
    supported_corrections: list[str] = Field(min_length=1)
    supported_representations: list[str] = Field(default_factory=list)
    fit_transform_behavior: str | None = None
    immutable_observations: list[str] = Field(default_factory=list)
    protected_semantics: str
    missingness_semantics: str
    feature_annotation_requirements: list[str] = Field(default_factory=list)
    upstream_provenance_requirements: list[str] = Field(default_factory=list)
