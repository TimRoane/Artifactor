from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from artifactor.config import ArtifactorConfig
from artifactor.contracts import EvidenceCard, GroundTruthRow, MeasurementFamily, OmicsMatrix
from artifactor.diagnostics import factor_stability
from artifactor.evaluation import METRIC_REGISTRY, relative_change
from artifactor.modalities import capability_for, capability_issues, capability_rows


def test_metric_registry_is_complete_and_zero_baseline_is_not_applicable() -> None:
    assert set(METRIC_REGISTRY) == {
        "technical_predictability",
        "biological_retention",
        "technical_removal",
        "biological_loss",
        "cross_modal_concordance",
    }
    assert all(item.limitations and item.short_definition for item in METRIC_REGISTRY.values())
    assert relative_change(0.0, 0.0) == (None, "baseline_below_tolerance")
    assert relative_change(0.5, 1.0) == (0.5, None)


def test_invalid_evidence_card_and_ground_truth_fail_actionably() -> None:
    with pytest.raises(ValidationError, match="supporting_evidence"):
        EvidenceCard.model_validate(
            {
                "finding_id": "bad",
                "priority": 1,
                "severity": "info",
                "classification": "technical",
                "title": "Bad card",
                "observation": "An association was observed.",
                "supporting_evidence": [],
                "alternative_explanations": ["Another variable"],
                "limitations": ["Observational"],
                "recommended_follow_ups": [],
                "artifact_links": ["x.json"],
            }
        )
    with pytest.raises(ValidationError, match="mutually exclusive"):
        GroundTruthRow(
            scenario="x",
            modality="rna",
            feature_id="a",
            is_biological=True,
            is_technical=True,
            is_mixed=False,
            is_null=False,
        )


def test_measurement_family_capabilities_are_explicit() -> None:
    assert capability_for("rna_continuous").measurement_family == MeasurementFamily.CONTINUOUS
    assert capability_for("variant_binary").supported_corrections == ["none"]
    rows = capability_rows()
    assert {row["measurement_family"] for row in rows} >= {
        "continuous",
        "count",
        "fraction",
        "binary",
        "segment",
        "sparse_event",
    }
    with pytest.raises(ValueError, match="unknown modality kind"):
        capability_for("fastq")


def test_unsupported_binary_correction_is_rejected_before_loading() -> None:
    config = ArtifactorConfig.model_validate(
        {
            "project": {"name": "binary"},
            "manifest": {"path": "does-not-exist.parquet"},
            "variables": {"biological": ["condition"], "technical": ["batch"]},
            "modalities": [
                {"name": "variants", "kind": "variant_binary", "path": "missing.parquet"},
                {"name": "protein", "kind": "proteomics_continuous", "path": "missing2.parquet"},
            ],
            "corrections": {"methods": ["none", "residualize"]},
        }
    )
    issues = capability_issues(config)
    assert issues[0].code == "unsupported_modality_correction"
    assert "binary measurements" in issues[0].message


def test_factor_stability_is_sign_invariant() -> None:
    rng = np.random.default_rng(4)
    values = rng.normal(size=(20, 4))
    matrix = OmicsMatrix(
        "rna",
        tuple(f"s{i}" for i in range(20)),
        tuple(f"f{i}" for i in range(4)),
        values,
        np.zeros_like(values, dtype=bool),
        "rna_continuous",
    )
    config = ArtifactorConfig.model_validate(
        {
            "project": {"name": "stability", "random_seed": 4},
            "manifest": {"path": "manifest.parquet"},
            "variables": {"biological": ["condition"], "technical": ["batch"]},
            "modalities": [
                {"name": "rna", "kind": "rna_continuous", "path": "rna.parquet"},
                {"name": "protein", "kind": "proteomics_continuous", "path": "protein.parquet"},
            ],
            "analysis": {"factor_stability_bootstraps": 3},
        }
    )
    components = np.linalg.svd(values, full_matrices=False)[2].T[:, 0]
    rows = [
        {"modality": modality, "feature": feature, "factor": "PC1", "loading": loading}
        for modality in ("rna", "block_pca")
        for feature, loading in zip(
            (
                matrix.feature_names
                if modality == "rna"
                else tuple(f"rna:{x}" for x in matrix.feature_names)
            ),
            components,
            strict=True,
        )
    ]
    loadings = pd.DataFrame(rows)
    positive = factor_stability({"rna": matrix}, loadings, config)
    loadings["loading"] *= -1
    negative = factor_stability({"rna": matrix}, loadings, config)
    assert positive == pytest.approx(negative)
