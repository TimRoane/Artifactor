from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from common import (
    choose_another_run,
    downloads,
    json_file,
    project_root,
    report_model,
    requested_run_dir,
    run_dir,
    table,
)

from artifactor.onboarding import (
    create_project_from_frames,
    infer_sample_id,
    inspect_frames,
    suggest_roles,
)
from artifactor.pipeline import analyze
from artifactor.simulation import simulate

st.set_page_config(page_title="Artifactor", page_icon="A", layout="wide")


@st.cache_data(show_spinner=False)
def uploaded_table(name: str, payload: bytes) -> pd.DataFrame:
    suffix = Path(name).suffix.lower()
    stream = io.BytesIO(payload)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(stream)
    if suffix == ".csv":
        return pd.read_csv(stream)
    if suffix in {".tsv", ".txt"}:
        return pd.read_csv(stream, sep="\t")
    raise ValueError("Use a CSV, TSV, TXT, or Parquet table.")


def slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower() or "study"


def show_completed_run() -> None:
    root = run_dir()
    if (root / "external_validation").exists():
        identity = json_file("external_validation/dataset_identity.json")
        conclusion = json_file("external_validation/validation_conclusion.json")
        st.title("Artifactor external validation")
        st.caption("Preregistered public-data evidence · research use only")
        left, middle, right = st.columns(3)
        left.metric("Dataset", identity["dataset_id"])
        middle.metric("Tier", identity["tier"])
        right.metric("Conclusion", conclusion["status"])
        st.info(conclusion["status_reason"])
        st.warning(conclusion["correction_reason"])
        st.subheader("Preregistered questions")
        st.dataframe(
            table("external_validation/validation_questions.parquet"),
            use_container_width=True,
        )
        st.subheader("Source-study comparison")
        st.dataframe(
            table("external_validation/source_study_comparison.parquet"),
            use_container_width=True,
        )
        downloads()
        return

    model = report_model()
    st.title(model["report_title"])
    st.caption("Explainable artifact investigation · research use only")
    left, middle, right = st.columns(3)
    left.metric("Samples", model["sample_count"])
    middle.metric("Design", model["design"]["overall_status"])
    right.metric("Recommendation", model["recommendation_display_name"])
    st.info(model["recommendation_rationale"])
    st.warning(model["research_limitation"])
    downloads()
    st.subheader("Top evidence")
    for finding in model["evidence_cards"][:3]:
        with st.expander(finding["title"], expanded=True):
            st.write(finding["observation"])
            st.caption("Limitation: " + finding["limitations"][0])
            st.write("Follow-up: " + finding["recommended_follow_ups"][0]["experiment"])
    st.subheader("Method decision trail")
    if model.get("analysis_type") == "targeted_ngs":
        st.error(model["ngs_summary"]["variant_statement"])
        st.dataframe(
            table("ngs/coverage_representation_eligibility.parquet"),
            use_container_width=True,
        )
    else:
        st.dataframe(
            table("corrections/method_eligibility.parquet"), use_container_width=True
        )


def show_preflight(config_path: Path) -> None:
    preflight = json.loads((config_path.parent / "preflight.json").read_text(encoding="utf-8"))
    st.subheader("Preflight result")
    left, middle, right = st.columns(3)
    left.metric("Matched samples", preflight.get("sample_count", 0))
    middle.metric("Design", preflight["design_status"])
    right.metric(
        "Correction gate", "eligible" if preflight["correction_eligible"] else "refused"
    )
    if preflight["correction_eligible"]:
        st.success(preflight["design_reason"])
    else:
        st.warning(preflight["design_reason"])
    for issue in preflight["issues"]:
        (st.error if issue["level"] == "error" else st.warning)(issue["message"])
    st.code(str(config_path), language=None)
    if st.button("Run analysis", type="primary", disabled=not preflight["valid"]):
        with st.spinner("Analyzing the study and evaluating correction safety…"):
            completed = analyze(config_path)
        st.session_state.run_dir = completed
        st.rerun()


