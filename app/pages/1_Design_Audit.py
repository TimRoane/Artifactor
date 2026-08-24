import streamlit as st
from common import choose_another_run, json_file, report_model, table

choose_another_run()
model = report_model()
st.title(
    "Design and Callability"
    if model.get("analysis_type") == "targeted_ngs"
    else "Study-Design Audit"
)
audit = json_file("design/design_summary.json")
st.json(audit)
st.dataframe(table("design/pairwise_identifiability.parquet"), use_container_width=True)
if not audit["correction_permitted"]:
    st.error("Correction is refused because declared effects are not independently identifiable.")
else:
    st.success("The configured correction design is eligible.")
if model.get("analysis_type") == "targeted_ngs":
    st.warning(
        "Structural panel absence is not represented as zero coverage; insufficient depth is not a negative event."
    )
    st.dataframe(table("ngs/callability_summary.parquet"), use_container_width=True)
    st.subheader("Common target universe")
    st.dataframe(table("ngs/common_target_universe.parquet"), use_container_width=True)
