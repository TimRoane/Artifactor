import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from artifactor.pipeline import analyze
from artifactor.simulation import simulate


@pytest.mark.slow
def test_scientific_scenarios(tmp_path: Path) -> None:
    runs = {}
    for scenario in ("separable", "confounded", "cross_modal", "plate_drift"):
        cohort = tmp_path / scenario
        simulate(scenario, cohort)
        runs[scenario] = analyze(cohort / "config.yaml")

    separable = runs["separable"]
    metrics = pd.read_parquet(separable / "evaluation/method_metrics.parquet")
    selected = json.loads((separable / "evaluation/recommendation.json").read_text())["method"]
    chosen = metrics[metrics.method == selected].iloc[0]
    truth = json.loads((separable / "evaluation/ground_truth_metrics.json").read_text())
    assert chosen.technical_removal >= 0.40
    assert chosen.biological_loss < 0.05
    assert truth["technical_precision"] >= 0.75
    assert truth["technical_recall"] >= 0.75
    assert truth["biological_precision"] >= 0.75
    assert truth["biological_recall"] >= 0.75
    assert truth["false_positive_rate_null"] <= 0.25

    baseline = json.loads(Path("tests/fixtures/v010_baseline.json").read_text())
    for metric in (
        "technical_predictability",
        "biological_retention",
        "cross_modal_concordance",
    ):
        observed = dict(zip(metrics.method, metrics[metric], strict=True))
        for method, expected in baseline["separable"][metric].items():
            assert observed[method] == pytest.approx(expected, abs=baseline["absolute_tolerance"])

    no_truth_config = yaml.safe_load((tmp_path / "separable/config.yaml").read_text())
    no_truth_config["project"]["name"] = "separable-no-truth"
    no_truth_config.pop("ground_truth", None)
    no_truth_path = tmp_path / "separable/config-no-truth.yaml"
    no_truth_path.write_text(yaml.safe_dump(no_truth_config, sort_keys=False), encoding="utf-8")
    without_truth = analyze(no_truth_path)
    without_truth_recommendation = json.loads(
        (without_truth / "evaluation/recommendation.json").read_text()
    )
    assert without_truth_recommendation == json.loads(
        (separable / "evaluation/recommendation.json").read_text()
    )

    refused = json.loads((runs["confounded"] / "evaluation/recommendation.json").read_text())
    assert refused["method"] == "none"

    cross = pd.read_parquet(runs["cross_modal"] / "diagnostics/associations.parquet")
    extraction = cross[cross.variable == "extraction_batch"].groupby("modality").effect_size.max()
    assert extraction["rna"] > 0.75
    assert extraction["protein"] < 0.25
    cross_metrics = pd.read_parquet(runs["cross_modal"] / "evaluation/method_metrics.parquet")
    recommendation = json.loads(
        (runs["cross_modal"] / "evaluation/recommendation.json").read_text()
    )
    baseline = cross_metrics[cross_metrics.method == "none"].iloc[0]
    corrected = cross_metrics[cross_metrics.method == recommendation["method"]].iloc[0]
    assert corrected.cross_modal_concordance >= baseline.cross_modal_concordance * 0.90

    drift = pd.read_parquet(runs["plate_drift"] / "diagnostics/associations.parquet")
    assert drift[drift.variable == "run_order"].effect_size.max() > 0.75
