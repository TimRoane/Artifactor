from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from artifactor.pipeline import analyze
from artifactor.simulation import simulate


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.slow
def test_default_ngs_separable_scientific_and_safety_gates(tmp_path: Path) -> None:
    cohort = tmp_path / "separable"
    simulate("ngs_separable", cohort, seed=20260807)
    source = {name: (cohort / name).read_bytes() for name in ("target_coverage.parquet", "variant_counts.parquet")}
    run = analyze(cohort / "config.yaml")
    coverage = _payload(run / "ground_truth/ngs_coverage_recovery.json")
    metrics = pd.read_parquet(run / "ngs/coverage_representation_metrics.parquet")
    selected = metrics.loc[metrics.representation == "nb_technical_residual"].iloc[0]
    assert min(
        coverage["technical_target_precision"],
        coverage["technical_target_recall"],
        coverage["biological_target_precision"],
        coverage["biological_target_recall"],
    ) >= 0.75
    assert selected.technical_removal >= 0.40
    assert selected.biological_loss < 0.05
    assert selected.replicate_loss <= 0.10
    assert source == {name: (cohort / name).read_bytes() for name in source}
    assert _payload(run / "ground_truth/ngs_variant_recovery.json")["original_calls_changed"] is False


@pytest.mark.slow
def test_ffpe_and_bridge_fixed_seed_evidence(tmp_path: Path) -> None:
    ffpe = tmp_path / "ffpe"
    simulate("ffpe_damage", ffpe, seed=20260807, samples=128, rna_features=160, protein_features=80)
    ffpe_run = analyze(ffpe / "config.yaml")
    recovery = _payload(ffpe_run / "ground_truth/ngs_variant_recovery.json")
    evidence = pd.read_parquet(ffpe_run / "ngs/ffpe_evidence.parquet").iloc[0]
    assert recovery["artifact_event_precision"] >= 0.70
    assert recovery["artifact_event_recall"] >= 0.70
    assert evidence.odds_ratio > 1
    document = (ffpe_run / "report/artifactor-report.html").read_text(encoding="utf-8").lower()
    assert "recommend automatic call removal" not in document

    bridge = tmp_path / "bridge"
    simulate("bridge_controls", bridge, seed=20260807, samples=128, rna_features=160, protein_features=80)
    bridge_run = analyze(bridge / "config.yaml")
    associations = pd.read_parquet(bridge_run / "ngs/coverage_factor_associations.parquet")
    leading = associations.sort_values("effect_size", ascending=False).iloc[0]
    assert leading.variable == "reagent_lot"
    card_text = (bridge_run / "interpretation/evidence_cards.json").read_text()
    assert "reagent_lot" in card_text
    assert pd.read_parquet(bridge_run / "ngs/replicate_agreement.parquet").applicability_status.eq("available").any()
