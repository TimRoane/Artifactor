import streamlit as st
from common import downloads, json_file, table

st.set_page_config(page_title="Artifactor", page_icon="🧬", layout="wide")
run = json_file("run.json")
recommendation = json_file("evaluation/recommendation.json")
findings = json_file("interpretation/findings.json")
st.title("Artifactor")
st.caption("Assay-aware technical artifact analysis · research use only")
left, middle, right = st.columns(3)
left.metric("Samples", run["sample_count"])
middle.metric("Design", run["design_status"])
right.metric("Recommendation", recommendation["method"])
st.info(recommendation["rationale"])
st.subheader("Top findings")
for finding in findings[:3]:
    with st.expander(finding["title"], expanded=True):
        st.write(finding["interpretation"])
        st.caption("Limitation: " + finding["limitation"])
        st.write("Follow-up: " + finding["follow_up"])
st.subheader("Method comparison")
st.dataframe(table("evaluation/method_metrics.parquet"), use_container_width=True)
downloads()
