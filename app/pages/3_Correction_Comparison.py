import plotly.express as px
import streamlit as st
from common import choose_another_run, json_file, report_model, table

choose_another_run()
model = report_model()
if model.get("analysis_type") == "targeted_ngs":
    st.title("Coverage Mitigation and Variant Diagnostics")
    st.error(model["ngs_summary"]["variant_statement"])
    metrics = table("ngs/coverage_representation_metrics.parquet")
    st.plotly_chart(
        px.scatter(
            metrics,
            x="technical_removal",
            y="biological_loss",
            color="representation",
            title="Exploratory coverage representation frontier",
        ),
        use_container_width=True,
    )
    st.dataframe(table("ngs/coverage_representation_eligibility.parquet"), use_container_width=True)
    st.subheader("Observed VAF with count/depth context")
    vaf = table("ngs/variant_callable_status.parquet")
    st.plotly_chart(
        px.scatter(
            vaf.head(5000),
            x="total_depth",
            y="observed_vaf",
            color="callability_status",
            hover_data=["variant_id", "alt_count", "existing_call_state"],
        ),
        use_container_width=True,
    )
    st.dataframe(table("ngs/sequence_context_summary.parquet"), use_container_width=True)
    st.stop()
st.title("Correction Comparison")
metrics = table("evaluation/method_metrics.parquet")
recommendation = json_file("interpretation/recommendation.json")
st.plotly_chart(
    px.scatter(
        metrics,
        x="technical_removal",
        y="biological_loss",
        color="method",
        hover_data=list(metrics.columns),
        title="Preservation/removal frontier",
    ),
    use_container_width=True,
)
st.dataframe(metrics, use_container_width=True)
st.subheader("Eligibility and selection trail")
st.dataframe(table("corrections/method_eligibility.parquet"), use_container_width=True)
st.success(recommendation["rationale"])
