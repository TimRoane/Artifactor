import plotly.express as px
import streamlit as st
from common import json_file, table

st.title("Correction Comparison")
metrics = table("evaluation/method_metrics.parquet")
recommendation = json_file("evaluation/recommendation.json")
st.plotly_chart(
    px.scatter(
        metrics,
        x="technical_removal",
        y="biological_loss",
        color="method",
        hover_data=metrics.columns,
        title="Preservation/removal frontier",
    ),
    use_container_width=True,
)
st.dataframe(metrics, use_container_width=True)
st.success(recommendation["rationale"])
