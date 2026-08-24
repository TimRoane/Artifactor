import plotly.express as px
import streamlit as st
from common import choose_another_run, report_model, table

choose_another_run()
model = report_model()
st.title("NGS QC Overview")
if model.get("analysis_type") != "targeted_ngs":
    st.info("This section is available for targeted-NGS runs.")
    st.stop()
summary = table("ngs/sample_qc_summary.parquet")
metric = st.selectbox("QC metric", sorted(summary.metric_id.unique()))
view = summary[summary.metric_id == metric]
st.plotly_chart(
    px.histogram(view, x="value", color="status", title=f"{metric} distribution"),
    use_container_width=True,
)
st.dataframe(view, use_container_width=True)
st.subheader("QC associations")
st.dataframe(
    table("ngs/sample_qc_associations.parquet").query("metric_id == @metric"),
    use_container_width=True,
)
st.subheader("Detection opportunity")
st.dataframe(table("ngs/detection_opportunity.parquet"), use_container_width=True)
