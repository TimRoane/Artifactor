# mypy: ignore-errors
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from artifactor import __version__
from artifactor.contracts import (
    DesignSummary,
    EvidenceCard,
    FactorSummary,
    GroundTruthSummary,
    ReportManifest,
    ReportModel,
    ReportSection,
)
from artifactor.evaluation import METRIC_REGISTRY
from artifactor.io import checksum, write_json

REQUIRED_V2_ARTIFACTS = (
    "run.json",
    "resolved_config.yaml",
    "design/design_summary.json",
    "factors/factor_summary.parquet",
    "corrections/method_eligibility.parquet",
    "corrections/correction_metrics.parquet",
    "interpretation/evidence_cards.json",
    "interpretation/recommendation.json",
)


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report_model(run_dir: Path) -> tuple[ReportModel, ReportManifest]:
    missing = [relative for relative in REQUIRED_V2_ARTIFACTS if not (run_dir / relative).exists()]
    if missing:
        raise ValueError(
            "This run does not contain the v0.2.0 evidence schema. Rerun `artifactor analyze` "
            f"with v0.2.0; missing artifacts: {', '.join(missing)}"
        )
    run = _json(run_dir / "run.json")
    if not isinstance(run, dict) or run.get("schema_version") != "2.0":
        raise ValueError(
            "Unsupported run schema; v0.2.0 report rebuilding requires schema_version 2.0"
        )
    config = yaml.safe_load((run_dir / "resolved_config.yaml").read_text(encoding="utf-8"))
    recommendation = _json(run_dir / "interpretation/recommendation.json")
    design = DesignSummary.model_validate(_json(run_dir / "design/design_summary.json"))
    factor_frame = pd.read_parquet(run_dir / "factors/factor_summary.parquet")
    factors = [FactorSummary.model_validate(row) for row in factor_frame.to_dict("records")]
    cards = [
        EvidenceCard.model_validate(row)
        for row in _json(run_dir / "interpretation/evidence_cards.json")
    ]
    truth_path = run_dir / "ground_truth/recovery_summary.json"
    ground_truth = (
        GroundTruthSummary.model_validate(_json(truth_path))
        if truth_path.exists()
        else GroundTruthSummary(supplied=False, omission_reason="ground_truth_not_supplied")
    )
    export_path = run_dir / "exports/corrected_data.json"
    correction_export = _json(export_path) if export_path.exists() else {"status": "not_generated", "files": []}
    sections = [
        ReportSection(
            section_id="decision",
            title="Decision Overview",
            included=True,
            summary=str(recommendation["rationale"]),
            artifact_links=["interpretation/recommendation.json"],
        ),
        ReportSection(
            section_id="design",
            title="Study-Design Audit",
            included=True,
            summary=design.summary_text,
            artifact_links=[
                "design/design_summary.json",
                "design/pairwise_identifiability.parquet",
                "design/contingency_cells.parquet",
            ],
        ),
        ReportSection(
            section_id="factors",
            title="Factor Explorer",
            included=True,
            summary=f"{len(factors)} latent factors were evaluated.",
            artifact_links=[
                "factors/factor_summary.parquet",
                "factors/factor_scores.parquet",
                "factors/factor_loadings.parquet",
            ],
        ),
        ReportSection(
            section_id="corrections",
            title="Correction Comparison",
            included=True,
            summary="Eligible correction methods are compared against the uncorrected representation with declared-biology guardrails.",
            artifact_links=[
                "corrections/method_eligibility.parquet",
                "corrections/correction_metrics.parquet",
                "corrections/effect_retention.parquet",
                "exports/corrected_data.json",
                *[str(item) for item in correction_export.get("files", [])],
            ],
        ),
        ReportSection(
            section_id="ground-truth",
            title="Ground-Truth Audit",
            included=ground_truth.supplied,
            summary="Synthetic recovery metrics are reported separately from observational evidence."
            if ground_truth.supplied
            else "Ground truth was not supplied for this run.",
            artifact_links=["ground_truth/recovery_summary.json"] if ground_truth.supplied else [],
            omission_reason=None if ground_truth.supplied else "ground_truth_not_supplied",
        ),
        ReportSection(
            section_id="evidence",
            title="Root-Cause Evidence",
            included=True,
            summary=f"{len(cards)} prioritized, non-causal evidence cards were generated.",
            artifact_links=["interpretation/evidence_cards.json"],
        ),
        ReportSection(
            section_id="reproducibility",
            title="Reproducibility and Downloads",
            included=True,
            summary="Configuration, checksums, software versions, resource telemetry, and analysis artifacts are retained.",
            artifact_links=[
                "run.json",
                "resolved_config.yaml",
                "input_checksums.json",
                "telemetry/resources.json",
            ],
        ),
    ]
    method = str(recommendation["method"])
    display = {
        "none": "No correction",
        "residualize": "Covariate-aware residualization",
        "combat": "ComBat-style location/scale harmonization",
    }.get(method, method)
    model = ReportModel(
        project_name=str(config["project"]["name"]),
        report_title=str(run.get("report_title", "Artifactor analysis")),
        run_fingerprint=str(run["run_fingerprint"]),
        sample_count=int(run["sample_count"]),
        modalities=list(run["modalities"]),
        design=design,
        recommendation_method=method,
        recommendation_display_name=display,
        recommendation_rationale=str(recommendation["rationale"]),
        research_limitation="This research workflow reports associations and testable hypotheses; it does not establish clinical validity or causal mechanisms.",
        metric_registry=METRIC_REGISTRY,
        factor_highlights=sorted(
            factors,
            key=lambda item: (item.classification == "unexplained", -item.variance_explained),
        )[:12],
        evidence_cards=cards,
        ground_truth=ground_truth,
        sections=sections,
        provenance=run,
    )
    source_paths = sorted(
        {
            link
            for section in sections
            for link in section.artifact_links
            if (run_dir / link).is_file()
        }
    )
    policy_path = run_dir / "provenance/report_policy.json"
    policy = (
        _json(policy_path).get("visualization_sampling_policy", "all persisted visualization rows")
        if policy_path.exists()
        else "all persisted visualization rows"
    )
    manifest = ReportManifest(
        generated_at=pd.Timestamp.now(tz="UTC").to_pydatetime(),
        run_fingerprint=model.run_fingerprint,
        source_artifact_checksums={
            relative: checksum(run_dir / relative) for relative in source_paths
        },
        included_sections=[section.section_id for section in sections if section.included],
        omitted_sections={
            section.section_id: str(section.omission_reason)
            for section in sections
            if not section.included
        },
        software_version=__version__,
        visualization_sampling_policy=str(policy),
    )
    write_json(model.model_dump(mode="json"), run_dir / "report/report_model.json")
    write_json(manifest.model_dump(mode="json"), run_dir / "report/report_manifest.json")
    return model, manifest
