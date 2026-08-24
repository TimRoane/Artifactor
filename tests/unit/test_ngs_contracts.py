from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from artifactor.config import load_config
from artifactor.contracts import TargetCoverageRow, VariantAlleleCountRow
from artifactor.modalities import capability_for
from artifactor.ngs import load_and_validate_ngs
from artifactor.ngs.variants import analyze_variants
from artifactor.simulation import simulate


def test_count_and_allele_contracts_reject_impossible_values() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        TargetCoverageRow(sample_id="S1", target_id="T1", raw_count=-1)
    with pytest.raises(ValidationError, match="alt_count cannot exceed total_depth"):
        VariantAlleleCountRow(
            sample_id="S1", variant_id="V1", ref_count=0, alt_count=4, total_depth=3
        )


def test_ngs_capabilities_preserve_observations_and_reject_continuous_correction() -> None:
    coverage = capability_for("targeted_ngs_coverage")
    allele = capability_for("targeted_ngs_allele_counts")
    assert coverage.supported_corrections == ["none"]
    assert "nb_technical_residual" in coverage.supported_representations
    assert "raw_count" in coverage.immutable_observations
    assert allele.supported_corrections == ["none"]
    assert "existing_call_state" in allele.immutable_observations


def test_reference_build_and_structural_absence_validation(tmp_path: Path) -> None:
    simulate("ngs_separable", tmp_path, seed=10, samples=20, rna_features=30, protein_features=16)
    config = load_config(tmp_path / "config.yaml")
    inputs = load_and_validate_ngs(config)
    absent_target = (
        pd.read_parquet(tmp_path / "target_annotations.parquet")
        .groupby("target_id")
        .panel_version.nunique()
        .idxmin()
    )
    assert absent_target not in set(inputs.common_targets.target_id)
    assert not inputs.coverage[inputs.coverage.target_id == absent_target].empty
    annotations = pd.read_parquet(tmp_path / "variant_annotations.parquet")
    annotations.loc[0, "reference_build"] = "GRCh37"
    annotations.to_parquet(tmp_path / "variant_annotations.parquet", index=False)
    with pytest.raises(ValueError, match="reference-build mismatch"):
        load_and_validate_ngs(config)


def test_zero_count_is_preserved_as_observed_not_missing(tmp_path: Path) -> None:
    simulate("ngs_separable", tmp_path, seed=11, samples=20, rna_features=30, protein_features=16)
    coverage_path = tmp_path / "target_coverage.parquet"
    coverage = pd.read_parquet(coverage_path)
    coverage.loc[0, "raw_count"] = 0
    coverage.to_parquet(coverage_path, index=False)
    inputs = load_and_validate_ngs(load_config(tmp_path / "config.yaml"))
    assert inputs.coverage.loc[0, "raw_count"] == 0
    assert pd.notna(inputs.coverage.loc[0, "raw_count"])


def test_missing_optional_read_support_omits_only_dependent_diagnostics(tmp_path: Path) -> None:
    simulate("ngs_separable", tmp_path, seed=12, samples=20, rna_features=30, protein_features=16)
    path = tmp_path / "variant_counts.parquet"
    frame = pd.read_parquet(path).drop(
        columns=[
            "alt_forward",
            "alt_reverse",
            "alt_f1r2",
            "alt_f2r1",
            "base_quality_mean",
            "mapping_quality_mean",
            "read_position_mean",
            "insert_size_mean",
        ]
    )
    frame.to_parquet(path, index=False)
    config = load_config(tmp_path / "config.yaml")
    inputs = load_and_validate_ngs(config)
    results = analyze_variants(inputs, config)
    assert (results.strand_bias.applicability_status != "available").all()
    assert (results.orientation_bias.applicability_status != "available").all()
    assert (results.read_support.applicability_status == "not_applicable").all()
