from __future__ import annotations

import pandas as pd

from artifactor.config import ArtifactorConfig
from artifactor.contracts import EligibilityResult


def build_findings(
    associations: pd.DataFrame,
    eligibility: EligibilityResult,
    recommendation: dict[str, object],
    config: ArtifactorConfig,
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    if not eligibility.eligible:
        findings.append(
            {
                "priority": "high",
                "classification": "mixed",
                "title": "Study design does not identify technical and protected biological effects independently",
                "evidence": eligibility.reasons,
                "interpretation": "The observed association may reflect biology, technical handling, or both.",
                "limitation": "This cohort cannot separate the aligned variables.",
                "follow_up": "Add bridge samples spanning biological groups and processing batches, or repeat with randomized processing.",
                "causal": False,
            }
        )
    supported = associations[
        (associations.q_value <= config.analysis.association_q_threshold)
        & (associations.effect_size >= config.analysis.association_effect_threshold)
    ].sort_values("effect_size", ascending=False)
    for _, row in supported.head(5).iterrows():
        findings.append(
            {
                "priority": "high" if row.effect_size >= 0.25 else "medium",
                "classification": row.role,
                "title": f"{row.variable} is associated with {row.modality} {row.factor}",
                "evidence": [
                    {
                        "effect_size": float(row.effect_size),
                        "q_value": float(row.q_value),
                        "n": int(row.n),
                    }
                ],
                "interpretation": f"The factor pattern is consistent with a {row.role} source but does not establish causation.",
                "limitation": "Latent-factor associations can reflect correlated, unmeasured variables.",
                "follow_up": "Repeat representative samples across the implicated technical levels and compare blinded measurements.",
                "causal": False,
            }
        )
    findings.append(
        {
            "priority": "medium",
            "classification": "decision",
            "title": f"Recommended output: {recommendation['method']}",
            "evidence": [recommendation["rationale"]],
            "interpretation": "Selection balances technical removal against retention of declared biology.",
            "limitation": "Preservation is evaluated only for declared variables and observed cross-modal signal.",
            "follow_up": "Validate the selected representation against independent controls before downstream discovery.",
            "causal": False,
        }
    )
    return findings
