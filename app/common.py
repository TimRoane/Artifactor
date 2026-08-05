from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import streamlit as st


def run_dir() -> Path:
    if "run_dir" not in st.session_state:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--run")
        args, _ = parser.parse_known_args()
        candidate = args.run or st.query_params.get("run")
        if not candidate:
            st.error("Launch with `artifactor serve --run <completed-run>`.")
            st.stop()
        st.session_state.run_dir = Path(candidate)
    root = Path(st.session_state.run_dir)
    if not (root / "run.json").exists():
        st.error(f"Invalid run directory: {root}")
        st.stop()
    return root


def json_file(relative: str):
    return json.loads((run_dir() / relative).read_text(encoding="utf-8"))


def table(relative: str) -> pd.DataFrame:
    return pd.read_parquet(run_dir() / relative).drop(columns=["schema_version"], errors="ignore")


def downloads() -> None:
    root = run_dir()
    st.download_button(
        "Download standalone report",
        (root / "report/index.html").read_bytes(),
        "artifactor-report.html",
        "text/html",
    )
