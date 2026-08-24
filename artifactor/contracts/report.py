from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence import EvidenceCard, GroundTruthSummary, MetricDefinition


class StrictReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DesignSummary(StrictReportModel):
    schema_version: str = "2.0"
    overall_status: Literal["separable", "weak_overlap", "highly_confounded", "non_identifiable"]
    correction_permitted: bool
    biological_variables: list[str]
    technical_variables: list[str]
    protected_variables: list[str]
    sample_count: int = Field(ge=0)
    design_rank: int = Field(ge=0)
    design_columns: int = Field(ge=0)
    condition_number: float
    limiting_pairs: list[str]
    summary_text: str


class FactorSummary(StrictReportModel):
    schema_version: str = "2.0"
    modality: str
    factor: str
    variance_explained: float = Field(ge=0)
    classification: Literal["biological", "technical", "mixed", "unexplained"]
    classification_confidence: Literal["low", "moderate", "high"]
    leading_biological_variable: str | None = None
    leading_biological_effect_size: float | None = None
    leading_technical_variable: str | None = None
    leading_technical_effect_size: float | None = None
    stability: float = Field(ge=0, le=1)
    n_samples: int = Field(ge=0)


class ReportSection(StrictReportModel):
    section_id: str
    title: str
    included: bool
    summary: str
    artifact_links: list[str] = Field(default_factory=list)
    omission_reason: str | None = None

    @model_validator(mode="after")
    def omission_is_explained(self) -> ReportSection:
        if not self.included and not self.omission_reason:
            raise ValueError("omitted report sections require an omission reason")
        return self


class ReportModel(StrictReportModel):
    schema_version: str = "2.0"
    project_name: str
    report_title: str
    run_fingerprint: str
    sample_count: int
    modalities: list[str]
    design: DesignSummary
    recommendation_method: str
    recommendation_display_name: str
    recommendation_rationale: str
    research_limitation: str
    metric_registry: dict[str, MetricDefinition]
    factor_highlights: list[FactorSummary]
    evidence_cards: list[EvidenceCard]
    ground_truth: GroundTruthSummary
    sections: list[ReportSection] = Field(min_length=7, max_length=7)
    provenance: dict[str, object]
    analysis_type: Literal["continuous_multiomics", "targeted_ngs"] = "continuous_multiomics"
    ngs_summary: dict[str, object] | None = None


class ReportManifest(StrictReportModel):
    schema_version: str = "2.0"
    generated_at: datetime
    run_fingerprint: str
    source_artifact_checksums: dict[str, str]
    included_sections: list[str]
    omitted_sections: dict[str, str]
    software_version: str
    visualization_sampling_policy: str
