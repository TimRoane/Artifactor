import streamlit as st
from common import json_file, report_model, shell, table
from design import note, page_heading, section_heading

shell("study_design")
model = report_model()
ngs = model.get("analysis_type") == "targeted_ngs"
page_heading(
    "01 / THE DESIGN GATE",
    "Can this study separate the effects?",
    "Independent support for biology and processing is the foundation of a defensible correction.",
)
audit = json_file("design/design_summary.json")
left, middle, right = st.columns(3)
left.metric("Samples", audit["sample_count"])
middle.metric("Design rank", f"{audit['design_rank']} / {audit['design_columns']}")
right.metric("Correction gate", "Eligible" if audit["correction_permitted"] else "Refused")
note(
    "Independent support" if audit["correction_permitted"] else "Correction is not identifiable",
    audit["summary_text"],
    "positive" if audit["correction_permitted"] else "caution",
)
section_heading("01", "The variables in the question")
left, right = st.columns(2)
with left, st.container(border=True):
    st.markdown("**Biology to preserve**")
    st.write(", ".join(audit["biological_variables"]) or "None declared")
    st.caption("Protected: " + (", ".join(audit["protected_variables"]) or "None declared"))
with right, st.container(border=True):
    st.markdown("**Technical effects to investigate**")
    st.write(", ".join(audit["technical_variables"]) or "None declared")
    st.caption("Processing variables that may be associated with observed variation.")
section_heading(
    "02",
    "Where the design has support",
    "Pairwise evidence shows whether declared effects can be distinguished.",
)
st.dataframe(
    table("design/pairwise_identifiability.parquet"), use_container_width=True, hide_index=True
)
with st.expander("Full design audit"):
    st.json(audit)
if ngs:
    section_heading("03", "Callability and panel coverage")
    note(
        "Absence has more than one meaning",
        "Structural panel absence is not zero coverage. Insufficient depth is not a negative event.",
        "caution",
    )
    st.dataframe(
        table("ngs/callability_summary.parquet"), use_container_width=True, hide_index=True
    )
    st.subheader("Common target universe")
    st.dataframe(
        table("ngs/common_target_universe.parquet"), use_container_width=True, hide_index=True
    )
