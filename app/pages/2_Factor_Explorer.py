import plotly.express as px
import streamlit as st
from common import choose_another_run, report_model, table

choose_another_run()
model = report_model()
st.title(
    "Coverage Factor Explorer"
    if model.get("analysis_type") == "targeted_ngs"
    else "Factor Explorer"
)
associations = table(
    "ngs/coverage_factor_associations.parquet"
    if model.get("analysis_type") == "targeted_ngs"
    else "factors/factor_metadata_associations.parquet"
)
if model.get("analysis_type") == "targeted_ngs":
    st.warning(
        "Derived count-aware diagnostic representation; original target counts are unchanged."
    )
    heat = associations.pivot(index="variable", columns="factor", values="effect_size")
    st.plotly_chart(
        px.imshow(
            heat, text_auto=".2f", aspect="auto", title="Coverage factor–metadata effect size"
        ),
        use_container_width=True,
    )
    factor = st.selectbox("Factor", sorted(associations.factor.unique()))
    loadings = table("ngs/coverage_factor_loadings.parquet")
    st.dataframe(
        loadings[loadings.factor == factor]
        .assign(magnitude=lambda x: x.loading.abs())
        .nlargest(20, "magnitude"),
        use_container_width=True,
    )
    st.subheader("Negative-binomial target evidence")
    st.dataframe(table("ngs/coverage_model_results.parquet"), use_container_width=True)
    st.stop()
modality = st.selectbox("Modality", sorted(associations.modality.unique()))
view = associations[associations.modality == modality]
heat = view.pivot(index="variable", columns="factor", values="effect_size")
st.plotly_chart(
    px.imshow(heat, text_auto=".2f", aspect="auto", title="Factor–metadata effect size"),
    use_container_width=True,
)
loadings = table("factors/factor_loadings.parquet")
factor = st.selectbox("Factor", sorted(loadings[loadings.modality == modality].factor.unique()))
st.dataframe(
    loadings[(loadings.modality == modality) & (loadings.factor == factor)]
    .assign(magnitude=lambda x: x.loading.abs())
    .nlargest(20, "magnitude"),
    use_container_width=True,
)
st.subheader("Factor evidence")
st.dataframe(
    table("factors/factor_summary.parquet").query("modality == @modality"), use_container_width=True
)
