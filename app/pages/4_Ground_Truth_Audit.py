import json

import streamlit as st
from common import report_model, run_dir, shell, table
from design import note, page_heading, section_heading

shell("ground_truth")
page_heading(
    "SYNTHETIC VALIDATION",
    "Check the answer against the known signal.",
    "Use injected effects to evaluate recovery. Keep this evidence separate from observations in real studies.",
)
model = report_model()
if not model["ground_truth"]["supplied"]:
    note(
        "Ground truth was not supplied",
        "This audit is available for synthetic benchmark runs. It is intentionally absent when the true effects are unknown.",
    )
else:
    note(
        "A controlled test of recovery",
        "Synthetic results measure performance under the simulator's assumptions. They do not establish external or clinical validity.",
        "caution",
    )
    with st.expander("Ground-truth summary"):
        st.json(model["ground_truth"])
    if model.get("analysis_type") == "targeted_ngs":
        for title, filename in [
            ("Coverage recovery", "ngs_coverage_recovery.json"),
            ("Variant and artifact recovery", "ngs_variant_recovery.json"),
        ]:
            path = run_dir() / "ground_truth" / filename
            if path.exists():
                section_heading("↗", title)
                st.json(json.loads(path.read_text(encoding="utf-8")))
    elif (run_dir() / "ground_truth/feature_recovery.parquet").exists():
        section_heading("01", "Feature-level recovery")
        st.dataframe(
            table("ground_truth/feature_recovery.parquet"),
            use_container_width=True,
            hide_index=True,
        )
