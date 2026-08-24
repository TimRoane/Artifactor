from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "4.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccessLevel(StrEnum):
    OPEN_DIRECT = "open_direct"
    OPEN_REGISTRATION_REQUIRED = "open_registration_required"
    CONTROLLED = "controlled"
    UNAVAILABLE = "unavailable"


class SourceRecord(StrictModel):
    source_name: str
    authoritative_url: str
    accession_or_study_id: str
    file_name: str
    file_role: str
    checksum_algorithm: Literal["md5", "sha256"]
    checksum: str
    size_bytes: int = Field(ge=0)
    tiers: list[Literal["pilot", "full"]]
    resolver: Literal["direct", "pdc_graphql"] = "direct"
    resolver_file_id: str | None = None
    resolver_study_id: str | None = None

    @model_validator(mode="after")
    def resolver_fields(self) -> SourceRecord:
        if self.resolver == "pdc_graphql" and not (
            self.resolver_file_id and self.resolver_study_id
        ):
            raise ValueError("PDC sources require resolver_file_id and resolver_study_id")
        return self


class DatasetEntry(StrictModel):
    dataset_id: str
    display_name: str
    release_or_snapshot: str
    retrieval_date: date
    primary_publication: str
    source_records: list[SourceRecord]
    license_or_terms: str
    redistribution_status: str
    expected_files: list[str]
    expected_checksums: dict[str, str]
    expected_size_bytes: int = Field(ge=0)
    access_level: AccessLevel
    adapter: Literal["seqc2", "cptac_ccrcc"]
    preparation_version: str
    notes: str


class DatasetRegistry(StrictModel):
    schema_version: str = SCHEMA_VERSION
    datasets: list[DatasetEntry]

    @model_validator(mode="after")
    def unique_ids(self) -> DatasetRegistry:
        ids = [item.dataset_id for item in self.datasets]
        if len(ids) != len(set(ids)):
            raise ValueError("dataset_id values must be unique")
        return self


class TransformationRecord(StrictModel):
    schema_version: str = SCHEMA_VERSION
    step_id: str
    input_artifacts: list[str]
    operation: str
    parameters: dict[str, object] = Field(default_factory=dict)
    output_artifacts: list[str]
    rows_in: int = Field(ge=0)
    rows_out: int = Field(ge=0)
    exclusion_reason_counts: dict[str, int] = Field(default_factory=dict)


class PreparationManifest(StrictModel):
    schema_version: str = SCHEMA_VERSION
    dataset_id: str
    source_snapshot: str
    preparation_version: str
    preparation_fingerprint: str
    start_timestamp: datetime
    completion_timestamp: datetime
    source_checksums: dict[str, str]
    code_commit: str | None
    container_digest: str | None
    dependency_versions: dict[str, str]
    parameters: dict[str, object]
    row_counts_before_after: dict[str, dict[str, int]]
    exclusions: list[dict[str, object]]
    warnings: list[str]
    output_checksums: dict[str, str]


class DatasetStatus(StrictModel):
    schema_version: str = SCHEMA_VERSION
    dataset_id: str
    tier: Literal["fixture", "pilot", "full"]
    access_level: AccessLevel
    expected_size_bytes: int
    present_files: list[str]
    missing_files: list[str]
    checksum_mismatches: list[str]
    verified: bool
    prepared_directories: list[str]
