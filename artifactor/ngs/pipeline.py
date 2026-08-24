# mypy: ignore-errors
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import psutil
import yaml

from artifactor import __version__
from artifactor.config import ArtifactorConfig
from artifactor.design import audit_design, build_design_evidence
from artifactor.io import checksum, write_json, write_table
from artifactor.modalities import capability_rows
from artifactor.reporting import build_report

from .coverage import analyze_coverage
from .evaluation import evaluate_coverage_truth, evaluate_variant_truth
from .evidence import build_ngs_evidence_cards
from .io import load_and_validate_ngs
from .qc import callability_evidence, detection_opportunity, sample_qc_evidence
from .variants import analyze_variants


def _fingerprint(config: ArtifactorConfig, checksums: dict[str, str]) -> tuple[str, str]:
    config_json = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    config_checksum = hashlib.sha256(config_json.encode()).hexdigest()
    payload = json.dumps(
        {
            "config": config_json,
            "inputs": checksums,
            "version": __version__,
            "seed": config.project.random_seed,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12], config_checksum


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _versions() -> dict[str, str]:
    result = {}
    for package in (
        "numpy",
        "pandas",
        "pyarrow",
        "pydantic",
        "scikit-learn",
        "scipy",
        "statsmodels",
    ):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    return result


def _write_table(frame: pd.DataFrame, path: Path) -> None:
    output = frame.copy()
    if "schema_version" in output:
        output["schema_version"] = "3.0"
    else:
        output.insert(0, "schema_version", "3.0")
    write_table(output, path)


def analyze_ngs(config_path: Path, config: ArtifactorConfig, resume: bool = False) -> Path:
    started = time.perf_counter()
    started_at = datetime.now(UTC).isoformat()
    inputs = load_and_validate_ngs(config)
    fingerprint, config_checksum = _fingerprint(config, inputs.original_checksums)
    run_dir = config.project.output_dir / f"{config.project.name}-{fingerprint}"
    if resume and (run_dir / "run.json").exists():
        prior = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        if prior.get("status") == "complete":
            return run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    stages: dict[str, dict[str, object]] = {}
    warnings = list(inputs.summary.warnings)

    def stage(name: str, start: float) -> None:
        stages[name] = {"status": "complete", "runtime_seconds": time.perf_counter() - start}

    moment = time.perf_counter()
    write_json(inputs.summary.model_dump(mode="json"), run_dir / "ngs/validation_summary.json")
    write_json(
        {
            "valid": True,
            "issues": [
                {"level": "warning", "code": "ngs_provenance_warning", "message": item}
                for item in warnings
            ],
        },
        run_dir / "validation.json",
    )
    _write_table(inputs.common_targets, run_dir / "ngs/common_target_universe.parquet")
    write_json(
        {
            "schema_version": "3.0",
            "capabilities": [
                *capability_rows("targeted_ngs_coverage"),
                *capability_rows("targeted_ngs_allele_counts"),
            ],
        },
        run_dir / "ngs/ngs_capabilities.json",
    )
    stage("validate_ngs", moment)

    moment = time.perf_counter()
    pairwise, eligibility, design_diagnostics = audit_design(inputs.manifest, config)
    design_summary, enriched_pairwise, cells, matrix_diagnostics = build_design_evidence(
        inputs.manifest, config, pairwise, eligibility, design_diagnostics
    )
    write_json(design_summary.model_dump(mode="json"), run_dir / "design/design_summary.json")
    _write_table(enriched_pairwise, run_dir / "design/pairwise_identifiability.parquet")
    _write_table(cells, run_dir / "design/contingency_cells.parquet")
    write_json(matrix_diagnostics, run_dir / "design/design_matrix_diagnostics.json")
    write_json(
        {"eligibility": eligibility.model_dump(mode="json"), "design": design_diagnostics},
        run_dir / "design/audit.json",
    )
    stage("audit_ngs_design", moment)

    moment = time.perf_counter()
    qc_summary, qc_associations = sample_qc_evidence(inputs, config)
    callability = callability_evidence(inputs, config)
    opportunity = detection_opportunity(inputs, config)
    _write_table(qc_summary, run_dir / "ngs/sample_qc_summary.parquet")
    _write_table(qc_associations, run_dir / "ngs/sample_qc_associations.parquet")
    _write_table(callability, run_dir / "ngs/callability_summary.parquet")
    _write_table(opportunity, run_dir / "ngs/detection_opportunity.parquet")
    stage("analyze_sample_qc", moment)

    moment = time.perf_counter()
    coverage = analyze_coverage(inputs, config, design_summary)
    for frame, relative in (
        (coverage.model_results, "ngs/coverage_model_results.parquet"),
        (coverage.factor_scores, "ngs/coverage_factor_scores.parquet"),
        (coverage.factor_loadings, "ngs/coverage_factor_loadings.parquet"),
        (coverage.factor_associations, "ngs/coverage_factor_associations.parquet"),
        (coverage.gc_curves, "ngs/gc_bias_curves.parquet"),
        (coverage.representation_metrics, "ngs/coverage_representation_metrics.parquet"),
        (coverage.representation_eligibility, "ngs/coverage_representation_eligibility.parquet"),
        (coverage.target_effect_retention, "ngs/target_effect_retention.parquet"),
    ):
        _write_table(frame, run_dir / relative)
    for name, frame in coverage.representations.items():
        _write_table(frame, run_dir / f"ngs/representations/{name}.parquet")
    write_json(
        {
            "schema_version": "3.0",
            "strategy": "grouped_resampled_prediction_on_fixed_representation",
            "group_column": config.evaluation.group_column,
            "prediction_preprocessing": "scaler_and_pca_fit_within_each_training_fold",
            "representation_boundary": "Representations are fitted once without simulator truth; this documented alternative is used because unseen technical levels do not have a safe correction transform.",
            "ground_truth_used_for_fitting_or_selection": False,
        },
        run_dir / "ngs/evaluation_boundary.json",
    )
    stage("fit_coverage_models_and_representations", moment)

    moment = time.perf_counter()
    variants = analyze_variants(inputs, config)
    for frame, relative in (
        (variants.model_results, "ngs/variant_model_results.parquet"),
        (variants.callable_status, "ngs/variant_callable_status.parquet"),
        (variants.context_summary, "ngs/sequence_context_summary.parquet"),
        (variants.strand_bias, "ngs/strand_bias_results.parquet"),
        (variants.orientation_bias, "ngs/orientation_bias_results.parquet"),
        (variants.read_support, "ngs/read_support_diagnostics.parquet"),
        (variants.ffpe_evidence, "ngs/ffpe_evidence.parquet"),
        (variants.control_recovery, "ngs/control_recovery.parquet"),
        (variants.replicate_agreement, "ngs/replicate_agreement.parquet"),
    ):
        _write_table(frame, run_dir / relative)
    stage("analyze_allele_counts_and_controls", moment)

    moment = time.perf_counter()
    coverage_truth_path = config.modalities[0].path.parent / "target_ground_truth.parquet"
    variant_truth_path = config.modalities[0].path.parent / "variant_ground_truth.parquet"
    if coverage_truth_path.exists():
        coverage_truth_summary, coverage_recovery = evaluate_coverage_truth(
            coverage.model_results, pd.read_parquet(coverage_truth_path)
        )
        write_json(coverage_truth_summary, run_dir / "ground_truth/ngs_coverage_recovery.json")
        _write_table(
            coverage_recovery, run_dir / "ground_truth/ngs_coverage_feature_recovery.parquet"
        )
        _write_table(
            coverage_recovery[
                [
                    column
                    for column in (
                        "target_id",
                        "technical_effect_size",
                        "technical_effect",
                        "biological_effect_size",
                        "biological_effect",
                    )
                    if column in coverage_recovery
                ]
            ],
            run_dir / "ground_truth/injected_vs_estimated.parquet",
        )
    if variant_truth_path.exists():
        variant_truth_summary, variant_recovery = evaluate_variant_truth(
            variants.callable_status,
            inputs.variant_annotations,
            inputs.manifest,
            pd.read_parquet(variant_truth_path),
            config.ngs.low_vaf_threshold,
            config.ngs.minimum_alt_count_for_diagnostics,
        )
        write_json(variant_truth_summary, run_dir / "ground_truth/ngs_variant_recovery.json")
        _write_table(variant_recovery, run_dir / "ground_truth/ngs_variant_event_recovery.parquet")
    stage("evaluate_ngs_ground_truth", moment)

    moment = time.perf_counter()
    recommendation = coverage.recommendation
    if not design_summary.correction_permitted:
        recommendation = {
            "method": "raw_offset",
            "representation": "raw_offset",
            "diagnostic_only": True,
            "rationale": "Exploratory coverage mitigation is refused because protected biology and run, batch, or panel structure are not independently identifiable. Original counts and calls remain unchanged.",
            "original_observations_unchanged": True,
            "eligibility": eligibility.model_dump(mode="json"),
        }
    cards = build_ngs_evidence_cards(
        design_summary,
        coverage.factor_associations,
        coverage.model_results,
        variants.ffpe_evidence,
        opportunity,
        recommendation,
        config,
    )
    write_json(recommendation, run_dir / "interpretation/recommendation.json")
    write_json(
        [card.model_dump(mode="json") for card in cards],
        run_dir / "interpretation/evidence_cards.json",
    )
    stage("build_ngs_evidence", moment)

    coverage_spec = next(item for item in config.modalities if item.kind == "targeted_ngs_coverage")
    allele_spec = next(
        item for item in config.modalities if item.kind == "targeted_ngs_allele_counts"
    )
    source_paths = {
        "manifest": config.manifest.path,
        "coverage": coverage_spec.path,
        "target_annotations": coverage_spec.annotations,
        "sample_qc": coverage_spec.sample_qc,
        "allele_counts": allele_spec.path,
        "variant_annotations": allele_spec.annotations,
    }
    if allele_spec.truth:
        source_paths["known_truth"] = allele_spec.truth
    current_checksums = {name: checksum(path) for name, path in source_paths.items()}
    for name, digest in current_checksums.items():
        expected = inputs.original_checksums[name]
        if digest != expected:
            raise RuntimeError(f"immutable targeted-NGS source {name} changed during analysis")
    resolved = config.model_dump(mode="json")
    (run_dir / "resolved_config.yaml").write_text(
        yaml.safe_dump(resolved, sort_keys=False), encoding="utf-8"
    )
    write_json(inputs.original_checksums, run_dir / "input_checksums.json")
    git_commit = _git_commit()
    if git_commit is None:
        warnings.append("Git commit was unavailable; source revision could not be recorded.")
    scientific_status = (
        "scientific_refusal"
        if not design_summary.correction_permitted
        else "diagnostic_only"
        if recommendation["method"] == "raw_offset"
        else "eligible_exploratory_representation"
    )
    run = {
        "schema_version": "3.0",
        "analysis_type": "targeted_ngs",
        "run_fingerprint": fingerprint,
        "status": "complete",
        "scientific_status": scientific_status,
        "start_timestamp": started_at,
        "completion_timestamp": datetime.now(UTC).isoformat(),
        "git_commit": git_commit,
        "artifactor_version": __version__,
        "python_version": platform.python_version(),
        "dependency_versions": _versions(),
        "operating_system": platform.platform(),
        "architecture": platform.machine(),
        "random_seed": config.project.random_seed,
        "reference_build": config.ngs.reference_build,
        "panel_versions": inputs.summary.panel_versions,
        "input_checksums": inputs.original_checksums,
        "configuration_checksum": config_checksum,
        "stages": stages,
        "warnings": warnings,
        "failures": [],
        "report_title": config.report.title,
        "sample_count": inputs.summary.sample_count,
        "target_count": inputs.summary.target_count,
        "variant_count": inputs.summary.variant_count,
        "modalities": [item.name for item in config.modalities],
        "design_status": design_summary.overall_status,
        "recommendation": recommendation,
        "original_genomic_observations_unchanged": True,
    }
    peak = psutil.Process(os.getpid()).memory_info().rss
    resources = {
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_bytes_observed": peak,
        "cpu_count": os.cpu_count(),
        "stages": stages,
    }
    write_json(run, run_dir / "run.json")
    write_json(run, run_dir / "provenance/run_manifest.json")
    write_json(resources, run_dir / "telemetry/resources.json")
    moment = time.perf_counter()
    build_report(run_dir)
    stage("build_report", moment)
    run["stages"] = stages
    resources["runtime_seconds"] = time.perf_counter() - started
    resources["stages"] = stages
    write_json(run, run_dir / "run.json")
    write_json(run, run_dir / "provenance/run_manifest.json")
    write_json(resources, run_dir / "telemetry/resources.json")
    build_report(run_dir)
    return run_dir
