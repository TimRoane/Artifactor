from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from artifactor.cli import app
from artifactor.config import load_config
from artifactor.onboarding import create_project_from_frames, inspect_frames


def _inputs() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    samples = [f"S{i}" for i in range(1, 9)]
    metadata = pd.DataFrame(
        {
            "specimen": samples,
            "condition": ["control"] * 4 + ["treated"] * 4,
            "processing_batch": ["B1", "B2"] * 4,
            "unused_note": ["x"] * 8,
        }
    )
    sample_rows = pd.DataFrame(
        {"id": samples, "F1": range(8), "F2": range(10, 18), "F3": range(20, 28)}
    )
    feature_rows = pd.DataFrame(
        [["G1", *range(8)], ["G2", *range(8, 16)]],
        columns=["feature", *samples],
    )
    return metadata, {"rna.csv": sample_rows, "protein.tsv": feature_rows}


def test_inspection_infers_id_orientation_and_roles() -> None:
    metadata, matrices = _inputs()
    result = inspect_frames(metadata, matrices)
    assert result.metadata_sample_id_column == "specimen"
    assert [item.orientation for item in result.matrices] == [
        "samples_by_features",
        "features_by_samples",
    ]
    assert result.suggested_biological == ["condition"]
    assert result.suggested_technical == ["processing_batch"]
    assert all(item.matched_samples == 8 for item in result.matrices)


def test_project_creation_normalizes_inputs_and_builds_preflight(tmp_path: Path) -> None:
    metadata, matrices = _inputs()
    config_path = create_project_from_frames(
        tmp_path / "project",
        "New Study",
        metadata,
        matrices,
        biological=["condition"],
        technical=["processing_batch"],
        protected=["condition"],
    )
    config = load_config(config_path)
    assert len(config.modalities) == 2
    assert config.manifest.sample_id_column == "sample_id"
    assert all(item.path.exists() for item in config.modalities)
    preflight = json.loads((config_path.parent / "preflight.json").read_text())
    assert preflight["valid"]
    assert preflight["design_status"] == "separable"


def test_init_cli_supports_one_matrix(tmp_path: Path) -> None:
    metadata, matrices = _inputs()
    metadata_path = tmp_path / "metadata.csv"
    matrix_path = tmp_path / "matrix.csv"
    metadata.to_csv(metadata_path, index=False)
    matrices["rna.csv"].to_csv(matrix_path, index=False)
    result = CliRunner().invoke(
        app,
        [
            "init", "--input", str(matrix_path), "--metadata", str(metadata_path),
            "--project", str(tmp_path / "created"), "--name", "CLI Study",
            "--biological", "condition", "--technical", "processing_batch",
            "--protected", "condition",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "created/config.yaml").exists()
    assert "next_command" in result.stdout
