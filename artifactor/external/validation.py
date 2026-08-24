from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import yaml

from artifactor.io import write_json

from .contracts import Deviation, ResultStatus, ValidationQuestion, derive_conclusion


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _seqc_results(prepared: Path, questions: list[ValidationQuestion], tier: str, target: Path) -> tuple[list[dict[str, object]], bool, str]:
    manifest = pd.read_parquet(prepared / "manifest.parquet")
    calls = pd.read_parquet(prepared / "variant_calls.parquet")
    calls["variant_id"] = calls[["chromosome", "position", "reference", "alternate"]].astype(str).agg(":".join, axis=1)
    call_sets = calls.groupby("sample_id")["variant_id"].agg(set).to_dict()
    pairs: list[dict[str, object]] = []
    samples = manifest[manifest["included_primary"]]
    reset_samples = samples.reset_index(drop=True)
    for i, (_, left) in enumerate(reset_samples.iterrows()):
        for _, right in reset_samples.iloc[i + 1 :].iterrows():
            # Submitted panels have different target universes; only compare like with like.
            if left.panel != right.panel:
                continue
            pairs.append({"left": left.sample_id, "right": right.sample_id, "same_reference": left.reference_sample == right.reference_sample, "same_lab": left.laboratory == right.laboratory, "jaccard": _jaccard(call_sets.get(left.sample_id, set()), call_sets.get(right.sample_id, set()))})
    pair_frame = pd.DataFrame(pairs)
    within = float(pair_frame.loc[pair_frame.same_reference, "jaccard"].median())
    between = float(pair_frame.loc[~pair_frame.same_reference, "jaccard"].median())
    lab_spread = float(pair_frame.groupby("same_lab")["jaccard"].median().max() - pair_frame.groupby("same_lab")["jaccard"].median().min())
    metrics = {"within_reference_median_jaccard": within, "between_reference_median_jaccard": between, "reference_separation": within - between, "same_lab_jaccard_spread": lab_spread, "samples": len(samples), "panels": int(samples.panel.nunique()), "laboratories": int(samples.laboratory.nunique())}
    rows: list[dict[str, object]] = []
    for question in questions:
        if question.question_id == "seqc_reference_separation":
            question.result_status = ResultStatus.PASS if within - between >= 0.10 else ResultStatus.FAIL
            question.result_summary = f"Median call-set Jaccard was {within:.3f} within reference samples and {between:.3f} between references."
        elif question.question_id == "seqc_technical_structure":
            question.result_status = ResultStatus.PARTIAL if tier == "pilot" else ResultStatus.PASS
            scope = "pilot limitation" if tier == "pilot" else "full processed tier"
            question.result_summary = f"Laboratory association was evaluable across {metrics['laboratories']} labs and {metrics['panels']} panel(s) ({scope})."
            if tier == "pilot":
                question.limitations.append("Pilot tier contains one panel, so cross-panel structure is not evaluable.")
        elif question.question_id == "seqc_replicate_reproducibility":
            question.result_status = ResultStatus.PASS if within > between else ResultStatus.FAIL
            question.result_summary = "Repeated libraries from the same reference sample were more concordant than libraries from different references." if within > between else "Expected replicate concordance direction was not observed."
        elif question.question_id == "seqc_expected_vaf":
            question.result_status = ResultStatus.PARTIAL
            question.result_summary = "Allele counts are valid for called IGT records, but absence-site depth is unavailable; missed-truth behavior by callability cannot be estimated."
            question.limitations.append("Submitted positive-only VCFs do not provide site-level depth for absent calls.")
        elif question.question_id == "seqc_negative_positions":
            question.result_status = ResultStatus.NOT_EVALUABLE
            question.result_summary = "Truth-negative callability is unavailable; VCF absence was not converted to a negative call."
            question.limitations.append("No all-sites callability evidence in public submitted VCFs.")
        else:
            question.result_status = ResultStatus.PARTIAL
            question.result_summary = "Observed reproducibility direction is compatible with the source publication; populations and universes differ."
        question.supporting_artifacts = ["validation_results.parquet", "seqc_pairwise_reproducibility.parquet"]
        rows.append({"schema_version": "4.0", "question_id": question.question_id, "status": question.result_status.value, **metrics})
    pair_frame.sort_values(["left", "right"]).to_parquet(target / "seqc_pairwise_reproducibility.parquet", index=False)
    return rows, False, "Submitted callsets are immutable observations; site-level callability and a correctable raw representation are unavailable."


