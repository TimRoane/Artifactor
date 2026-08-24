from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import streamlit as st

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
        st.query_params.pop("run", None)
        st.switch_page("Home.py")


def run_dir() -> Path:
    root = requested_run_dir()
    if root is None:
        st.error("Open this page from a completed run, or return to Home to start an analysis.")
        st.stop()
    if not (root / "report/report_model.json").exists() and not (
        root / "external_validation/validation_conclusion.json"
    ).exists():
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
    st.download_button(
        "Download standalone report",
        report.read_bytes(),
        report.name,
        "text/html",
    )
    export_path = root / "exports/corrected_data.json"
    if export_path.exists():
        export = json.loads(export_path.read_text(encoding="utf-8"))
        if export.get("status") == "available":
            st.success(f"Corrected data are available ({export['method']}).")
            for relative in export.get("files", []):
                path = root / relative
                st.download_button(
                    f"Download {path.name}",
                    path.read_bytes(),
                    path.name,
                    "text/csv",
                    key=f"download-{relative}",
                )
        else:
            st.info(str(export.get("reason", "No corrected dataset was generated.")))
