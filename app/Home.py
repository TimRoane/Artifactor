from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from common import (
    downloads,
    json_file,
    project_root,
    report_model,
    requested_run_dir,
    run_dir,
    shell,
    table,
)
from design import evidence_card, hero, launch_card, note, page_heading, section_heading

from artifactor.onboarding import (
    create_project_from_frames,
    infer_sample_id,
    inspect_frames,
    suggest_roles,
)
from artifactor.pipeline import analyze
from artifactor.simulation import simulate


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
        page_heading(
            "EXTERNAL VALIDATION",
            "Evidence beyond the simulator.",
            "Preregistered questions, public-data observations, and their limits.",
        )
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
    page_heading(
        "INVESTIGATION OVERVIEW",
        model["report_title"],
        "The decision, the evidence behind it, and the next question worth asking.",
    )
    left, middle, right, fourth = st.columns(4)
    left.metric("Samples", model["sample_count"])
    middle.metric("Modalities", len(model["modalities"]))
    right.metric("Study design", model["design"]["overall_status"].replace("_", " ").capitalize())
    fourth.metric("Evidence cards", len(model["evidence_cards"]))
    permitted = model["design"]["correction_permitted"]
    decision_tone = (
        "caution"
        if not permitted
        else "neutral"
        if model["recommendation_method"] == "none"
        else "positive"
    )
    note(
        model["recommendation_display_name"],
        model["recommendation_rationale"],
        decision_tone,
    )
    st.caption(model["research_limitation"])
    downloads()
    section_heading(
        "01",
        "What deserves your attention",
        "Leading findings, paired with an experiment that could test them.",
    )
    for index, finding in enumerate(model["evidence_cards"][:3], start=1):
        evidence_card(finding, index)
    if not model["evidence_cards"]:
        note(
            "No evidence cards in this run",
            "Review the study-design audit and correction comparison for the available evidence.",
        )
    section_heading("02", "How the decision was made")
    if model.get("analysis_type") == "targeted_ngs":
        st.error(model["ngs_summary"]["variant_statement"])
        st.dataframe(
            table("ngs/coverage_representation_eligibility.parquet"),
            use_container_width=True,
        )
    else:
        st.dataframe(table("corrections/method_eligibility.parquet"), use_container_width=True)


def show_preflight(config_path: Path) -> None:
    preflight = json.loads((config_path.parent / "preflight.json").read_text(encoding="utf-8"))
    section_heading(
        "04",
        "A final check before analysis",
        "The study design determines whether correction can be evaluated.",
    )
    left, middle, right = st.columns(3)
    left.metric("Matched samples", preflight.get("sample_count", 0))
    middle.metric("Design", preflight["design_status"])
    right.metric("Correction gate", "eligible" if preflight["correction_eligible"] else "refused")
    clear_design = preflight["correction_eligible"] and preflight["design_status"] == "separable"
    note(
        "Ready to evaluate correction" if clear_design else "Review the design before proceeding",
        preflight["design_reason"],
        "positive" if clear_design else "caution",
    )
    for issue in preflight["issues"]:
        (st.error if issue["level"] == "error" else st.warning)(issue["message"])
    with st.expander("Project configuration"):
        st.code(str(config_path), language=None)
    if st.button("Run analysis", type="primary", disabled=not preflight["valid"]):
        with st.spinner("Analyzing the study and evaluating correction safety…"):
            completed = analyze(config_path)
        st.session_state.run_dir = completed
        st.rerun()