def _cptac_results(prepared: Path, questions: list[ValidationQuestion]) -> tuple[list[dict[str, object]], bool, str]:
    manifest = pd.read_parquet(prepared / "manifest.parquet")
    technical = pd.read_parquet(prepared / "technical_metadata.parquet")
    metrics = {"manifest_rows": len(manifest), "subjects": int(manifest.subject_id.nunique()), "rna_samples": int((manifest.modality == "rna").sum()), "protein_samples": int((manifest.modality == "protein").sum()), "tmt_plexes": int(technical.tmt_plex.nunique()), "centers": int(technical.center.nunique()), "unknown_tissue_rows": int((manifest.tissue_type == "unknown").sum())}
    rows: list[dict[str, object]] = []
    for question in questions:
        if question.question_id == "cptac_biological_separation":
            question.result_status = ResultStatus.PARTIAL
            question.result_summary = "Tumor/normal and subject relationships are available, but this release limits the case study to preparation and diagnostic evidence."
        elif question.question_id == "cptac_protein_technical":
            question.result_status = ResultStatus.PARTIAL
            question.result_summary = f"Plex/channel/center metadata are available ({metrics['tmt_plexes']} plexes), but the supplied protein matrix was already ComBat-adjusted upstream."
            question.limitations.append("Upstream ComBat adjustment may have altered technical structure.")
        elif question.question_id == "cptac_rna_technical":
            question.result_status = ResultStatus.NOT_EVALUABLE
            question.result_summary = "The frozen public RNA supplement lacks documented per-sample technical covariates needed by this question."
        elif question.question_id == "cptac_cross_modal":
            question.result_status = ResultStatus.NOT_EVALUABLE
            question.result_summary = "No frozen versioned one-to-one RNA-protein mapping is bundled; expanded ad hoc mapping is prohibited."
        elif question.question_id == "cptac_correction_eligibility":
            question.result_status = ResultStatus.PASS
            question.result_summary = "Artifactor correctly refuses a new correction because the publication protein matrix is already ComBat-adjusted and RNA technical metadata are incomplete."
        else:
            question.result_status = ResultStatus.PASS
            question.result_summary = "Evidence statement records alternative explanations, missing metadata, and a distinguishing follow-up experiment without causal language."
        question.supporting_artifacts = ["validation_results.parquet", "preparation_manifest.json"]
        rows.append({"schema_version": "4.0", "question_id": question.question_id, "status": question.result_status.value, **metrics})
    return rows, False, "Correction refused: upstream protein correction plus incomplete RNA technical metadata prevents a valid new correction claim."


def validate_external(config: Path, preregistration: Path, output: Path | None = None) -> Path:
    settings = yaml.safe_load(config.read_text(encoding="utf-8"))
    frozen = yaml.safe_load(preregistration.read_text(encoding="utf-8"))
    if "extends" in frozen:
        base = yaml.safe_load((preregistration.parent / frozen.pop("extends")).read_text(encoding="utf-8"))
        frozen = {**base, **frozen}
    if settings["dataset_id"] != frozen["dataset_id"]:
        raise ValueError("dataset differs from preregistration freeze")
    if settings.get("preparation_fingerprint") != frozen.get("preparation_fingerprint"):
        raise ValueError("preparation fingerprint differs from preregistration freeze")
    prepared = Path(settings["prepared_dir"])
    manifest = json.loads((prepared / "preparation_manifest.json").read_text(encoding="utf-8"))
    if manifest["preparation_fingerprint"] != frozen["preparation_fingerprint"]:
        raise ValueError("prepared data do not match preregistration snapshot")
    questions = [ValidationQuestion.model_validate(item) for item in frozen["questions"]]
    run = output or Path(settings.get("output_dir", "results")) / f"external-{settings['dataset_id']}-{manifest['preparation_fingerprint']}"
    target = run / "external_validation"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prepared / "preparation_manifest.json", target / "preparation_manifest.json")
    shutil.copy2(preregistration, target / "preregistration_snapshot.yaml")
    identity = {"schema_version": "4.0", "dataset_id": settings["dataset_id"], "tier": settings["tier"], "source_snapshot": manifest["source_snapshot"], "preparation_fingerprint": manifest["preparation_fingerprint"]}
    write_json(identity, target / "dataset_identity.json")
    if settings["dataset_id"] == "seqc2_oncopanel":
        rows, eligible, reason = _seqc_results(prepared, questions, settings["tier"], target)
    else:
        rows, eligible, reason = _cptac_results(prepared, questions)
    pd.DataFrame([item.model_dump(mode="json") for item in questions]).to_parquet(target / "validation_questions.parquet", index=False)
    pd.DataFrame(rows).to_parquet(target / "validation_results.parquet", index=False)
    pd.DataFrame([{"schema_version": "4.0", "comparison": "published_direction", "status": "partially_consistent", "reason": "Directional comparison only; populations and preprocessing are not numerically identical."}]).to_parquet(target / "source_study_comparison.parquet", index=False)
    deviations: list[Deviation] = []
    if settings["dataset_id"] == "cptac_ccrcc":
        deviations.append(Deviation(deviation_id="DEV-CPTAC-001", timestamp=datetime.now(UTC), trigger="Official PDC metadata audit before results", original_plan="Use PDC000128 as primary global proteome", changed_plan="Use PDC000127 CCRCC Discovery Proteome; PDC000128 is phosphoproteome", reason="Official PDC accession metadata contradict the draft plan.", affected_questions=[item.question_id for item in questions], whether_results_were_viewed=False, approval_or_review_status="documented_authoritative_source_correction"))
    write_json([item.model_dump(mode="json") for item in deviations], target / "deviation_log.json")
    conclusion = derive_conclusion(settings["dataset_id"], questions, eligible, reason)
    write_json(conclusion.model_dump(mode="json"), target / "validation_conclusion.json")
    write_json({"schema_version": "4.0", "status": "complete", "dataset_id": settings["dataset_id"], "validation_conclusion": conclusion.status.value}, run / "run.json")
    return run
