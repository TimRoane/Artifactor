from __future__ import annotations

import pandas as pd

from artifactor.config import ArtifactorConfig
from artifactor.contracts import (
    DesignSummary,
    EvidenceCard,
    EvidenceReference,
    FollowUpRecommendation,
)


def _follow_up(
    experiment: str, variable: str, controls: list[str], supporting: str, weakening: str
) -> FollowUpRecommendation:
    return FollowUpRecommendation(
        experiment=experiment,
        samples="Use representative specimens spanning protected biological groups and implicated technical levels.",
        variable_to_balance=variable,
        controls=controls,
        blinded=True,
        expected_comparison="Compare matched or bridge material across the implicated technical contrast with depth and callability balanced.",
        supporting_outcome=supporting,
        weakening_outcome=weakening,
    )


def build_ngs_evidence_cards(
    design: DesignSummary,
    factor_associations: pd.DataFrame,
    model_results: pd.DataFrame,
    ffpe_evidence: pd.DataFrame,
    opportunity: pd.DataFrame,
    recommendation: dict[str, object],
    config: ArtifactorConfig,
) -> list[EvidenceCard]:
    cards: list[EvidenceCard] = []
    if not design.correction_permitted:
        variable = config.ngs.panel_version_column if config.ngs else "panel_version"
        cards.append(
            EvidenceCard(
                finding_id="ngs-design-refusal",
                priority=1,
                severity="high",
                classification="design",
                title="Targeted-NGS mitigation is refused by the study design",
                observation=design.summary_text
                + " Structural target differences and insufficient detection opportunity cannot be normalized away.",
                supporting_evidence=[
                    EvidenceReference(
                        label="Design status",
                        value=design.overall_status,
                        artifact="design/design_summary.json",
                    )
                ],
                alternative_explanations=[
                    "The apparent technical separation may be protected biology aligned with run or panel version."
                ],
                limitations=[
                    "This cohort lacks the independent bridge support required to estimate both effects."
                ],
                recommended_follow_ups=[
                    _follow_up(
                        "Balanced cross-run and cross-panel bridge study",
                        variable,
                        [
                            "shared reference material",
                            "representative samples from each biological group",
                        ],
                        "The signature follows run or panel version within matched material.",
                        "The signature remains tied to biology after balanced reprocessing.",
                    )
                ],
                related_variables=[*config.variables.biological, *config.variables.technical],
                artifact_links=[
                    "design/pairwise_identifiability.parquet",
                    "ngs/common_target_universe.parquet",
                    "ngs/detection_opportunity.parquet",
                ],
            )
        )
    technical = factor_associations[factor_associations.role == "technical"].sort_values(
        "effect_size", ascending=False
    )
    if not technical.empty and float(technical.iloc[0].effect_size) >= 0.2:
        row = technical.iloc[0]
        variable = str(row.variable)
        cards.append(
            EvidenceCard(
                finding_id="ngs-coverage-technical-factor",
                priority=len(cards) + 1,
                severity="warning",
                classification="technical",
                title=f"Coverage structure associated with {variable}",
                observation=f"A count-aware coverage factor has effect-size {float(row.effect_size):.3f} for {variable}; this is an association in an exploratory offset-normalized representation.",
                supporting_evidence=[
                    EvidenceReference(
                        label="Factor association effect size",
                        value=float(row.effect_size),
                        artifact="ngs/coverage_factor_associations.parquet",
                        row_filter={"factor": str(row.factor), "variable": variable},
                    )
                ],
                alternative_explanations=[
                    "Unequal sequencing exposure",
                    "Correlated library preparation or reagent lot",
                    "Protected biology incompletely balanced across the technical level",
                ],
                limitations=[
                    "Latent-factor association does not identify a molecular mechanism.",
                    "Only supplied assay metadata and common targets are evaluated.",
                ],
                recommended_follow_ups=[
                    _follow_up(
                        "Blinded bridge-control rerun",
                        variable,
                        ["same reference material across runs", "balanced library inputs"],
                        "The coverage signature follows the implicated technical level.",
                        "The signature does not reproduce in matched bridge material.",
                    )
                ],
                related_modalities=["targeted_ngs_coverage"],
                related_factors=[str(row.factor)],
                related_variables=[variable],
                artifact_links=[
                    "ngs/coverage_factor_scores.parquet",
                    "ngs/coverage_factor_loadings.parquet",
                    "ngs/coverage_model_results.parquet",
                ],
            )
        )
    if (
        not ffpe_evidence.empty
        and ffpe_evidence.iloc[0].applicability_status == "available"
        and float(ffpe_evidence.iloc[0].odds_ratio) > 1
    ):
        row = ffpe_evidence.iloc[0]
        cards.append(
            EvidenceCard(
                finding_id="ngs-ffpe-context",
                priority=len(cards) + 1,
                severity="warning",
                classification="technical",
                title="Low-VAF C>T/G>A pattern is consistent with a damage-related hypothesis",
                observation=f"After depth adjustment, the configured low-VAF context pattern has odds ratio {float(row.odds_ratio):.2f} for FFPE status. Original allele counts and calls are unchanged.",
                supporting_evidence=[
                    EvidenceReference(
                        label="Depth-adjusted FFPE odds ratio",
                        value=float(row.odds_ratio),
                        artifact="ngs/ffpe_evidence.parquet",
                    )
                ],
                alternative_explanations=[
                    "Correlated extraction or library preparation",
                    "Context-specific background error",
                    "Unequal depth or sample quality",
                ],
                limitations=[
                    "The association does not prove FFPE damage causation.",
                    "Artifactor uses upstream summary counts and does not inspect reads.",
                ],
                recommended_follow_ups=[
                    _follow_up(
                        "Damage-repair and orthogonal-confirmation comparison",
                        "ffpe_status",
                        [
                            "matched fresh-frozen material",
                            "reference dilution series",
                            "blinded locus confirmation",
                        ],
                        "The low-VAF context excess is reduced by damage repair and reproduces in affected material.",
                        "The excess persists equally in non-FFPE controls or does not confirm orthogonally.",
                    )
                ],
                related_modalities=["targeted_ngs_allele_counts"],
                related_variables=["ffpe_status", "DV200"],
                artifact_links=[
                    "ngs/sequence_context_summary.parquet",
                    "ngs/ffpe_evidence.parquet",
                    "ngs/variant_callable_status.parquet",
                ],
            )
        )
    limited = (
        opportunity.groupby("variable").low_depth_fraction.max().sort_values(ascending=False)
        if not opportunity.empty
        else pd.Series(dtype=float)
    )
    if not limited.empty and float(limited.iloc[0]) > 0.2:
        variable = str(limited.index[0])
        cards.append(
            EvidenceCard(
                finding_id="ngs-detection-opportunity",
                priority=len(cards) + 1,
                severity="high",
                classification="mixed",
                title="Detection opportunity differs across cohort strata",
                observation=f"At least one {variable} stratum has {float(limited.iloc[0]):.1%} monitored observations below the configured depth threshold; absence cannot be interpreted as a negative event.",
                supporting_evidence=[
                    EvidenceReference(
                        label="Maximum low-depth fraction",
                        value=float(limited.iloc[0]),
                        artifact="ngs/detection_opportunity.parquet",
                    )
                ],
                alternative_explanations=[
                    "Unequal library yield",
                    "Panel-version structural differences",
                    "Sample-quality imbalance",
                ],
                limitations=[
                    "Callability summaries do not establish the underlying wet-lab source."
                ],
                recommended_follow_ups=[
                    _follow_up(
                        "Balanced exposure and common-callable-universe review",
                        variable,
                        ["depth-matched samples", "shared positive and negative controls"],
                        "Event differences diminish after opportunity is balanced.",
                        "Differences persist within adequately callable matched strata.",
                    )
                ],
                related_variables=[variable],
                artifact_links=[
                    "ngs/detection_opportunity.parquet",
                    "ngs/callability_summary.parquet",
                ],
            )
        )
    cards.append(
        EvidenceCard(
            finding_id="ngs-coverage-recommendation",
            priority=len(cards) + 1,
            severity="info" if recommendation.get("method") != "raw_offset" else "warning",
            classification="decision",
            title="Exploratory coverage representation decision",
            observation=str(recommendation["rationale"]),
            supporting_evidence=[
                EvidenceReference(
                    label="Selected representation",
                    value=str(recommendation["method"]),
                    artifact="interpretation/recommendation.json",
                )
            ],
            alternative_explanations=[
                "Eligible representations may be practically equivalent within resampling uncertainty."
            ],
            limitations=[
                "The selected representation is exploratory and does not replace original coverage counts.",
                "Variant calls and VAF observations are never corrected.",
            ],
            recommended_follow_ups=[
                _follow_up(
                    "Prospective bridge-control validation",
                    config.variables.technical[0],
                    ["technical replicates", "positive and negative reference controls"],
                    "The selected representation reduces technical disagreement while control recovery remains stable.",
                    "Protected effects or control agreement deteriorate prospectively.",
                )
            ],
            related_variables=[*config.variables.biological, *config.variables.technical],
            artifact_links=[
                "ngs/coverage_representation_metrics.parquet",
                "ngs/coverage_representation_eligibility.parquet",
                "ngs/target_effect_retention.parquet",
            ],
        )
    )
    return cards
