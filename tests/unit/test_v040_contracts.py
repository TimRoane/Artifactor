from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from artifactor.benchmarking import benchmark_plan, estimate_cost
from artifactor.cli import app
from artifactor.datasets import load_registry
from artifactor.external.contracts import (
    ConclusionStatus,
    EvidenceLevel,
    ResultStatus,
    ValidationQuestion,
    derive_conclusion,
)
from artifactor.reporting import build_external_report
from artifactor.reproducibility import compare_runs


def test_registry_is_frozen_and_access_explicit() -> None:
    registry = load_registry()
    assert registry.schema_version == "4.0"
    assert {item.dataset_id for item in registry.datasets} == {"seqc2_oncopanel", "cptac_ccrcc"}
    assert all(item.source_records and item.access_level.value.startswith("open_") for item in registry.datasets)
    assert all(record.checksum and record.size_bytes > 0 for item in registry.datasets for record in item.source_records)


def test_conclusion_is_mechanically_derived() -> None:
    question = ValidationQuestion(question_id="q", dataset_id="d", title="t", hypothesis="h", analysis_population="p", primary_metrics=["m"], acceptance_rule="r", non_evaluable_rule="n", evidence_level=EvidenceLevel.REFERENCE_TRUTH, result_status=ResultStatus.PARTIAL)
    conclusion = derive_conclusion("d", [question], False, "refused")
    assert conclusion.status == ConclusionStatus.PARTIAL
    assert not conclusion.correction_eligible


def test_benchmark_plan_is_read_only_and_cost_is_labeled_estimate() -> None:
    plan = benchmark_plan("small")
    assert plan["read_only"] and not plan["paid_execution_started"]
    cost = estimate_cost({"cpu_hours": 2, "memory_gb_hours": 4}, {"cpu_hour": 1, "memory_gb_hour": 0.5, "currency": "USD"})
    assert cost["total_estimated_cost"] == 4
    assert cost["estimate_not_observed_cost"]


def test_compare_runs_separates_environment_fields(tmp_path: Path) -> None:
    left, right = tmp_path / "a", tmp_path / "b"
    left.mkdir()
    right.mkdir()
    common = {"schema_version": "4.0", "input_fingerprint": "x", "config_fingerprint": "y", "recommendation": {"method": "none"}}
    (left / "run.json").write_text(json.dumps({**common, "timestamp": "one"}), encoding="utf-8")
    (right / "run.json").write_text(json.dumps({**common, "timestamp": "two"}), encoding="utf-8")
    pd.DataFrame({"id": ["x"], "score": [1.0]}).to_parquet(left / "values.parquet", index=False)
    pd.DataFrame({"id": ["x"], "score": [1.0 + 1e-8]}).to_parquet(right / "values.parquet", index=False)
    result = compare_runs(left, right)
    assert result.decision_parity
    assert result.overall_status == "equivalent_within_tolerance"
    assert "timestamp" in result.environment_differences


def test_v040_cli_commands_are_discoverable() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["datasets", "list"])
    assert result.exit_code == 0
    assert "seqc2_oncopanel" in result.stdout
    result = runner.invoke(app, ["benchmark", "plan", "--profile", "small"])
    assert result.exit_code == 0
    assert '"read_only": true' in result.stdout


def test_external_report_rebuilds_from_persisted_artifacts(tmp_path: Path) -> None:
    evidence = tmp_path / "external_validation"
    evidence.mkdir()
    (evidence / "dataset_identity.json").write_text(json.dumps({"schema_version": "4.0", "dataset_id": "fixture", "source_snapshot": "frozen", "tier": "fixture", "preparation_fingerprint": "abc"}), encoding="utf-8")
    (evidence / "validation_conclusion.json").write_text(json.dumps({"schema_version": "4.0", "status": "partially_validated", "status_reason": "derived", "correction_eligible": False, "correction_reason": "refused"}), encoding="utf-8")
    (evidence / "preparation_manifest.json").write_text(json.dumps({"warnings": ["known limitation"]}), encoding="utf-8")
    (evidence / "deviation_log.json").write_text("[]", encoding="utf-8")
    pd.DataFrame([{"question_id": "q", "title": "Question", "result_status": "partial", "result_summary": "limited", "evidence_level": "reference_truth"}]).to_parquet(evidence / "validation_questions.parquet", index=False)
    pd.DataFrame([{"comparison": "published_direction", "status": "partially_consistent"}]).to_parquet(evidence / "source_study_comparison.parquet", index=False)
    report = build_external_report(tmp_path)
    assert report.name == "external-validation-report.html"
    assert "partially_validated" in report.read_text(encoding="utf-8")
