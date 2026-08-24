from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResultStatus(StrEnum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    NOT_EVALUABLE = "not_evaluable"


class EvidenceLevel(StrEnum):
    SYNTHETIC_GROUND_TRUTH = "synthetic_ground_truth"
    REFERENCE_TRUTH = "reference_truth"
    TECHNICAL_REPLICATION = "technical_replication"
    PUBLISHED_DIRECTIONAL_COMPARISON = "published_directional_comparison"
    OBSERVATIONAL_ASSOCIATION = "observational_association"


class ConclusionStatus(StrEnum):
    VALIDATED = "validated_for_declared_scope"
    PARTIAL = "partially_validated"
    FAILED = "failed_validation"
    INSUFFICIENT = "insufficient_public_evidence"


class ValidationQuestion(StrictModel):
    schema_version: str = "4.0"
    question_id: str
    dataset_id: str
    title: str
    hypothesis: str
    analysis_population: str
    primary_metrics: list[str]
    secondary_metrics: list[str] = Field(default_factory=list)
    acceptance_rule: str
    non_evaluable_rule: str
    evidence_level: EvidenceLevel
    result_status: ResultStatus | None = None
    result_summary: str | None = None
    supporting_artifacts: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Deviation(StrictModel):
    schema_version: str = "4.0"
    deviation_id: str
    timestamp: datetime
    trigger: str
    original_plan: str
    changed_plan: str
    reason: str
    affected_questions: list[str]
    whether_results_were_viewed: bool
    approval_or_review_status: str


class CaseStudyConclusion(StrictModel):
    schema_version: str = "4.0"
    dataset_id: str
    status: ConclusionStatus
    status_reason: str
    question_counts: dict[str, int]
    correction_eligible: bool
    correction_reason: str
    limitations: list[str]


def derive_conclusion(dataset_id: str, questions: list[ValidationQuestion], correction_eligible: bool, correction_reason: str) -> CaseStudyConclusion:
    counts = {status.value: sum(item.result_status == status for item in questions) for status in ResultStatus}
    evaluable = len(questions) - counts[ResultStatus.NOT_EVALUABLE.value]
    if counts[ResultStatus.FAIL.value]:
        status = ConclusionStatus.FAILED
    elif evaluable == 0:
        status = ConclusionStatus.INSUFFICIENT
    elif counts[ResultStatus.PARTIAL.value] or counts[ResultStatus.NOT_EVALUABLE.value]:
        status = ConclusionStatus.PARTIAL
    else:
        status = ConclusionStatus.VALIDATED
    return CaseStudyConclusion(dataset_id=dataset_id, status=status, status_reason="Derived mechanically from preregistered question statuses; presentation cannot upgrade it.", question_counts=counts, correction_eligible=correction_eligible, correction_reason=correction_reason, limitations=sorted({limitation for item in questions for limitation in item.limitations}))
