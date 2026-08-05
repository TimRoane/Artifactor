from pathlib import Path

import pytest
from pydantic import ValidationError

from artifactor.config import ArtifactorConfig


def valid_payload() -> dict:
    return {
        "project": {"name": "test"},
        "manifest": {"path": "manifest.parquet"},
        "variables": {
            "biological": ["condition"],
            "technical": ["batch"],
            "protected": ["condition"],
        },
        "modalities": [
            {"name": "rna", "kind": "rna_continuous", "path": "rna.parquet"},
            {"name": "protein", "kind": "proteomics_continuous", "path": "protein.parquet"},
        ],
    }


def test_unknown_key_is_rejected() -> None:
    payload = valid_payload()
    payload["analysis"] = {"permutatoins": 99}
    with pytest.raises(ValidationError, match="permutatoins"):
        ArtifactorConfig.model_validate(payload)


def test_raw_counts_require_explicit_transform() -> None:
    payload = valid_payload()
    payload["modalities"][0]["kind"] = "rna_counts"
    with pytest.raises(ValidationError, match="explicit transform"):
        ArtifactorConfig.model_validate(payload)


def test_relative_paths_resolve_from_config() -> None:
    config = ArtifactorConfig.model_validate(valid_payload()).resolved(Path("example/config.yaml"))
    assert config.manifest.path.is_absolute()
    assert config.manifest.path.name == "manifest.parquet"