def analyze_my_data() -> None:
    st.subheader("1. Upload analysis-ready tables")
    st.write(
        "Upload sample metadata and at least one numeric measurement matrix. "
        "Rows may be samples or features; Artifactor will inspect both orientations."
    )
    metadata_upload = st.file_uploader(
        "Sample metadata", type=["csv", "tsv", "txt", "parquet", "pq"]
    )
    matrix_uploads = st.file_uploader(
        "Measurement matrix or matrices",
        type=["csv", "tsv", "txt", "parquet", "pq"],
        accept_multiple_files=True,
    )
    if not metadata_upload or not matrix_uploads:
        st.caption(
            "Metadata needs one row per sample. A samples-by-features matrix needs a sample-ID "
            "column; a features-by-samples matrix needs sample IDs as column names."
        )
        return
    try:
        metadata = uploaded_table(metadata_upload.name, metadata_upload.getvalue())
        matrices = {
            item.name: uploaded_table(item.name, item.getvalue()) for item in matrix_uploads
        }
    except (OSError, ValueError) as exc:
        st.error(f"Could not read the uploaded tables: {exc}")
        return
    st.dataframe(metadata.head(10), use_container_width=True)
    try:
        inferred_id = infer_sample_id(metadata, matrices)
    except ValueError:
        inferred_id = str(metadata.columns[0])
    sample_id = st.selectbox(
        "Which metadata column identifies samples?",
        list(map(str, metadata.columns)),
        index=list(map(str, metadata.columns)).index(inferred_id),
    )
    try:
        inspection = inspect_frames(metadata.copy(), matrices, sample_id)
    except ValueError as exc:
        st.error(f"Input matching failed: {exc}")
        return
    st.subheader("Sample matching and orientation")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "matrix": item.name,
                    "orientation": item.orientation,
                    "matched_samples": item.matched_samples,
                    "metadata_only": item.metadata_only_samples,
                    "matrix_only": item.matrix_only_samples,
                    "features": item.feature_count,
                    "numeric_cells": f"{item.numeric_fraction:.1%}",
                }
                for item in inspection.matrices
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    for item in inspection.matrices:
        for warning in item.warnings:
            st.warning(f"{item.name}: {warning}")
    roles = suggest_roles(metadata, sample_id)
    available_roles = [str(column) for column in metadata.columns if str(column) != sample_id]
    st.subheader("2. Tell Artifactor what the metadata means")
    biological = st.multiselect(
        "Biological variables to preserve",
        available_roles,
        default=roles["biological"],
        help="Examples: condition, disease status, tissue, treatment, sex, or timepoint.",
    )
    technical_options = [item for item in available_roles if item not in biological]
    technical = st.multiselect(
        "Technical variables to investigate",
        technical_options,
        default=[item for item in roles["technical"] if item in technical_options],
        help="Examples: batch, plate, instrument, center, lane, lot, or processing date.",
    )
    protected = st.multiselect(
        "Protected variables correction must preserve",
        biological,
        default=biological,
    )
    identifier_options = [
        item for item in available_roles if item not in biological and item not in technical
    ]
    identifiers = st.multiselect(
        "Other identifier columns (kept as metadata, not analyzed)",
        identifier_options,
        default=[item for item in roles["identifier"] if item in identifier_options],
        help="Examples: subject ID, specimen ID, or aliquot ID.",
    )
    if not biological or not technical:
        st.warning("Choose at least one biological and one technical variable to continue.")
    st.subheader("3. Confirm matrix types and analysis size")
    labels = {
        "Generic continuous": "generic_continuous",
        "RNA expression (normalized/continuous)": "rna_continuous",
        "Protein abundance (continuous)": "proteomics_continuous",
        "Metabolomics abundance (continuous)": "generic_continuous",
        "Continuous genomic summary": "genomic_continuous",
    }
    kinds: dict[str, str] = {}
    for name in matrices:
        choice = st.selectbox(f"{name}", list(labels), key=f"kind-{name}")
        kinds[name] = labels[choice]
    budget = st.selectbox(
        "Analysis depth", ["quick", "standard", "full"], index=0,
        help="Quick is best for the first pass. Standard/full increase resampling and runtime.",
    )
    project_name = st.text_input("Project name", "My Artifactor Study")
    confirmed = st.checkbox(
        "I reviewed the biological, technical, and protected variable assignments."
    )
    if st.button(
        "Create project and run preflight",
        type="primary",
        disabled=not (biological and technical and confirmed),
    ):
        root = project_root()
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        destination = root / f"{slug(project_name)}-{stamp}"
        try:
            config = create_project_from_frames(
                destination,
                project_name,
                metadata,
                matrices,
                sample_id,
                biological,
                technical,
                protected,
                identifiers,
                kinds,  # type: ignore[arg-type]
                budget,  # type: ignore[arg-type]
            )
        except (OSError, ValueError) as exc:
            st.error(f"Project setup failed: {exc}")
            return
        st.session_state.onboarding_config = config
        st.rerun()


def try_demo() -> None:
    st.subheader("Try a complete example")
    scenario = st.selectbox(
        "Demo",
        ["separable", "confounded"],
        format_func=lambda item: {
            "separable": "Correction is safe: biology and batch overlap",
            "confounded": "Correction is refused: biology and batch are inseparable",
        }[item],
    )
    st.write(
        "The demo creates synthetic inputs with known truth, runs the same pipeline used for "
        "uploaded data, and opens the completed result."
    )
    if st.button("Run demo", type="primary"):
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        destination = project_root() / f"demo-{scenario}-{stamp}"
        with st.spinner("Creating and analyzing the demonstration…"):
            simulate(scenario, destination, samples=80, rna_features=500, protein_features=150)
            completed = analyze(destination / "config.yaml")
        st.session_state.run_dir = completed
        st.rerun()


def open_run() -> None:
    st.subheader("Open a completed run")
    root = project_root()
    recent = sorted(
        (path.parent for path in root.glob("**/run.json")),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:20] if root.exists() else []
    selected = st.selectbox(
        "Recent runs",
        [""] + [str(path) for path in recent],
        format_func=lambda value: "Choose a recent run…" if not value else value,
    )
    candidate = st.text_input("Or enter a run directory", value=selected)
    if st.button("Open run", disabled=not candidate):
        path = Path(candidate).expanduser().resolve()
        if not (path / "run.json").exists():
            st.error("That directory does not contain run.json.")
            return
        st.session_state.run_dir = path
        st.rerun()


if requested_run_dir() is not None:
    choose_another_run()
    show_completed_run()
elif "onboarding_config" in st.session_state:
    st.title("Artifactor study setup")
    if st.button("Start over"):
        del st.session_state.onboarding_config
        st.rerun()
    show_preflight(Path(st.session_state.onboarding_config))
else:
    st.title("Start an Artifactor analysis")
    st.write(
        "Check whether technical processing affected your measurement data, whether correction "
        "is scientifically safe, and download corrected data when it passes the safety gates."
    )
    mode = st.radio(
        "What would you like to do?",
        ["Analyze my data", "Try a demonstration", "Open a completed run"],
        horizontal=True,
    )
    if mode == "Analyze my data":
        analyze_my_data()
    elif mode == "Try a demonstration":
        try_demo()
    else:
        open_run()
