# mypy: ignore-errors
from __future__ import annotations

import re

import pandas as pd

from artifactor.config import ArtifactorConfig
from artifactor.contracts import (
    DesignSummary,
    EvidenceCard,
    EvidenceReference,
    FollowUpRecommendation,
)


def _follow_up(variable: str, classification: str) -> FollowUpRecommendation:
    lower = variable.lower()
    if "rin" in lower or "dv200" in lower:
        experiment = "RNA-quality bridge experiment"
        controls = ["matched high- and low-quality aliquots", "extraction control"]
    elif "plate" in lower or "order" in lower:
        experiment = "Randomized plate-position and run-order repeat"
        controls = ["edge and center controls", "bridge samples on every plate"]
    elif "instrument" in lower or "operator" in lower:
        experiment = "Blinded cross-operator or cross-instrument repeat"
        controls = ["shared reference material", "technical replicates"]
    elif classification == "design":
        experiment = "Balanced cross-batch reprocessing study"
        controls = ["bridge samples from each biological group", "shared reference control"]
    else:
        experiment = "Blinded cross-batch reprocessing experiment"
        controls = ["technical replicates", "bridge samples across processing levels"]
    return FollowUpRecommendation(
        experiment=experiment,
        samples="Select representative samples spanning biological groups and the implicated technical levels.",
        variable_to_balance=variable,
        controls=controls,
        blinded=True,
        expected_comparison="Compare the same biological groups after balanced assignment across technical levels.",
        supporting_outcome="The signature follows the technical level after biological balance is restored.",
        weakening_outcome="The signature remains tied to biology and does not reproduce across the technical contrast.",
    )


def build_evidence_cards(
    design: DesignSummary,
    factor_summary: pd.DataFrame,
    recommendation: dict[str, object],
    config: ArtifactorConfig,
) -> list[EvidenceCard]:
    cards: list[EvidenceCard] = []
    if not design.correction_permitted:
        variable = (
            config.variables.technical[0] if config.variables.technical else "processing_batch"
        )
        cards.append(
            EvidenceCard(
                finding_id="design-non-identifiable",
                priority=1,
                severity="high",
                classification="design",
                title="Protected biology and technical handling are not independently identifiable",
                observation=design.summary_text,
                supporting_evidence=[
                    EvidenceReference(
                        label="Design status",
                        value=design.overall_status,
                        artifact="design/design_summary.json",
                    )
                ],
                alternative_explanations=[
                    "The observed separation may reflect biology, handling, or their alignment."
                ],
                limitations=[
                    "This cohort does not contain the independent support needed to estimate both effects."
                ],
                recommended_follow_ups=[_follow_up(variable, "design")],
                related_variables=[*config.variables.biological, *config.variables.technical],
                artifact_links=[
                    "design/pairwise_identifiability.parquet",
                    "design/contingency_cells.parquet",
                ],
            )
        )
    candidates = factor_summary[
        (factor_summary.classification.isin(["technical", "mixed"]))
        & (factor_summary.classification_confidence != "low")
    ].sort_values(
        ["classification_confidence", "leading_technical_effect_size"], ascending=[True, False]
    )
    for index, row in enumerate(candidates.head(4).itertuples(), start=len(cards) + 1):
        variable = str(row.leading_technical_variable or "technical metadata")
        if variable.lower() in {"rin", "dv200"} and str(row.modality) == "protein":
            observation = f"Protein {row.factor} is associated with {variable}; this may proxy broader specimen quality or correlated handling rather than a direct protein effect."
            alternatives = [
                "Correlated extraction handling",
                "Shared specimen degradation",
                "Cohort allocation imbalance",
            ]
        else:
            observation = f"{row.modality} {row.factor} is associated with {variable} and is classified as {row.classification}."
            alternatives = [
                "Correlated technical metadata",
                "Unmeasured cohort allocation",
                "A biological variable correlated with processing",
            ]
        cards.append(
            EvidenceCard(
                finding_id=f"factor-{str(row.modality).lower()}-{str(row.factor).lower()}",
                priority=index,
                severity="warning" if row.classification == "technical" else "high",
                classification=str(row.classification),
                title=f"{variable} signature in {row.modality} {row.factor}",
                observation=observation,
                supporting_evidence=[
                    EvidenceReference(
                        label="Technical association effect size",
                        value=float(row.leading_technical_effect_size),
                        artifact="factors/factor_summary.parquet",
                        row_filter={"modality": str(row.modality), "factor": str(row.factor)},
                    ),
                    EvidenceReference(
                        label="Factor stability",
                        value=float(row.stability),
                        artifact="factors/factor_summary.parquet",
                        row_filter={"modality": str(row.modality), "factor": str(row.factor)},
                    ),
                ],
                alternative_explanations=alternatives,
                limitations=[
                    "Latent-factor association does not establish assay root cause.",
                    "Only declared metadata can be evaluated.",
                ],
                recommended_follow_ups=[_follow_up(variable, str(row.classification))],
                related_modalities=[str(row.modality)],
                related_factors=[str(row.factor)],
                related_variables=[variable],
                artifact_links=[
                    "factors/factor_summary.parquet",
                    "factors/factor_metadata_associations.parquet",
                    "factors/factor_loadings.parquet",
                ],
            )
        )
    method = str(recommendation.get("method", "none"))
    cards.append(
        EvidenceCard(
            finding_id="correction-decision",
            priority=len(cards) + 1,
            severity="info" if method != "none" else "warning",
            classification="decision",
            title="Correction decision",
            observation=str(
                recommendation.get("rationale", "No recommendation rationale was recorded.")
            ),
            supporting_evidence=[
                EvidenceReference(
                    label="Selected method",
                    value=method,
                    artifact="interpretation/recommendation.json",
                )
            ],
            alternative_explanations=[
                "Alternative eligible methods may have similar performance within uncertainty."
            ],
            limitations=[
                "Preservation is assessed only for declared variables and supplied feature mappings."
            ],
            recommended_follow_ups=[
                _follow_up(
                    config.variables.technical[0]
                    if config.variables.technical
                    else "technical variable",
                    "decision",
                )
            ],
            related_variables=[*config.variables.biological, *config.variables.technical],
            artifact_links=[
                "corrections/method_eligibility.parquet",
                "corrections/correction_metrics.parquet",
                "interpretation/recommendation.json",
            ],
        )
    )
    for card in cards:
        if re.search(
            r"\b(caused by|proves|eliminated all batch effects|preserved all biology)\b",
            card.observation.lower(),
        ):
            raise ValueError("prohibited causal language in evidence card")
    return cards
