from __future__ import annotations

import math

from artifactor.contracts import MetricDefinition

BASELINE_TOLERANCE = 1e-8

METRIC_REGISTRY: dict[str, MetricDefinition] = {
    "technical_predictability": MetricDefinition(
        metric_id="technical_predictability",
        display_name="Detectability of laboratory signature",
        short_definition="Cross-validated detectability of declared technical metadata.",
        long_definition="Prediction performance for declared processing, handling, or assay variables from the analyzed representation.",
        direction="lower",
        range="model-dependent; categorical balanced accuracy is 0–1 and continuous R² is floored at 0",
        baseline_interpretation="The uncorrected representation defines the comparison baseline.",
        limitations=[
            "Depends on declared metadata and the prediction model.",
            "A low value does not prove that every artifact is absent.",
        ],
        aggregation_method="Arithmetic mean across adequate modality-variable evaluations.",
    ),
    "biological_retention": MetricDefinition(
        metric_id="biological_retention",
        display_name="Retention of declared biology",
        short_definition="Cross-validated detectability of declared biological variables.",
        long_definition="Prediction performance for the biological variables the analysis was instructed to preserve.",
        direction="higher",
        range="model-dependent; categorical balanced accuracy is 0–1 and continuous R² is floored at 0",
        baseline_interpretation="Compare with the same metric in the uncorrected representation.",
        limitations=["Does not protect undeclared or unknown biology."],
        aggregation_method="Arithmetic mean across adequate modality-variable evaluations.",
    ),
    "technical_removal": MetricDefinition(
        metric_id="technical_removal",
        display_name="Relative reduction in laboratory-signature detectability",
        short_definition="Relative reduction in technical predictability versus baseline.",
        long_definition="One minus corrected technical predictability divided by baseline technical predictability.",
        direction="higher",
        range="unbounded below to 1; not applicable for a near-zero baseline",
        baseline_interpretation="Zero means no change from the uncorrected representation.",
        limitations=["This is not the literal percentage of physical artifact molecules removed."],
        aggregation_method="Ratio of aggregate corrected and baseline predictability.",
    ),
    "biological_loss": MetricDefinition(
        metric_id="biological_loss",
        display_name="Relative loss of declared-biological detectability",
        short_definition="Relative decrease in biological predictability versus baseline.",
        long_definition="One minus corrected biological predictability divided by baseline biological predictability.",
        direction="lower",
        range="unbounded below to 1; not applicable for a near-zero baseline",
        baseline_interpretation="Zero means no change; a negative value means predictability improved within evaluation uncertainty.",
        limitations=[
            "Improvement can reflect noise reduction or uncertainty; it does not mean new biology was created."
        ],
        aggregation_method="Ratio of aggregate corrected and baseline predictability.",
    ),
    "cross_modal_concordance": MetricDefinition(
        metric_id="cross_modal_concordance",
        display_name="RNA-protein agreement",
        short_definition="Median agreement among supplied mapped cross-modal features.",
        long_definition="Median pairwise Pearson correlation over valid supplied feature mappings.",
        direction="unchanged",
        range="-1 to 1",
        baseline_interpretation="Correction should preserve the uncorrected mapped-feature concordance.",
        limitations=[
            "Only supplied mappings and the selected concordance statistic are evaluated."
        ],
        aggregation_method="Median across mapped feature-pair correlations.",
    ),
}


def relative_change(
    corrected: float, baseline: float, tolerance: float = BASELINE_TOLERANCE
) -> tuple[float | None, str | None]:
    if not math.isfinite(baseline) or abs(baseline) < tolerance:
        return None, "baseline_below_tolerance"
    return 1.0 - corrected / baseline, None


def metric_registry_payload() -> dict[str, dict[str, object]]:
    return {key: value.model_dump(mode="json") for key, value in METRIC_REGISTRY.items()}
