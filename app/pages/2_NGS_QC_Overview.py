import plotly.express as px
import streamlit as st
from common import report_model, shell, table
from design import chart, note, page_heading, section_heading

shell("ngs_quality")
model = report_model()
page_heading(
    "ASSAY QUALITY",
    "Put coverage in context.",
    "Review sample quality, callability, and the opportunity to detect a signal.",
)
if model.get("analysis_type") != "targeted_ngs":
    note(
        "A different measurement family",
        "This page is for targeted-NGS studies. Explore Study design or Factor explorer for this continuous-matrix run.",
    )
    st.stop()
summary = table("ngs/sample_qc_summary.parquet")
metric = st.selectbox("QC metric", sorted(summary.metric_id.unique()))
view = summary[summary.metric_id == metric]
chart(px.histogram(view, x="value", color="status", title=f"{metric} distribution"))
with st.expander("Sample-level measurements"):
    st.dataframe(view, use_container_width=True, hide_index=True)
section_heading("01", "Quality associations")
st.dataframe(
    table("ngs/sample_qc_associations.parquet").query("metric_id == @metric"),
    use_container_width=True,
    hide_index=True,
)
section_heading(
    "02",
    "Detection opportunity",
    "Interpret observations alongside the coverage and callability that support them.",
)
st.dataframe(table("ngs/detection_opportunity.parquet"), use_container_width=True, hide_index=True)
