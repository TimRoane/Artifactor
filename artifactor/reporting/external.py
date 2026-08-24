from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

STYLE = """body{font-family:system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#172033}h1,h2{color:#173b57}.card{border:1px solid #ccd6df;border-radius:8px;padding:1rem;margin:1rem 0}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{border:1px solid #dce3e9;padding:.45rem;text-align:left}.warning{background:#fff4d6;border-left:5px solid #d68b00;padding:1rem}.status{font-weight:700}"""


def build_external_report(run: Path) -> Path:
    source = run / "external_validation"
    identity = json.loads((source / "dataset_identity.json").read_text(encoding="utf-8"))
    conclusion = json.loads((source / "validation_conclusion.json").read_text(encoding="utf-8"))
    questions = pd.read_parquet(source / "validation_questions.parquet")
    comparison = pd.read_parquet(source / "source_study_comparison.parquet")
    preparation = json.loads((source / "preparation_manifest.json").read_text(encoding="utf-8"))
    deviations = json.loads((source / "deviation_log.json").read_text(encoding="utf-8"))
    report_dir = run / "report"
    report_dir.mkdir(exist_ok=True)
    destination = report_dir / "external-validation-report.html"
    warnings = preparation.get("warnings", [])
    body = f"""<!doctype html><html><head><meta charset='utf-8'><title>Artifactor external validation</title><style>{STYLE}</style></head><body>
<h1>Artifactor external validation</h1><p>Research-use-only evidence report · schema 4.0</p>
<div class='card'><h2>Dataset identity</h2><p><b>{html.escape(identity['dataset_id'])}</b> · {html.escape(identity['source_snapshot'])} · tier {html.escape(identity['tier'])}</p><p>Preparation fingerprint: <code>{identity['preparation_fingerprint']}</code></p></div>
<div class='card'><h2>Validation conclusion</h2><p class='status'>{html.escape(conclusion['status'])}</p><p>{html.escape(conclusion['status_reason'])}</p><p>Correction eligible: <b>{str(conclusion['correction_eligible']).lower()}</b> — {html.escape(conclusion['correction_reason'])}</p></div>
<h2>Preregistered questions</h2>{questions[['question_id', 'title', 'result_status', 'result_summary', 'evidence_level']].to_html(index=False, escape=True)}
<h2>Source-study comparison</h2>{comparison.to_html(index=False, escape=True)}
<h2>Preparation limitations</h2><div class='warning'>{'<br>'.join(html.escape(item) for item in warnings) or 'None recorded.'}</div>
<h2>Deviation log</h2><pre>{html.escape(json.dumps(deviations, indent=2))}</pre>
<p>Generated exclusively from persisted machine-readable artifacts. A presentation layer cannot upgrade the mechanically derived conclusion.</p></body></html>"""
    destination.write_text(body, encoding="utf-8")
    return destination


def build_benchmark_report(run: Path) -> Path:
    source = run / "benchmarks" if (run / "benchmarks").exists() else run
    resources = pd.read_parquet(source / "run_resources.parquet")
    conclusion = json.loads((source / "benchmark_conclusion.json").read_text(encoding="utf-8"))
    report_dir = run / "report"
    report_dir.mkdir(exist_ok=True)
    destination = report_dir / "benchmark-report.html"
    body = f"<!doctype html><html><head><meta charset='utf-8'><title>Artifactor benchmark</title><style>{STYLE}</style></head><body><h1>Artifactor benchmark report</h1><p>Measured resource evidence; estimates are never labeled observed cost.</p><div class='card'><pre>{html.escape(json.dumps(conclusion, indent=2))}</pre></div>{resources.to_html(index=False, escape=True)}<p>Scientific parity is a prerequisite for cost-performance comparisons.</p></body></html>"
    destination.write_text(body, encoding="utf-8")
    return destination
