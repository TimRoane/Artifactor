"""Shared presentation components. No analysis or artifact mutation lives here."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st

COLORS = ["#147d74", "#d18a43", "#5276a5", "#9d647d", "#718357", "#8877aa"]
LOGO = '<span class="brand-mark" aria-hidden="true">A<span>·</span></span>'


def setup() -> None:
    st.set_page_config(page_title="Artifactor | Research workspace", page_icon="◈", layout="wide")
    st.set_option("client.toolbarMode", "viewer")
    css = (Path(__file__).parent / "assets/workspace.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")


def brand() -> None:
    st.html(
        f'<div class="brand">{LOGO}<div>artifactor<span>THE RESEARCH WORKSPACE</span></div></div>'
    )


def topbar(label: str) -> None:
    st.html(
        '<div class="workspace-bar"><span>ARTIFACTOR <i>/</i> '
        f'{escape(label.upper())}</span><span class="research-tag">RESEARCH USE ONLY</span></div>'
    )


def page_heading(kicker: str, title: str, description: str) -> None:
    st.html(f'<div class="eyebrow">{escape(kicker)}</div>')
    st.title(title)
    st.markdown(f'<p class="page-description">{escape(description)}</p>', unsafe_allow_html=True)


def hero() -> None:
    # A schematic, intentionally separate from the measured results and their charts.
    cells = "".join(f'<span class="cell c{i % 7}"></span>' for i in range(36))
    st.html(
        '<section class="hero"><div class="hero-copy">'
        '<div class="eyebrow">EVIDENCE BEFORE CORRECTION</div>'
        "<h1>Every signal<br>has a <em>story.</em></h1>"
        "<p>Find what biology and technical processing leave behind. "
        "Know what to preserve, what to investigate, and when to stop.</p>"
        '<div class="hero-foot"><span>01 &nbsp; Audit</span><span>02 &nbsp; Investigate</span>'
        "<span>03 &nbsp; Decide</span></div></div>"
        '<div class="signal-art" role="img" aria-label="Conceptual matrix separating '
        'biological, technical, and unresolved evidence; not measured data.">'
        '<div class="art-label">READING THE SIGNAL</div>'
        f'<div class="matrix">{cells}</div><div class="signal-branches">'
        '<div><b class="dot bio"></b><span>Biological<small>Preserve the question</small></span></div>'
        '<div><b class="dot tech"></b><span>Technical<small>Investigate the process</small></span></div>'
        '<div><b class="dot unknown"></b><span>Unresolved<small>Make uncertainty visible</small></span></div>'
        '</div><div class="art-caption">A CONCEPTUAL VIEW OF VARIATION</div></div></section>'
    )


def section_heading(number: str, title: str, description: str = "") -> None:
    st.html(
        f'<div class="section-heading"><span>{escape(number)}</span><div>'
        f"<h2>{escape(title)}</h2>"
        + (f"<p>{escape(description)}</p>" if description else "")
        + "</div></div>"
    )


def launch_card(number: str, title: str, description: str, tag: str) -> None:
    st.html(
        f'<div class="launch-card"><div class="card-top"><span>{escape(number)}</span>'
        f"<span>{escape(tag)}</span></div><h3>{escape(title)}</h3>"
        f"<p>{escape(description)}</p></div>"
    )


def note(title: str, body: str, tone: str = "neutral") -> None:
    tone = tone if tone in {"neutral", "positive", "caution"} else "neutral"
    st.html(
        f'<div class="decision-note {tone}"><span class="note-rule"></span><div>'
        f"<strong>{escape(title)}</strong><p>{escape(body)}</p></div></div>"
    )


def evidence_card(finding: dict[str, Any], index: int, *, detailed: bool = False) -> None:
    classification = str(finding.get("classification", "Evidence"))
    with st.container(border=True):
        st.html(
            '<div class="evidence-head">'
            f'<span>FINDING {index:02d}</span><span class="evidence-label">'
            f"{escape(classification.replace('_', ' '))}</span></div>"
            f'<h3 class="evidence-title">{escape(str(finding["title"]))}</h3>'
        )
        st.write(finding["observation"])
        followups = finding.get("recommended_follow_ups", [])
        if followups:
            note("Next experiment", str(followups[0]["experiment"]))
        limitations = finding.get("limitations", [])
        if limitations:
            st.caption("Interpretation limit · " + "; ".join(limitations))
        if detailed:
            with st.expander("Supporting evidence and alternative explanations"):
                st.json(finding.get("supporting_evidence", []))
                for explanation in finding.get("alternative_explanations", []):
                    st.write("• " + explanation)


def chart(figure: go.Figure, *, height: int = 440) -> None:
    """Apply one readable chart style without changing data or analytical scales."""
    figure.update_layout(
        template="plotly_white",
        colorway=COLORS,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"family": "Segoe UI, Arial, sans-serif", "color": "#263c46", "size": 13},
        title={"font": {"size": 17}, "x": 0.02, "xanchor": "left"},
        margin={"l": 30, "r": 30, "t": 70, "b": 35},
        legend={"title_font_size": 12, "font_size": 12},
        height=height,
        coloraxis_colorbar={"outlinewidth": 0, "thickness": 12},
    )
    figure.update_xaxes(gridcolor="#eef1ef", zerolinecolor="#d7dfdb", automargin=True)
    figure.update_yaxes(gridcolor="#eef1ef", zerolinecolor="#d7dfdb", automargin=True)
    # Express assigns its own colors before the figure reaches this helper.
    for index, trace in enumerate(figure.data):
        if trace.type in {"scatter", "bar", "histogram"}:
            if isinstance(trace.marker.color, str) or trace.marker.color is None:
                trace.marker.color = COLORS[index % len(COLORS)]
            if trace.type == "scatter" and trace.mode and "markers" in trace.mode:
                trace.marker.size = 10
                trace.marker.line = {"width": 1, "color": "white"}
    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})
