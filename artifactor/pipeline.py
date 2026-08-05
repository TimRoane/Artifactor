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
from artifactor.config import ArtifactorConfig, load_config
from artifactor.correction import apply_corrections
from artifactor.design import audit_design
from artifactor.diagnostics import associations, latent_diagnostics, outliers, variance_partition
from artifactor.evaluation import evaluate
from artifactor.interpretation import build_findings
from artifactor.io import checksum, read_table, validate_inputs, write_json, write_table
from artifactor.reporting import build_report


def _fingerprint(config: ArtifactorConfig, inputs: dict[str, str]) -> tuple[str, str]:
    config_json = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    config_checksum = hashlib.sha256(config_json.encode()).hexdigest()
    payload = json.dumps(
        {
            "config": config_json,
            "inputs": inputs,
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
    packages = ["numpy", "pandas", "polars", "pyarrow", "pydantic", "scikit-learn", "scipy"]
    result = {}
    for package in packages:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    return result


def analyze(config_path: Path, resume: bool = False) -> Path:
    started = time.perf_counter()
    started_at = datetime.now(UTC).isoformat()
    config = load_config(config_path)
    if config.analysis.analysis_budget == "quick":
        config = config.model_copy(
            update={
                "analysis": config.analysis.model_copy(
                    update={
                        "latent_components": min(config.analysis.latent_components, 5),
                        "permutations": min(config.analysis.permutations, 99),
                        "cross_validation_folds": min(config.analysis.cross_validation_folds, 3),
                        "bootstrap_iterations": min(config.analysis.bootstrap_iterations, 20),
                    }
                ),
                "modalities": [
                    modality.model_copy(
                        update={"max_features": min(modality.max_features or 1000, 1000)}
                    )
                    for modality in config.modalities
                ],
            }
        )
    input_paths = {"manifest": config.manifest.path} | {m.name: m.path for m in config.modalities}
    if config.feature_map:
        input_paths["feature_map"] = config.feature_map
    if config.ground_truth:
        input_paths["ground_truth"] = config.ground_truth
    checksums = {name: checksum(path) for name, path in input_paths.items()}
    fingerprint, config_checksum = _fingerprint(config, checksums)
    run_dir = config.project.output_dir / f"{config.project.name}-{fingerprint}"
    if resume and (run_dir / "run.json").exists():
        prior = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        if prior.get("status") == "complete":
            return run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    stages: dict[str, dict[str, object]] = {}
    warnings: list[str] = []

    def stage(name: str, start: float) -> None:
        stages[name] = {"status": "complete", "runtime_seconds": time.perf_counter() - start}

    moment = time.perf_counter()
    validation, metadata, matrices = validate_inputs(config)
    write_json(validation.model_dump(), run_dir / "validation.json")
    if not validation.valid or metadata is None:
        raise ValueError(
            "input validation failed: " + "; ".join(i.message for i in validation.issues)
        )
    warnings.extend(i.message for i in validation.issues if i.level == "warning")
    stage("validate", moment)
    moment = time.perf_counter()
    confounding, eligibility, design_summary = audit_design(metadata, config)
    write_table(confounding, run_dir / "design/confounding.parquet")
    write_table(
        confounding[
            [
                "biological_variable",
                "technical_variable",
                "overlap_score",
                "identifiability_status",
                "reason",
            ]
        ],
        run_dir / "design/overlap.parquet",
    )
    write_json(
        {"eligibility": eligibility.model_dump(), "design": design_summary},
        run_dir / "design/audit.json",
    )
    stage("design_audit", moment)
    moment = time.perf_counter()
    factors, loadings, scores, _ = latent_diagnostics(matrices, config)
    association_table = associations(scores, metadata, config)
    supported = association_table[
        (association_table.q_value <= config.analysis.association_q_threshold)
        & (association_table.effect_size >= config.analysis.association_effect_threshold)
    ]
    classifications: dict[tuple[str, str], str] = {}
    for key, group in supported.groupby(["modality", "factor"]):
        roles = set(group.role)
        has_biology = bool(roles & {"biological", "protected"})
        has_technical = "technical" in roles
        factor_key = (str(key[0]), str(key[1]))
        classifications[factor_key] = (
            "mixed"
            if has_biology and has_technical
            else "biological"
            if has_biology
            else "technical"
        )
    factors["classification"] = [
        classifications.get((str(row.modality), str(row.factor)), "unexplained")
        for row in factors.itertuples()
    ]
    variance = pd.concat(
        [variance_partition(m, metadata, config) for m in matrices.values()], ignore_index=True
    )
    outlier_table = pd.concat([outliers(m) for m in matrices.values()], ignore_index=True)
    missingness = pd.concat(
        [
            pd.DataFrame(
                {
                    "modality": m.name,
                    "sample_id": m.sample_ids,
                    "missing_fraction": m.missing_mask.mean(axis=1),
                }
            )
            for m in matrices.values()
        ],
        ignore_index=True,
    )
    for matrix in matrices.values():
        mask = pd.DataFrame(matrix.missing_mask, columns=matrix.feature_names)
        mask.insert(0, "sample_id", matrix.sample_ids)
        write_table(mask, run_dir / f"diagnostics/imputation_mask/{matrix.name}.parquet")
    for table, path in [
        (factors, "diagnostics/factors.parquet"),
        (loadings, "diagnostics/loadings.parquet"),
        (association_table, "diagnostics/associations.parquet"),
        (variance, "diagnostics/variance_partition.parquet"),
        (outlier_table, "diagnostics/outliers.parquet"),
        (missingness, "diagnostics/missingness.parquet"),
    ]:
        write_table(table, run_dir / path)
    if int(variance.negative_clamped.sum()):
        warnings.append(
            f"clamped {int(variance.negative_clamped.sum())} negative partial R-squared estimates for presentation"
        )
    stage("diagnostics", moment)
    moment = time.perf_counter()
    corrected, method_status = apply_corrections(matrices, metadata, config, eligibility.eligible)
    for method, by_modality in corrected.items():
        for name, matrix in by_modality.items():
            write_table(matrix.to_frame(), run_dir / f"corrections/{method}/{name}.parquet")
    write_json(method_status, run_dir / "corrections/status.json")
    stage("corrections", moment)
    moment = time.perf_counter()
    feature_map = read_table(config.feature_map) if config.feature_map else None
    metrics, bootstrap, recommendation = evaluate(corrected, metadata, config, feature_map)
    if not eligibility.eligible:
        recommendation = {
            "method": "none",
            "rationale": "Correction not recommended. Biological condition and processing batch are not independently identifiable from this cohort.",
            "eligibility": eligibility.model_dump(),
        }
    write_table(metrics, run_dir / "evaluation/method_metrics.parquet")
    write_table(bootstrap, run_dir / "evaluation/bootstrap_metrics.parquet")
    write_json(recommendation, run_dir / "evaluation/recommendation.json")
    if config.ground_truth:
        truth = read_table(config.ground_truth)
        technical_truth = truth[truth.signal == "processing_artifact"]
        expected = set(map(tuple, technical_truth[["modality", "feature"]].astype(str).to_numpy()))
        predicted = set(
            map(
                tuple,
                variance.nlargest(len(expected), "partial_r2_technical")[
                    [
                        "modality",
                        "feature",
                    ]
                ]
                .astype(str)
                .to_numpy(),
            )
        )
        hits = len(expected & predicted)
        write_json(
            {
                "artifact_feature_precision": hits / max(len(predicted), 1),
                "artifact_feature_recall": hits / max(len(expected), 1),
                "true_positive_count": hits,
            },
            run_dir / "evaluation/ground_truth_metrics.json",
        )
    stage("evaluation", moment)
    moment = time.perf_counter()
    findings = build_findings(association_table, eligibility, recommendation, config)
    write_json(findings, run_dir / "interpretation/findings.json")
    stage("interpretation", moment)
    peak = psutil.Process(os.getpid()).memory_info().rss
    write_json(
        {
            "runtime_seconds": time.perf_counter() - started,
            "peak_memory_bytes_observed": peak,
            "cpu_count": os.cpu_count(),
            "stages": stages,
        },
        run_dir / "telemetry/resources.json",
    )
    resolved = config.model_dump(mode="json")
    (run_dir / "resolved_config.yaml").write_text(
        yaml.safe_dump(resolved, sort_keys=False), encoding="utf-8"
    )
    write_json(checksums, run_dir / "input_checksums.json")
    run = {
        "schema_version": "1.0",
        "run_fingerprint": fingerprint,
        "status": "complete",
        "start_timestamp": started_at,
        "completion_timestamp": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "artifactor_version": __version__,
        "python_version": platform.python_version(),
        "dependency_versions": _versions(),
        "operating_system": platform.platform(),
        "architecture": platform.machine(),
        "random_seed": config.project.random_seed,
        "input_checksums": checksums,
        "configuration_checksum": config_checksum,
        "stages": stages,
        "warnings": warnings,
        "failures": [],
        "report_title": config.report.title,
        "sample_count": len(metadata),
        "modalities": list(matrices),
        "design_status": eligibility.status,
        "recommendation": recommendation,
    }
    write_json(run, run_dir / "run.json")
    moment = time.perf_counter()
    build_report(run_dir)
    stage("report", moment)
    run["stages"] = stages
    write_json(run, run_dir / "run.json")
    return run_dir
