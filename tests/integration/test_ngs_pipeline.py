from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from artifactor.pipeline import analyze
from artifactor.reporting import build_report
from artifactor.simulation import simulate

REQUIRED_NGS = (
    "ngs/validation_summary.json",
    "ngs/sample_qc_summary.parquet",
    "ngs/callability_summary.parquet",
    "ngs/common_target_universe.parquet",
    "ngs/coverage_model_results.parquet",
    "ngs/coverage_factor_scores.parquet",
    "ngs/gc_bias_curves.parquet",
    "ngs/coverage_representation_metrics.parquet",
    "ngs/variant_model_results.parquet",
    "ngs/variant_callable_status.parquet",
    "ngs/sequence_context_summary.parquet",
    "ngs/strand_bias_results.parquet",
    "ngs/orientation_bias_results.parquet",
    "ngs/read_support_diagnostics.parquet",
    "ngs/control_recovery.parquet",
    "ngs/replicate_agreement.parquet",
    "report/report_model.json",
    "report/artifactor-report.html",
)


def test_tiny_ngs_run_is_complete_immutable_and_reportable(tmp_path: Path) -> None:
    cohort = tmp_path / "ngs"
    simulate("ngs_separable", cohort, seed=13, samples=32, rna_features=48, protein_features=24)
    before = {
        name: (cohort / name).read_bytes()
        for name in ("target_coverage.parquet", "variant_counts.parquet")
    }
    run = analyze(cohort / "config.yaml")
    assert all((run / item).exists() for item in REQUIRED_NGS)
    assert before == {name: (cohort / name).read_bytes() for name in before}
    payload = json.loads((run / "run.json").read_text())
    assert payload["status"] == "complete"
    assert payload["analysis_type"] == "targeted_ngs"
    assert payload["original_genomic_observations_unchanged"] is True
    model = json.loads((run / "report/report_model.json").read_text())
    assert model["analysis_type"] == "targeted_ngs"
    assert (
        "Original genomic observations and call states are unchanged"
        in model["ngs_summary"]["variant_statement"]
    )
    document = (run / "report/artifactor-report.html").read_text(encoding="utf-8")
    for heading in (
        "Decision Overview",
        "Design and Callability",
        "NGS QC and Coverage Factors",
        "Coverage Mitigation and Variant Diagnostics",
        "Root-Cause Evidence",
        "Reproducibility and Downloads",
    ):
        assert heading in document
    assert '<script src="http' not in document
    metrics_before = (run / "ngs/coverage_representation_metrics.parquet").read_bytes()
    build_report(run)
    assert (run / "ngs/coverage_representation_metrics.parquet").read_bytes() == metrics_before


def test_ngs_confounded_is_successful_scientific_refusal(tmp_path: Path) -> None:
    cohort = tmp_path / "confounded"
    simulate("ngs_confounded", cohort, seed=14, samples=32, rna_features=48, protein_features=24)
    run = analyze(cohort / "config.yaml")
    payload = json.loads((run / "run.json").read_text())
    assert payload["status"] == "complete"
    assert payload["scientific_status"] == "scientific_refusal"
    assert payload["recommendation"]["method"] == "raw_offset"
    assert "refused" in payload["recommendation"]["rationale"]
    eligibility = pd.read_parquet(run / "ngs/coverage_representation_eligibility.parquet")
    assert not eligibility.loc[eligibility.representation != "raw_offset", "eligible"].any()
