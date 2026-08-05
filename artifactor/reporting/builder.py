from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import plotly.express as px


def build_report(run_dir: Path) -> Path:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    recommendation = json.loads(
        (run_dir / "evaluation/recommendation.json").read_text(encoding="utf-8")
    )
    findings = json.loads((run_dir / "interpretation/findings.json").read_text(encoding="utf-8"))
    metrics = pd.read_parquet(run_dir / "evaluation/method_metrics.parquet")
    plot = px.scatter(
        metrics,
        x="technical_removal",
        y="biological_loss",
        color="method",
        title="Technical removal versus biological loss",
    )
    plot_html = plot.to_html(full_html=False, include_plotlyjs=True)
    cards = "".join(
        f"<article><h3>{html.escape(item['title'])}</h3><p>{html.escape(item['interpretation'])}</p><p><b>Limitation:</b> {html.escape(item['limitation'])}</p><p><b>Follow-up:</b> {html.escape(item['follow_up'])}</p></article>"
        for item in findings
    )
    document = f"""<!doctype html><html><head><meta charset='utf-8'><title>Artifactor report</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#17212b}}header{{background:#eef7f3;padding:1.5rem;border-radius:12px}}article{{border-left:4px solid #2e7d6e;padding:.25rem 1rem;margin:1.5rem 0}}table{{border-collapse:collapse}}td,th{{padding:.5rem;border:1px solid #ccd}}.warning{{color:#8a4b08}}</style></head><body>
<header><h1>{html.escape(run.get("report_title", "Artifactor analysis"))}</h1><p><b>Decision:</b> {html.escape(str(recommendation["method"]))}</p><p>{html.escape(str(recommendation["rationale"]))}</p><p>This research prototype reports associations and hypotheses, not clinical or causal conclusions.</p></header>
<h2>Biological Preservation Audit</h2>{plot_html}{metrics.to_html(index=False)}
<h2>Prioritized findings</h2>{cards}
<h2>Reproducibility</h2><pre>{html.escape(json.dumps(run, indent=2))}</pre></body></html>"""
    destination = run_dir / "report/index.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
    return destination
