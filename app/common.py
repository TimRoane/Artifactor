from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from design import brand, note, section_heading, setup, topbar

from artifactor import __version__
from artifactor.io import checksum


def requested_run_dir() -> Path | None:
    if "run_dir" in st.session_state:
        return Path(st.session_state.run_dir)
    if "requested_run_checked" not in st.session_state:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--run")
        args, _ = parser.parse_known_args()
        candidate = args.run or st.query_params.get("run")
        st.session_state.requested_run_checked = True
        if candidate:
            st.session_state.run_dir = Path(candidate)
            return Path(candidate)
    return None


def project_root() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--project-root", default="projects")
    args, _ = parser.parse_known_args()
    return Path(args.project_root).resolve()


def choose_another_run() -> None:
    """Render navigation that leaves the active run and returns to the start screen."""
    if requested_run_dir() is None:
        return
    if st.button("← Choose another run", key="choose-another-run"):
        st.session_state.pop("run_dir", None)
        st.session_state.pop("onboarding_config", None)
        st.session_state.pop("workspace_mode", None)
        st.query_params.pop("run", None)
        st.switch_page("Home.py")


def shell(active: str = "workspace") -> None:
    """Present the same navigation and visual frame on every application page."""
    setup()
    root = requested_run_dir()
    with st.sidebar:
        brand()
        st.html('<div class="nav-label">WORKSPACE</div>')
        if root:
            st.page_link("Home.py", label="Overview")
        elif st.button("Start here", key="nav-workspace", use_container_width=True):
            st.session_state.pop("workspace_mode", None)
            st.session_state.pop("onboarding_config", None)
            st.rerun()
        if root:
            external = (root / "external_validation").exists()
            if not external:
                st.html('<div class="nav-label">INVESTIGATION</div>')
                st.page_link("pages/1_Design_Audit.py", label="01   Study design")
                st.page_link("pages/2_Factor_Explorer.py", label="02   Factor explorer")
                if (root / "ngs").exists():
                    st.page_link("pages/2_NGS_QC_Overview.py", label="03   NGS quality")
                st.page_link("pages/3_Correction_Comparison.py", label="Correction comparison")
                st.page_link("pages/4_Root_Cause_Report.py", label="Evidence & follow-up")
                st.page_link("pages/4_Ground_Truth_Audit.py", label="Ground-truth audit")
            st.html('<div class="nav-label">RECORD</div>')
            st.page_link("pages/5_Run_Provenance.py", label="Provenance & downloads")
            st.html(
                '<div class="sidebar-context"><span>ACTIVE RUN</span>'
                f"<strong>{escape(root.name)}</strong><p>Saved evidence · ready to review</p></div>"
            )
            choose_another_run()
        else:
            st.html(
                '<div class="sidebar-context"><span>YOUR NEXT INVESTIGATION</span>'
                "<strong>Start with a question.<br>Leave with evidence.</strong>"
                "<p>New studies, synthetic demonstrations, and completed results in one place.</p></div>"
            )
        st.html(
            '<div class="sidebar-footer"><strong>Evidence before correction.</strong><br>'
            f"Artifactor {escape(__version__)}<br>Research prototype · research use only</div>"
        )
    topbar(active.replace("_", " "))


def run_dir() -> Path:
    root = requested_run_dir()
    if root is None:
        st.error("Open this page from a completed run, or return to Home to start an analysis.")
        st.stop()
    if (
        not (root / "report/report_model.json").exists()
        and not (root / "external_validation/validation_conclusion.json").exists()
    ):
        st.error(f"Invalid completed Artifactor run directory: {root}")
        st.stop()
    return root


@st.cache_data(show_spinner=False)
def _json_cached(path: str, digest: str):
    del digest
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_file(relative: str):
    path = run_dir() / relative
    return _json_cached(str(path), checksum(path))


@st.cache_data(show_spinner=False)
def _table_cached(path: str, digest: str) -> pd.DataFrame:
    del digest
    return pd.read_parquet(path).drop(columns=["schema_version"], errors="ignore")


def table(relative: str) -> pd.DataFrame:
    path = run_dir() / relative
    return _table_cached(str(path), checksum(path))


def report_model():
    return json_file("report/report_model.json")


def downloads() -> None:
    root = run_dir()
    report = (
        root / "report/external-validation-report.html"
        if (root / "external_validation").exists()
        else root / "report/artifactor-report.html"
    )
    section_heading(
        "↓",
        "Take the evidence with you",
        "An interactive report and the data this run can responsibly release.",
    )
    with st.container(border=True):
        left, right = st.columns([3, 2])
        with left:
            st.markdown("**The complete investigation, in one report.**")
            st.caption(
                "Opens in a browser. Interactive plots work offline; linked artifact downloads require the run folder."
            )
        with right:
            st.download_button(
                "Download standalone report",
                report.read_bytes(),
                report.name,
                "text/html",
                type="primary",
                use_container_width=True,
            )
    export_path = root / "exports/corrected_data.json"
    if export_path.exists():
        export = json.loads(export_path.read_text(encoding="utf-8"))
        if export.get("status") == "available":
            with st.expander("Corrected datasets · available", expanded=True):
                st.caption(
                    f"Selected method: {export['method']}. Original measurements remain unchanged."
                )
                files = export.get("files", [])
                columns = st.columns(min(3, max(1, len(files))))
                for index, relative in enumerate(files):
                    path = root / relative
                    columns[index % len(columns)].download_button(
                        f"Download {path.name}",
                        path.read_bytes(),
                        path.name,
                        "text/csv",
                        key=f"download-{relative}",
                        use_container_width=True,
                    )
        else:
            note(
                "No corrected dataset released",
                str(export.get("reason", "No corrected dataset was generated.")),
                "caution",
            )
