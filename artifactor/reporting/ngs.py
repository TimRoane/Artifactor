# mypy: ignore-errors
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio
import yaml

from artifactor import __version__
from artifactor.contracts import (
    DesignSummary,
    EvidenceCard,
    GroundTruthSummary,
    ReportManifest,
    ReportModel,
    ReportSection,
)
from artifactor.evaluation import METRIC_REGISTRY
from artifactor.io import checksum, write_json

REPORT_COLORS = [
    "#2563EB",
    "#DC2626",
    "#059669",
    "#7C3AED",
    "#EA580C",
    "#0891B2",
    "#DB2777",
    "#65A30D",
]

REQUIRED_NGS_ARTIFACTS = (
    "run.json",
    "resolved_config.yaml",
    "ngs/validation_summary.json",
    "design/design_summary.json",
    "ngs/sample_qc_summary.parquet",
    "ngs/callability_summary.parquet",
    "ngs/coverage_model_results.parquet",
    "ngs/coverage_factor_scores.parquet",
    "ngs/coverage_representation_metrics.parquet",
    "ngs/variant_callable_status.parquet",
    "ngs/sequence_context_summary.parquet",
    "interpretation/evidence_cards.json",
    "interpretation/recommendation.json",
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_ngs_report_model(run_dir: Path) -> tuple[ReportModel, ReportManifest]:
    missing = [item for item in REQUIRED_NGS_ARTIFACTS if not (run_dir / item).exists()]
    if missing:
        raise ValueError(
            f"Targeted-NGS report evidence is incomplete; missing artifacts: {', '.join(missing)}"
        )
    run = _read_json(run_dir / "run.json")
    validation = _read_json(run_dir / "ngs/validation_summary.json")
    design = DesignSummary.model_validate(_read_json(run_dir / "design/design_summary.json"))
    recommendation = _read_json(run_dir / "interpretation/recommendation.json")
    cards = [
        EvidenceCard.model_validate(row)
        for row in _read_json(run_dir / "interpretation/evidence_cards.json")
    ]
    config = yaml.safe_load((run_dir / "resolved_config.yaml").read_text(encoding="utf-8"))
    coverage_truth_path = run_dir / "ground_truth/ngs_coverage_recovery.json"
    variant_truth_path = run_dir / "ground_truth/ngs_variant_recovery.json"
    truth_supplied = coverage_truth_path.exists() or variant_truth_path.exists()
    ground_truth = GroundTruthSummary(
        supplied=truth_supplied,
        omission_reason=None if truth_supplied else "ground_truth_not_supplied",
    )
    sections = [
        ReportSection(
            section_id="decision",
            title="Decision Overview",
            included=True,
            summary=str(recommendation["rationale"]),
            artifact_links=["interpretation/recommendation.json", "ngs/validation_summary.json"],
        ),
        ReportSection(
            section_id="design",
            title="Design and Callability",
            included=True,
            summary=design.summary_text,
            artifact_links=[
                "design/design_summary.json",
                "design/pairwise_identifiability.parquet",
                "ngs/callability_summary.parquet",
                "ngs/common_target_universe.parquet",
                "ngs/detection_opportunity.parquet",
            ],
        ),
        ReportSection(
            section_id="factors",
            title="NGS QC and Coverage Factors",
            included=True,
            summary="Sample QC, count-aware offset-normalized factors, target attribution, and GC behavior are linked below.",
            artifact_links=[
                "ngs/sample_qc_summary.parquet",
                "ngs/sample_qc_associations.parquet",
                "ngs/coverage_factor_scores.parquet",
                "ngs/coverage_factor_loadings.parquet",
                "ngs/coverage_factor_associations.parquet",
                "ngs/coverage_model_results.parquet",
                "ngs/gc_bias_curves.parquet",
            ],
        ),
        ReportSection(
            section_id="corrections",
            title="Coverage Mitigation and Variant Diagnostics",
            included=True,
            summary="Coverage representations are exploratory; allele counts, VAF observations, and existing call states remain unchanged.",
            artifact_links=[
                "ngs/coverage_representation_metrics.parquet",
                "ngs/coverage_representation_eligibility.parquet",
                "ngs/target_effect_retention.parquet",
                "ngs/evaluation_boundary.json",
                "ngs/variant_model_results.parquet",
                "ngs/variant_callable_status.parquet",
                "ngs/sequence_context_summary.parquet",
                "ngs/strand_bias_results.parquet",
                "ngs/orientation_bias_results.parquet",
                "ngs/read_support_diagnostics.parquet",
                "ngs/control_recovery.parquet",
                "ngs/replicate_agreement.parquet",
            ],
        ),
        ReportSection(
            section_id="ground-truth",
            title="Ground-Truth Audit",
            included=truth_supplied,
            summary="Simulator or declared truth recovery is reported separately from observational evidence."
            if truth_supplied
            else "Ground truth was not supplied.",
            artifact_links=[
                item
                for item in (
                    "ground_truth/ngs_coverage_recovery.json",
                    "ground_truth/ngs_variant_recovery.json",
                )
                if (run_dir / item).exists()
            ],
            omission_reason=None if truth_supplied else "ground_truth_not_supplied",
        ),
        ReportSection(
            section_id="evidence",
            title="Root-Cause Evidence",
            included=True,
            summary=f"{len(cards)} targeted-NGS evidence cards prioritize design safety and assay follow-up.",
            artifact_links=["interpretation/evidence_cards.json"],
        ),
        ReportSection(
            section_id="reproducibility",
            title="Reproducibility and Downloads",
            included=True,
            summary="Reference build, panel/pipeline provenance, annotations, model parameters, seed, and checksums are retained.",
            artifact_links=[
                "run.json",
                "resolved_config.yaml",
                "input_checksums.json",
                "ngs/ngs_capabilities.json",
                "provenance/run_manifest.json",
                "telemetry/resources.json",
            ],
        ),
    ]
    ngs_summary = {
        "reference_build": validation["reference_build"],
        "target_count": validation["target_count"],
        "variant_count": validation["variant_count"],
        "panel_versions": validation["panel_versions"],
        "coverage_representation": recommendation["method"],
        "variant_statement": "Original genomic observations and call states are unchanged. Any normalized or residual representation is exploratory and must be validated before downstream use.",
        "analysis_budget": config.get("analysis", {}).get("analysis_budget", "standard"),
        "coverage_truth": _read_json(coverage_truth_path) if coverage_truth_path.exists() else None,
        "variant_truth": _read_json(variant_truth_path) if variant_truth_path.exists() else None,
    }
    model = ReportModel(
        project_name=config["project"]["name"],
        report_title=run["report_title"],
        run_fingerprint=run["run_fingerprint"],
        sample_count=run["sample_count"],
        modalities=run["modalities"],
        design=design,
        recommendation_method=recommendation["method"],
        recommendation_display_name=recommendation["method"].replace("_", " ").title(),
        recommendation_rationale=recommendation["rationale"],
        research_limitation="Research use only. Artifactor analyzes analysis-ready targeted-NGS summary tables; it does not process reads, call variants, rewrite observations, establish causation, or provide clinical validation.",
        metric_registry=METRIC_REGISTRY,
        factor_highlights=[],
        evidence_cards=cards,
        ground_truth=ground_truth,
        sections=sections,
        provenance=run,
        analysis_type="targeted_ngs",
        ngs_summary=ngs_summary,
    )
    source_paths = sorted(
        {
            link
            for section in sections
            for link in section.artifact_links
            if (run_dir / link).is_file()
        }
    )
    manifest = ReportManifest(
        generated_at=pd.Timestamp.now(tz="UTC").to_pydatetime(),
        run_fingerprint=model.run_fingerprint,
        source_artifact_checksums={item: checksum(run_dir / item) for item in source_paths},
        included_sections=[item.section_id for item in sections if item.included],
        omitted_sections={
            item.section_id: str(item.omission_reason) for item in sections if not item.included
        },
        software_version=__version__,
        visualization_sampling_policy="Persisted compact NGS summaries and bounded factor/VAF samples; no full count matrix is embedded.",
    )
    write_json(model.model_dump(mode="json"), run_dir / "report/report_model.json")
    write_json(manifest.model_dump(mode="json"), run_dir / "report/report_manifest.json")
    return model, manifest


def _table(frame: pd.DataFrame, limit: int = 100) -> str:
    return (
        frame.drop(columns=["schema_version"], errors="ignore")
        .head(limit)
        .to_html(index=False, border=0, classes="data")
    )


def _links(items: list[str]) -> str:
    return "".join(
        f'<li><a download href="../{html.escape(item)}">{html.escape(item)}</a></li>'
        for item in items
    )


def build_ngs_report(run_dir: Path, standalone: bool = True) -> Path:
    model, manifest = build_ngs_report_model(run_dir)
    validation = _read_json(run_dir / "ngs/validation_summary.json")
    callability = pd.read_parquet(run_dir / "ngs/callability_summary.parquet")
    qc_associations = pd.read_parquet(run_dir / "ngs/sample_qc_associations.parquet")
    scores = pd.read_parquet(run_dir / "ngs/coverage_factor_scores.parquet")
    coverage_models = pd.read_parquet(run_dir / "ngs/coverage_model_results.parquet")
    representation_metrics = pd.read_parquet(
        run_dir / "ngs/coverage_representation_metrics.parquet"
    )
    variant_status = pd.read_parquet(run_dir / "ngs/variant_callable_status.parquet")
    context = pd.read_parquet(run_dir / "ngs/sequence_context_summary.parquet")
    control = pd.read_parquet(run_dir / "ngs/control_recovery.parquet")
    replicate = pd.read_parquet(run_dir / "ngs/replicate_agreement.parquet")
    pc = (
        scores.pivot(index="sample_id", columns="factor", values="score")
        .reset_index()
        .merge(
            scores.drop_duplicates("sample_id").drop(
                columns=["factor", "score", "variance_explained"]
            ),
            on="sample_id",
        )
    )
    color = model.design.technical_variables[0]
    factor_figure = px.scatter(
        pc,
        x="PC1",
        y="PC2",
        color=color,
        title=f"Count-aware offset-normalized coverage factors colored by {color}",
        template="plotly_white",
        color_discrete_sequence=REPORT_COLORS,
    )
    factor_html = pio.to_html(
        factor_figure,
        full_html=False,
        include_plotlyjs="inline" if standalone else "cdn",
        config={"responsive": True},
    )
    frontier = px.scatter(
        representation_metrics,
        x="technical_removal",
        y="biological_loss",
        color="representation",
        title="Exploratory coverage mitigation frontier",
        template="plotly_white",
        color_discrete_sequence=REPORT_COLORS,
    )
    frontier_html = pio.to_html(
        frontier, full_html=False, include_plotlyjs=False, config={"responsive": True}
    )
    vaf_sample = variant_status[(variant_status.total_depth > 0)].head(3000)
    vaf_figure = px.scatter(
        vaf_sample,
        x="total_depth",
        y="observed_vaf",
        color="callability_status",
        hover_data=["alt_count", "variant_id", "existing_call_state"],
        title="Observed VAF with alternate-count and depth context",
        template="plotly_white",
        color_discrete_sequence=REPORT_COLORS,
    )
    vaf_html = pio.to_html(
        vaf_figure, full_html=False, include_plotlyjs=False, config={"responsive": True}
    )
    cards = "".join(
        f'<article class="card"><span class="status {card.severity}">{html.escape(card.severity.upper())}</span><h3>{html.escape(card.title)}</h3><p>{html.escape(card.observation)}</p><h4>Alternatives</h4><ul>{"".join(f"<li>{html.escape(x)}</li>" for x in card.alternative_explanations)}</ul><h4>Limitations</h4><ul>{"".join(f"<li>{html.escape(x)}</li>" for x in card.limitations)}</ul><h4>Testable follow-up</h4><p>{html.escape(card.recommended_follow_ups[0].experiment)}</p><ul>{_links(card.artifact_links)}</ul></article>'
        for card in model.evidence_cards
    )
    truth = '<p class="omitted">Not included: ground_truth_not_supplied.</p>'
    if model.ground_truth.supplied:
        truth = f"<h3>Coverage truth</h3><pre>{html.escape(json.dumps(model.ngs_summary.get('coverage_truth'), indent=2))}</pre><h3>Variant truth</h3><pre>{html.escape(json.dumps(model.ngs_summary.get('variant_truth'), indent=2))}</pre>"
    sections = {item.section_id: item for item in model.sections}
    nav = "".join(
        f'<a href="#{item.section_id}">{html.escape(item.title)}</a>' for item in model.sections
    )
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(model.report_title)}</title><style>:root{{--ink:#17212b;--muted:#53606d;--bg:#f5f7f9;--accent:#176b5b;--line:#d8dee4}}*{{box-sizing:border-box}}body{{margin:0;font:16px/1.55 system-ui;color:var(--ink);background:var(--bg)}}nav{{position:sticky;top:0;background:white;border-bottom:1px solid var(--line);padding:.75rem;display:flex;gap:1rem;overflow:auto;z-index:10}}nav a{{color:var(--accent);font-weight:700;white-space:nowrap}}main{{max-width:1200px;margin:auto;padding:1.5rem}}header,section{{background:white;border:1px solid var(--line);border-radius:12px;padding:1.4rem;margin-bottom:1.2rem}}header{{background:#e8f5f1}}.safety{{border:2px solid #9b1c1c;padding:1rem;font-weight:700}}.status{{border:1px solid currentColor;border-radius:1rem;padding:.15rem .5rem;font-size:.75rem;font-weight:800}}.high{{color:#9b1c1c}}.warning{{color:#8a4b08}}.info{{color:#176b5b}}.card{{border-left:4px solid var(--accent);padding:1rem;margin:1rem 0;background:#fbfcfd}}table.data{{border-collapse:collapse;width:100%;display:block;overflow:auto}}.data th,.data td{{padding:.45rem;border:1px solid var(--line);text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}@media print{{nav{{display:none}}}}</style></head><body><nav aria-label="Report sections">{nav}</nav><main><header><h1>{html.escape(model.report_title)}</h1><p><strong>{html.escape(model.recommendation_display_name)}</strong> — {html.escape(model.recommendation_rationale)}</p><p class="safety">{html.escape(model.ngs_summary["variant_statement"])}</p><p>{html.escape(model.research_limitation)}</p><small>Run {html.escape(model.run_fingerprint)} · {model.sample_count} samples · {validation["target_count"]} targets · {validation["variant_count"]} monitored variants · budget {html.escape(model.ngs_summary["analysis_budget"])}</small></header>
<section id="decision"><h2>Decision Overview</h2><p>{html.escape(model.recommendation_rationale)}</p><dl><dt>Reference build</dt><dd>{html.escape(validation["reference_build"])}</dd><dt>Panel versions</dt><dd>{html.escape(", ".join(validation["panel_versions"]))}</dd><dt>Design</dt><dd>{html.escape(model.design.overall_status)}</dd></dl></section>
<section id="design"><h2>Design and Callability</h2><p>{html.escape(model.design.summary_text)}</p><p>Structural panel absence is excluded from numeric zero coverage. Insufficient depth is not interpreted as a negative event.</p>{_table(callability)}</section>
<section id="factors"><h2>NGS QC and Coverage Factors</h2><p>These are derived diagnostic representations. Raw target counts are unchanged. PC1 and PC2 are observed axes, not inherently biological or technical.</p>{factor_html}<h3>QC associations</h3>{_table(qc_associations)}<h3>Target-level negative-binomial evidence</h3>{_table(coverage_models)}</section>
<section id="corrections"><h2>Coverage Mitigation and Variant Diagnostics</h2><p>Coverage candidates are exploratory representations, not replacement observations. VAF is always displayed with alternate counts and total depth.</p>{frontier_html}{_table(representation_metrics)}{vaf_html}<h3>Sequence-context spectrum</h3>{_table(context)}<h3>Control recovery</h3>{_table(control)}<h3>Replicate agreement</h3>{_table(replicate)}</section>
<section id="ground-truth"><h2>Ground-Truth Audit</h2>{truth}</section><section id="evidence"><h2>Root-Cause Evidence</h2><p>Findings are associations and testable assay hypotheses; no card instructs automatic call deletion.</p>{cards}</section>
<section id="reproducibility"><h2>Reproducibility and Downloads</h2><p>{html.escape(manifest.visualization_sampling_policy)}</p><ul>{_links(sections["reproducibility"].artifact_links + ["report/report_model.json", "report/report_manifest.json"])}</ul><details><summary>Run manifest</summary><pre>{html.escape(json.dumps(model.provenance, indent=2))}</pre></details></section></main></body></html>"""
    destination = run_dir / "report/artifactor-report.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
    (run_dir / "report/index.html").write_text(document, encoding="utf-8")
    return destination