def analyze_my_data() -> None:
    section_heading(
        "01",
        "Bring the measurements. Keep the context.",
        "Add sample metadata and analysis-ready measurements. We will check how the samples line up.",
    )
    left, right = st.columns(2, gap="large")
    with left, st.container(border=True):
        st.markdown("**Sample context**")
        st.caption("One row per sample, with biological and processing variables.")
        metadata_upload = st.file_uploader(
            "Sample metadata", type=["csv", "tsv", "txt", "parquet", "pq"]
        )
    with right, st.container(border=True):
        st.markdown("**Measurement data**")
        st.caption("One or more numeric matrices. Samples can be in rows or columns.")
        matrix_uploads = st.file_uploader(
            "Measurement matrix or matrices",
            type=["csv", "tsv", "txt", "parquet", "pq"],
            accept_multiple_files=True,
        )
    if not metadata_upload or not matrix_uploads:
        note(
            "Start with analysis-ready data",
            "Use normalized continuous measurements and matching sample IDs. Raw sequencing reads and variant files need upstream processing first.",
        )
        with st.expander("What should my tables look like?"):
            st.markdown("**Metadata** · identifiers plus the variables that describe your study")
            st.code(
                "sample_id,condition,batch\nS01,control,B1\nS02,treated,B1\nS03,control,B2\nS04,treated,B2",
                language="text",
            )
            st.markdown("**Measurements** · sample identifiers plus numeric feature columns")
            st.code(
                "sample_id,gene_1,gene_2\nS01,4.2,8.1\nS02,5.0,7.8\nS03,4.4,8.0\nS04,5.1,7.6",
                language="text",
            )
            st.caption(
                "Illustrative format only. A real study needs enough samples to support its design and evaluation."
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
    with st.expander("Preview sample metadata", expanded=True):
        st.dataframe(metadata.head(10), use_container_width=True, hide_index=True)
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
    section_heading(
        "02",
        "Define what matters",
        "Declare the biology to protect and the technical effects to investigate.",
    )
    biology_panel, technical_panel = st.columns(2, gap="large")
    biological = biology_panel.multiselect(
        "Biological variables to preserve",
        available_roles,
        default=roles["biological"],
        help="Examples: condition, disease status, tissue, treatment, sex, or timepoint.",
    )
    technical_options = [item for item in available_roles if item not in biological]
    technical = technical_panel.multiselect(
        "Technical variables to investigate",
        technical_options,
        default=[item for item in roles["technical"] if item in technical_options],
        help="Examples: batch, plate, instrument, center, lane, lot, or processing date.",
    )
    protected = biology_panel.multiselect(
        "Protected variables correction must preserve",
        biological,
        default=biological,
    )
    identifier_options = [
        item for item in available_roles if item not in biological and item not in technical
    ]
    identifiers = technical_panel.multiselect(
        "Other identifier columns (kept as metadata, not analyzed)",
        identifier_options,
        default=[item for item in roles["identifier"] if item in identifier_options],
        help="Examples: subject ID, specimen ID, or aliquot ID.",
    )
    if not biological or not technical:
        st.warning("Choose at least one biological and one technical variable to continue.")
    section_heading(
        "03",
        "Set the scope",
        "Confirm the measurement types, choose analysis depth, and name your study.",
    )
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
    scope, identity = st.columns([1, 2], gap="large")
    budget = scope.selectbox(
        "Analysis depth",
        ["quick", "standard", "full"],
        index=0,
        help="Quick is best for the first pass. Standard/full increase resampling and runtime.",
    )
    project_name = identity.text_input("Project name", "My Artifactor Study")
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
    section_heading(
        "01",
        "Two studies. Two responsible decisions.",
        "Explore both a correction that passes the checks and a design that cannot support one.",
    )
    left, right = st.columns(2)
    with left:
        note(
            "Independent support",
            "Biology and batch overlap across samples. The analysis can compare corrections against biological-preservation criteria.",
            "positive",
        )
    with right:
        note(
            "Confounded by design",
            "Biology and batch are inseparable. The result explains why correction is refused and what evidence is missing.",
            "caution",
        )
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
    st.caption("80 synthetic samples · RNA + protein · fixed seed · no external dataset required")
    if st.button("Run demo", type="primary"):
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        destination = project_root() / f"demo-{scenario}-{stamp}"
        try:
            with st.status("Building your investigation…", expanded=True) as progress:
                st.write(
                    "Generating a synthetic cohort with known biological and technical effects."
                )
                simulate(scenario, destination, samples=80, rna_features=500, protein_features=150)
                st.write("Auditing the design, evaluating the evidence, and preparing the report.")
                completed = analyze(destination / "config.yaml")
                progress.update(label="Investigation complete", state="complete", expanded=False)
        except (OSError, ValueError) as exc:
            st.error(f"The demonstration could not finish: {exc}")
            return
        st.session_state.run_dir = completed
        st.rerun()


def open_run() -> None:
    section_heading(
        "01", "Pick up the investigation", "Reopen saved evidence without rerunning the analysis."
    )
    root = project_root()
    recent = (
        sorted(
            (path.parent for path in root.glob("**/run.json")),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:20]
        if root.exists()
        else []
    )
    selected = st.selectbox(
        "Recent runs",
        [""] + [str(path) for path in recent],
        format_func=lambda value: "Choose a recent run…" if not value else Path(value).name,
    )
    if not recent:
        note(
            "A fresh workspace",
            "Completed studies will appear here. You can also open a run stored elsewhere by entering its directory below.",
        )
    candidate = st.text_input("Or enter a run directory", value=selected)
    if st.button("Open run", disabled=not candidate):
        path = Path(candidate).expanduser().resolve()
        if not (path / "run.json").exists():
            st.error("That directory does not contain run.json.")
            return
        st.session_state.run_dir = path
        st.rerun()


def show_workspace() -> None:
    hero()
    section_heading("↗", "Where would you like to begin?")
    choices = [
        (
            "01",
            "Start with your data",
            "Build a study from your measurements and sample metadata. Let the design guide the analysis.",
            "NEW STUDY",
            "Analyze my data",
            "analyze",
        ),
        (
            "02",
            "See the method in action",
            "Explore two synthetic studies. See when correction is justified, and when restraint is the result.",
            "GUIDED DEMO",
            "Try a demonstration",
            "demo",
        ),
        (
            "03",
            "Return to the evidence",
            "Open a completed investigation. Review the decision, explore the evidence, and collect your report.",
            "SAVED RESULTS",
            "Open a completed run",
            "open",
        ),
    ]
    for column, (number, title, description, tag, label, mode) in zip(
        st.columns(3, gap="medium"), choices, strict=True
    ):
        with column, st.container(border=True):
            launch_card(number, title, description, tag)
            if st.button(
                label,
                key=f"launch-{mode}",
                type="primary" if mode == "analyze" else "secondary",
                use_container_width=True,
            ):
                st.session_state.workspace_mode = mode
                st.rerun()
    st.html(
        '<div class="workflow-strip"><div><strong>Design comes first.</strong>'
        "<p>Check what the study can identify before changing the measurements.</p></div>"
        "<div><strong>Preservation is part of the test.</strong>"
        "<p>Evaluate technical removal alongside retention of declared biology.</p></div>"
        "<div><strong>Every decision leaves a record.</strong>"
        "<p>Inspect the evidence, its limitations, and the next experiment.</p></div></div>"
    )


shell("overview" if requested_run_dir() is not None else "workspace")
if requested_run_dir() is not None:
    show_completed_run()
elif "onboarding_config" in st.session_state:
    page_heading(
        "STUDY SETUP",
        "Ready for a closer look.",
        "Review the preflight result before launching the investigation.",
    )
    if st.button("Start over"):
        del st.session_state.onboarding_config
        st.rerun()
    show_preflight(Path(st.session_state.onboarding_config))
else:
    mode = st.session_state.get("workspace_mode")
    if mode is None:
        show_workspace()
    else:
        if st.button("← Back to workspace"):
            st.session_state.pop("workspace_mode", None)
            st.rerun()
        if mode == "analyze":
            page_heading(
                "NEW STUDY",
                "Give your study a clear starting point.",
                "Measurements, metadata, and a question worth protecting.",
            )
            analyze_my_data()
        elif mode == "demo":
            page_heading(
                "GUIDED DEMONSTRATIONS",
                "See the evidence change the decision.",
                "A complete investigation, from a known synthetic signal to an explained result.",
            )
            try_demo()
        else:
            page_heading(
                "COMPLETED RUNS",
                "Your evidence, ready to revisit.",
                "Continue from a saved investigation and take its results with you.",
            )
            open_run()
