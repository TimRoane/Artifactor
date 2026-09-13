import plotly.express as px
import streamlit as st
from common import downloads, json_file, report_model, shell, table
from design import chart, note, page_heading, section_heading

shell("correction_comparison")
model = report_model()
ngs = model.get("analysis_type") == "targeted_ngs"
page_heading(
    "THE CORRECTION DECISION",
    "Reduce the artifact. Protect the question.",
    "Compare technical-signal reduction with retention of declared biology. Improvement must satisfy both.",
)
if ngs:
    note(
        "Original variant observations are retained",
        model["ngs_summary"]["variant_statement"],
        "caution",
    )
    metrics = table("ngs/coverage_representation_metrics.parquet")
    chart(
        px.scatter(
            metrics,
            x="technical_removal",
            y="biological_loss",
            color="representation",
            title="Exploratory coverage representations",
            labels={
                "technical_removal": "Technical signal removed",
                "biological_loss": "Declared biological loss",
            },
        )
    )
    st.dataframe(
        table("ngs/coverage_representation_eligibility.parquet"),
        use_container_width=True,
        hide_index=True,
    )
    section_heading(
        "01",
        "Allele observations in context",
        "Observed VAF alongside its read depth. Display limited to the first 5,000 saved observations.",
    )
    vaf = table("ngs/variant_callable_status.parquet")
    chart(
        px.scatter(
            vaf.head(5000),
            x="total_depth",
            y="observed_vaf",
            color="callability_status",
            hover_data=["variant_id", "alt_count", "existing_call_state"],
            labels={"total_depth": "Total read depth", "observed_vaf": "Observed VAF"},
        )
    )
    with st.expander("Sequence-context evidence"):
        st.dataframe(
            table("ngs/sequence_context_summary.parquet"), use_container_width=True, hide_index=True
        )
else:
    metrics = table("evaluation/method_metrics.parquet")
    recommendation = json_file("interpretation/recommendation.json")
    note(
        model["recommendation_display_name"],
        recommendation["rationale"],
        "caution" if recommendation.get("method") == "none" else "positive",
    )
    section_heading("01", "The preservation / removal trade-off")
    chart(
        px.scatter(
            metrics,
            x="technical_removal",
            y="biological_loss",
            color="method",
            hover_data=list(metrics.columns),
            title="Candidate correction comparison",
            labels={
                "technical_removal": "Technical signal removed",
                "biological_loss": "Declared biological loss",
                "method": "Method",
            },
        )
    )
    st.caption(
        "Further right: more technical removal. Lower: less measured biological loss. Negative loss reflects an increase in the measured retention score."
    )
    with st.expander("Compare all measured scores", expanded=True):
        st.dataframe(metrics, use_container_width=True, hide_index=True)
    section_heading(
        "02",
        "Eligibility and selection",
        "The decision trail includes methods the study could not support.",
    )
    st.dataframe(
        table("corrections/method_eligibility.parquet"), use_container_width=True, hide_index=True
    )
downloads()
