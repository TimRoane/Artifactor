import json
from pathlib import Path

from artifactor.io import checksum
from artifactor.pipeline import analyze
from artifactor.simulation import simulate

REQUIRED = [
    "run.json",
    "validation.json",
    "design/confounding.parquet",
    "diagnostics/factors.parquet",
    "diagnostics/associations.parquet",
    "corrections/none/rna.parquet",
    "evaluation/method_metrics.parquet",
    "evaluation/recommendation.json",
    "interpretation/findings.json",
    "telemetry/resources.json",
    "report/index.html",
    "design/design_summary.json",
    "design/pairwise_identifiability.parquet",
    "factors/factor_summary.parquet",
    "factors/factor_scores.parquet",
    "corrections/method_eligibility.parquet",
    "corrections/correction_metrics.parquet",
    "ground_truth/recovery_summary.json",
    "interpretation/evidence_cards.json",
    "exports/corrected_data.json",
    "report/report_model.json",
    "report/report_manifest.json",
    "report/artifactor-report.html",
    "provenance/run_manifest.json",
]


def test_tiny_end_to_end_and_reproducible_fingerprint(tmp_path: Path) -> None:
    cohort = tmp_path / "cohort"
    simulate("separable", cohort, seed=7, samples=30, rna_features=60, protein_features=30)
    run = analyze(cohort / "config.yaml")
    assert all((run / relative).exists() for relative in REQUIRED)
    second = analyze(cohort / "config.yaml", resume=True)
    assert second == run
    payload = json.loads((run / "run.json").read_text())
    assert payload["status"] == "complete"
    model = json.loads((run / "report/report_model.json").read_text())
    assert len(model["sections"]) == 7
    assert model["recommendation_method"] == payload["recommendation"]["method"]
    assert model["ground_truth"]["supplied"] is True
    corrected_export = json.loads((run / "exports/corrected_data.json").read_text())
    if payload["recommendation"]["method"] == "none":
        assert corrected_export["status"] == "not_generated"
        assert corrected_export["files"] == []
    else:
        assert corrected_export["status"] == "available"
        assert all((run / relative).exists() for relative in corrected_export["files"])
    document = (run / "report/artifactor-report.html").read_text(encoding="utf-8")
    for heading in (
        "Decision Overview",
        "Study-Design Audit",
        "Factor Explorer",
        "Correction Comparison",
        "Ground-Truth Audit",
        "Root-Cause Evidence",
        "Reproducibility and Downloads",
    ):
        assert heading in document
    assert '<script src="http' not in document
    assert (run / "report/artifactor-report.html").stat().st_size < 15 * 1024 * 1024
    assert "full omics matrix" not in document.lower()
    report_manifest = json.loads((run / "report/report_manifest.json").read_text())
    assert all(
        checksum(run / relative) == digest
        for relative, digest in report_manifest["source_artifact_checksums"].items()
    )


def test_confounded_refuses_correction(tmp_path: Path) -> None:
    cohort = tmp_path / "confounded"
    simulate("confounded", cohort, seed=9, samples=30, rna_features=60, protein_features=30)
    run = analyze(cohort / "config.yaml")
    recommendation = json.loads((run / "evaluation/recommendation.json").read_text())
    assert recommendation["method"] == "none"
    assert "not independently identifiable" in recommendation["rationale"]
    corrected_export = json.loads((run / "exports/corrected_data.json").read_text())
    assert corrected_export["status"] == "not_generated"
    assert corrected_export["files"] == []
