from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio

from .model import build_report_model

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


def _table(frame: pd.DataFrame, limit: int = 100) -> str:
    return (
        frame.drop(columns=["schema_version"], errors="ignore")
        .head(limit)
        .to_html(index=False, border=0, classes="data")
    )


def _artifact_links(links: list[str]) -> str:
    return "".join(
        f'<li><a download href="../{html.escape(link)}">{html.escape(link)}</a></li>'
        for link in links
    )


def build_report(run_dir: Path, standalone: bool = True) -> Path:
    if (run_dir / "ngs/validation_summary.json").exists():
        from .ngs import build_ngs_report

        return build_ngs_report(run_dir, standalone=standalone)
    model, manifest = build_report_model(run_dir)
    eligibility = pd.read_parquet(run_dir / "corrections/method_eligibility.parquet")
    metrics = pd.read_parquet(run_dir / "evaluation/method_metrics.parquet")
    factors = pd.read_parquet(run_dir / "factors/factor_summary.parquet")
    factor_scores = pd.read_parquet(run_dir / "factors/factor_scores.parquet")
    pairwise = pd.read_parquet(run_dir / "design/pairwise_identifiability.parquet")
    cells = pd.read_parquet(run_dir / "design/contingency_cells.parquet")
    correction_sample = pd.read_parquet(run_dir / "corrections/visualization_samples.parquet")
    correction_export_path = run_dir / "exports/corrected_data.json"
    correction_export = (
        json.loads(correction_export_path.read_text(encoding="utf-8"))
        if correction_export_path.exists()
        else {"status": "not_generated", "reason": "This older run has no corrected-data export manifest.", "files": []}
    )
    if correction_export["status"] == "available":
        export_notice = (
            '<div class="download"><h3>Corrected data are available</h3><p>'
            + html.escape(str(correction_export["reason"]))
            + "</p><ul>"
            + _artifact_links([str(item) for item in correction_export["files"]])
            + "</ul></div>"
        )
    else:
        export_notice = (
            '<div class="omitted"><h3>No corrected dataset generated</h3><p>'
            + html.escape(str(correction_export["reason"]))
            + "</p></div>"
        )
    figure = px.scatter(
        metrics,
        x="technical_removal",
        y="biological_loss",
        color="method",
        hover_data=["biological_retention", "cross_modal_concordance"],
        title="Technical-signature reduction versus declared-biological loss",
        template="plotly_white",
        color_discrete_sequence=REPORT_COLORS,
    )
    plot_html = pio.to_html(
        figure,
        full_html=False,
        include_plotlyjs=False,
        config={"responsive": True},
    )
    first_modality = str(factor_scores.modality.iloc[0])
    score_metadata = factor_scores[factor_scores.modality == first_modality].drop_duplicates(
        "sample_id"
    )
    wide_scores = (
        factor_scores[factor_scores.modality == first_modality]
        .pivot(index="sample_id", columns="factor", values="score")
        .reset_index()
    )
    wide_scores = wide_scores.merge(
        score_metadata.drop(columns=["modality", "factor", "score"]), on="sample_id"
    )
    color_variable = (model.design.biological_variables + model.design.technical_variables)[0]
    factor_figure = px.scatter(
        wide_scores,
        x="PC1",
        y="PC2",
        color=color_variable,
        title=f"{first_modality}: first two observed axes colored by {color_variable}",
        template="plotly_white",
        color_discrete_sequence=REPORT_COLORS,
    )
    factor_plot_html = pio.to_html(
        factor_figure,
        full_html=False,
        include_plotlyjs="inline" if standalone else "cdn",
        config={"responsive": True},
    )
    correction_color = model.design.technical_variables[0]
    correction_figure = px.scatter(
        correction_sample,
        x="pc1",
        y="pc2",
        color=correction_color,
        facet_col="method",
        facet_row="modality",
        title=f"Saved before/after views colored by {correction_color}",
        template="plotly_white",
        color_discrete_sequence=REPORT_COLORS,
    )
    correction_plot_html = pio.to_html(
        correction_figure, full_html=False, include_plotlyjs=False, config={"responsive": True}
    )
    section_map = {section.section_id: section for section in model.sections}
    cards = "".join(
        f'<article class="card"><span class="status {card.severity}">{html.escape(card.severity.upper())}</span><h3>{html.escape(card.title)}</h3><p>{html.escape(card.observation)}</p><h4>Alternative explanations</h4><ul>{"".join(f"<li>{html.escape(x)}</li>" for x in card.alternative_explanations)}</ul><h4>Limitations</h4><ul>{"".join(f"<li>{html.escape(x)}</li>" for x in card.limitations)}</ul><h4>Recommended follow-up</h4><p>{html.escape(card.recommended_follow_ups[0].experiment)} — balance {html.escape(card.recommended_follow_ups[0].variable_to_balance)}.</p><h4>Supporting artifacts</h4><ul>{_artifact_links(card.artifact_links)}</ul></article>'
        for card in model.evidence_cards
    )
    truth = ""
    if model.ground_truth.supplied:
        summary = json.loads(
            (run_dir / "ground_truth/recovery_summary.json").read_text(encoding="utf-8")
        )
        truth = f'<dl class="metrics">{"".join(f"<dt>{html.escape(str(k))}</dt><dd>{html.escape(str(v))}</dd>" for k, v in summary.items() if k != "by_modality")}</dl>'
        injected = pd.read_parquet(run_dir / "ground_truth/injected_vs_estimated.parquet")
        truth_figure = px.scatter(
            injected,
            x="injected_technical_effect",
            y="estimated_technical_effect",
            color="modality",
            title="Injected versus estimated technical effects",
            template="plotly_white",
            color_discrete_sequence=REPORT_COLORS,
        )
        truth += pio.to_html(
            truth_figure, full_html=False, include_plotlyjs=False, config={"responsive": True}
        )
    else:
        truth = '<p class="omitted">Not included: ground_truth_not_supplied. This section is available for synthetic benchmark runs only.</p>'
    nav = "".join(f'<a href="#{s.section_id}">{html.escape(s.title)}</a>' for s in model.sections)
    metric_definitions = "".join(
        f"<article><h3>{html.escape(item.display_name)}</h3><p>{html.escape(item.short_definition)}</p><small>Direction: {html.escape(item.direction)}. {html.escape(item.baseline_interpretation)}</small></article>"
        for item in model.metric_registry.values()
    )
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(model.report_title)}</title>
<style>:root{{--ink:#17212b;--muted:#53606d;--bg:#f6f8fa;--accent:#176b5b;--line:#d8dee4}}*{{box-sizing:border-box}}body{{margin:0;font:16px/1.55 system-ui;color:var(--ink);background:var(--bg)}}nav{{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);padding:.8rem;z-index:10;display:flex;gap:1rem;overflow:auto}}nav a{{color:var(--accent);font-weight:650;white-space:nowrap}}main{{max-width:1180px;margin:auto;padding:1.5rem}}section,header{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:1.4rem;margin:0 0 1.25rem}}header{{background:#eaf5f2}}h1,h2,h3{{line-height:1.2}}.status{{font-size:.75rem;font-weight:800;border:1px solid currentColor;border-radius:1rem;padding:.15rem .5rem}}.high{{color:#9b1c1c}}.warning{{color:#8a4b08}}.info{{color:#176b5b}}.card{{border-left:4px solid var(--accent);padding:1rem;margin:1rem 0;background:#fbfcfd}}.download{{border:2px solid var(--accent);background:#eaf5f2;border-radius:8px;padding:1rem;margin:1rem 0}}table.data{{border-collapse:collapse;width:100%;display:block;overflow:auto}}.data th,.data td{{padding:.45rem;border:1px solid var(--line);text-align:left}}.omitted{{border:1px dashed var(--muted);padding:1rem}}dl.metrics{{display:grid;grid-template-columns:minmax(12rem,1fr) 2fr;gap:.35rem}}dt{{font-weight:700}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}small{{color:var(--muted)}}@media print{{nav{{display:none}}section{{break-inside:avoid}}}}</style></head><body>
<nav aria-label="Report sections">{nav}</nav><main><header><h1>{html.escape(model.report_title)}</h1><p><strong>{html.escape(model.recommendation_display_name)}</strong> — {html.escape(model.recommendation_rationale)}</p><p>{html.escape(model.research_limitation)}</p><small>Run {html.escape(model.run_fingerprint)} · {model.sample_count} samples · {html.escape(", ".join(model.modalities))}</small></header>
<section id="decision"><h2>Decision Overview</h2><p>{html.escape(model.recommendation_rationale)}</p>{_table(eligibility)}<h3>Metric definitions</h3>{metric_definitions}</section>
<section id="design"><h2>Study-Design Audit</h2><p><span class="status {"info" if model.design.correction_permitted else "high"}">{html.escape(model.design.overall_status.upper())}</span> {html.escape(model.design.summary_text)}</p>{_table(pairwise)}<h3>Observed design cells</h3><p>Counts and expected counts show where biological and technical levels have independent support.</p>{_table(cells)}</section>
<section id="factors"><h2>Factor Explorer</h2><p>PC1 is the largest observed axis of variation and PC2 is the next independent axis; neither is inherently biological or technical. Classifications combine declared-metadata association strength with sign-invariant bootstrap stability.</p>{factor_plot_html}{_table(factors)}</section>
<section id="corrections"><h2>Correction Comparison and corrected data</h2>{export_notice}<p>Lower technical predictability is evaluated alongside retention of declared biology and mapped cross-modal concordance. The first chart is the decision frontier; the faceted sample view shows how the saved representation changed.</p>{plot_html}{correction_plot_html}{_table(metrics)}</section>
<section id="ground-truth"><h2>Ground-Truth Audit</h2>{truth}</section>
<section id="evidence"><h2>Root-Cause Evidence</h2><p>These are observational findings and testable hypotheses, not causal conclusions.</p>{cards}</section>
<section id="reproducibility"><h2>Reproducibility and Downloads</h2><p>Visualization policy: {html.escape(manifest.visualization_sampling_policy)}</p><ul>{_artifact_links(section_map["reproducibility"].artifact_links + ["report/report_model.json", "report/report_manifest.json"])}</ul><details><summary>Run manifest</summary><pre>{html.escape(json.dumps(model.provenance, indent=2))}</pre></details></section>
</main></body></html>"""
    destination = run_dir / "report/artifactor-report.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(doc, encoding="utf-8")
    (run_dir / "report/index.html").write_text(doc, encoding="utf-8")
    return destination
