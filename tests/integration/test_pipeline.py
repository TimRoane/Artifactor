import json
from pathlib import Path

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


def test_confounded_refuses_correction(tmp_path: Path) -> None:
    cohort = tmp_path / "confounded"
    simulate("confounded", cohort, seed=9, samples=30, rna_features=60, protein_features=30)
    run = analyze(cohort / "config.yaml")
    recommendation = json.loads((run / "evaluation/recommendation.json").read_text())
    assert recommendation["method"] == "none"
    assert "not independently identifiable" in recommendation["rationale"]
