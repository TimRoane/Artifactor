from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from artifactor.onboarding import create_project_from_frames
from artifactor.pipeline import analyze
from artifactor.simulation import simulate


def test_single_matrix_onboarding_to_corrected_download(tmp_path: Path) -> None:
    source = tmp_path / "source"
    simulate("separable", source, seed=31, samples=36, rna_features=60, protein_features=24)
    config = create_project_from_frames(
        tmp_path / "project",
        "Uploaded Study",
        pd.read_parquet(source / "manifest.parquet"),
        {"expression.csv": pd.read_parquet(source / "rna.parquet")},
        biological=["condition"],
        technical=["extraction_batch"],
        protected=["condition"],
    )
    run = analyze(config)
    export = json.loads((run / "exports/corrected_data.json").read_text())
    assert export["status"] == "available"
    assert export["method"] in {"residualize", "combat"}
    assert export["files"]
    assert all((run / relative).exists() for relative in export["files"])
    corrected = pd.read_csv(run / export["files"][0])
    assert corrected.columns[0] == "sample_id"
    assert len(corrected) == 36
    report = (run / "report/artifactor-report.html").read_text(encoding="utf-8")
    assert "Corrected data are available" in report
