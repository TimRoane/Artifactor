import plotly.express as px
import streamlit as st
from common import report_model, shell, table
from design import chart, note, page_heading, section_heading

shell("factor_explorer")
model = report_model()
ngs = model.get("analysis_type") == "targeted_ngs"
page_heading(
    "02 / SOURCES OF VARIATION",
    "What is shaping the signal?",
    "Explore how latent factors relate to sample metadata, then inspect the features behind them.",
)
associations = table(
    "ngs/coverage_factor_associations.parquet"
    if ngs
    else "factors/factor_metadata_associations.parquet"
)
if ngs:
    note(
        "A diagnostic view of coverage",
        "These factors come from a derived count-aware representation. Original target counts remain unchanged.",
        "caution",
    )
    view = associations
else:
    modality = st.selectbox("Modality", sorted(associations.modality.unique()))
    view = associations[associations.modality == modality]
section_heading(
    "01",
    "Connect factors to the study",
    "Association strength describes statistical consistency, not proof of cause.",
)
heat = view.pivot(index="variable", columns="factor", values="effect_size")
chart(
    px.imshow(
        heat,
        text_auto=".2f",
        aspect="auto",
        title="Factor–metadata association strength",
        color_continuous_scale=["#f2f5ed", "#a6c6ad", "#147d74", "#143c3b"],
        labels={"x": "Factor", "y": "Metadata variable", "color": "Effect size"},
    )
)
section_heading(
    "02",
    "Look inside a factor",
    "The 20 largest absolute loadings identify its strongest feature contributions.",
)
loadings = table(
    "ngs/coverage_factor_loadings.parquet" if ngs else "factors/factor_loadings.parquet"
)
available = loadings if ngs else loadings[loadings.modality == modality]
factor = st.selectbox("Factor", sorted(available.factor.unique()))
st.dataframe(
    available[available.factor == factor]
    .assign(magnitude=lambda x: x.loading.abs())
    .nlargest(20, "magnitude"),
    use_container_width=True,
    hide_index=True,
)
with st.expander("Negative-binomial target evidence" if ngs else "Full factor evidence"):
    st.dataframe(
        table("ngs/coverage_model_results.parquet")
        if ngs
        else table("factors/factor_summary.parquet").query("modality == @modality"),
        use_container_width=True,
        hide_index=True,
    )
