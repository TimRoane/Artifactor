from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "2.0"


class StrictEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MetricDefinition(StrictEvidenceModel):
    metric_id: str
    display_name: str
    short_definition: str
    long_definition: str
    direction: Literal["higher", "lower", "unchanged", "contextual"]
    range: str
    baseline_interpretation: str
    limitations: list[str] = Field(min_length=1)
    aggregation_method: str


class EvidenceReference(StrictEvidenceModel):
    label: str
    value: float | int | str | bool | None = None
    artifact: str
    row_filter: dict[str, str | int | float | bool] = Field(default_factory=dict)


class FollowUpRecommendation(StrictEvidenceModel):
    experiment: str
    samples: str
    variable_to_balance: str
    controls: list[str] = Field(min_length=1)
    blinded: bool
    expected_comparison: str
    supporting_outcome: str
    weakening_outcome: str


class EvidenceCard(StrictEvidenceModel):
    finding_id: str
    priority: int = Field(ge=1)
    severity: Literal["info", "warning", "high"]
    classification: Literal["design", "biological", "technical", "mixed", "unexplained", "decision"]
    title: str
    observation: str
    supporting_evidence: list[EvidenceReference] = Field(min_length=1)
    alternative_explanations: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    recommended_follow_ups: list[FollowUpRecommendation] = Field(min_length=1)
    related_modalities: list[str] = Field(default_factory=list)
    related_factors: list[str] = Field(default_factory=list)
    related_variables: list[str] = Field(default_factory=list)
    artifact_links: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def prohibit_causal_language(self) -> EvidenceCard:
        text = " ".join(
            [self.title, self.observation, *self.alternative_explanations, *self.limitations]
        ).lower()
        prohibited = (
            "caused by",
            " proves ",
            "eliminated all batch effects",
            "preserved all biology",
        )
        if any(phrase in f" {text} " for phrase in prohibited):
            raise ValueError("observational evidence cards must not use prohibited causal language")
        return self


class GroundTruthSummary(StrictEvidenceModel):
    schema_version: str = SCHEMA_VERSION
    supplied: bool
    synthetic_only: bool = True
    biological_precision: float | None = None
    biological_recall: float | None = None
    biological_f1: float | None = None
    technical_precision: float | None = None
    technical_recall: float | None = None
    technical_f1: float | None = None
    false_positive_rate_null: float | None = None
    effect_rmse: float | None = None
    technical_effect_correlation: float | None = None
    classification_threshold: float | None = None
    by_modality: list[dict[str, str | float | int | None]] = Field(default_factory=list)
    omission_reason: str | None = None


class GroundTruthRow(StrictEvidenceModel):
    schema_version: str = SCHEMA_VERSION
    scenario: str
    modality: str
    feature_id: str
    is_biological: bool
    is_technical: bool
    is_mixed: bool
    is_null: bool
    biological_effect_type: str | None = None
    biological_effect_size: float = 0.0
    technical_effect_type: str | None = None
    technical_effect_size: float = 0.0
    technical_variable: str | None = None
    mapped_feature_id: str | None = None

    @model_validator(mode="after")
    def exactly_one_class(self) -> GroundTruthRow:
        if sum((self.is_biological, self.is_technical, self.is_mixed, self.is_null)) != 1:
            raise ValueError("ground-truth classification flags must be mutually exclusive")
        return self
