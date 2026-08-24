from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from artifactor.pipeline import analyze
from artifactor.reporting import build_report
from artifactor.simulation import simulate


def test_report_rebuild_and_optional_ground_truth_omission(tmp_path: Path) -> None:
    cohort = tmp_path / "cohort"
    simulate("separable", cohort, seed=12, samples=24, rna_features=40, protein_features=20)
    run = analyze(cohort / "config.yaml")
    metrics_before = (run / "evaluation/method_metrics.parquet").read_bytes()
    for relative in (
        "ground_truth/recovery_summary.json",
        "ground_truth/feature_recovery.parquet",
        "ground_truth/injected_vs_estimated.parquet",
    ):
        (run / relative).unlink()
    destination = build_report(run)
    assert destination.exists()
    assert (run / "evaluation/method_metrics.parquet").read_bytes() == metrics_before
    model = json.loads((run / "report/report_model.json").read_text())
    assert model["ground_truth"]["omission_reason"] == "ground_truth_not_supplied"


def test_v010_report_has_precise_migration_error(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text('{"schema_version":"1.0"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Rerun.*v0.2.0"):
        build_report(tmp_path)


def test_report_uses_real_colors_under_streamlit_plotly_theme(tmp_path: Path) -> None:
    import plotly.io as pio
    import streamlit  # noqa: F401

    assert pio.templates.default == "streamlit"
    cohort = tmp_path / "streamlit-colors"
    simulate("separable", cohort, seed=21, samples=24, rna_features=40, protein_features=20)
    run = analyze(cohort / "config.yaml")
    document = (run / "report/artifactor-report.html").read_text(encoding="utf-8")
    colors = re.findall(
        r'hovertemplate":"condition=[^\\]+.*?marker":\{"color":"(#[0-9A-Fa-f]{6})',
        document,
        flags=re.DOTALL,
    )
    assert colors[:2] == ["#2563EB", "#DC2626"]
