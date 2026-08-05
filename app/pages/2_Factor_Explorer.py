import plotly.express as px
import streamlit as st
from common import table

st.title("Factor Explorer")
associations = table("diagnostics/associations.parquet")
modality = st.selectbox("Modality", sorted(associations.modality.unique()))
view = associations[associations.modality == modality]
heat = view.pivot(index="variable", columns="factor", values="effect_size")
st.plotly_chart(
    px.imshow(heat, text_auto=".2f", aspect="auto", title="Factor–metadata effect size"),
    use_container_width=True,
)
loadings = table("diagnostics/loadings.parquet")
factor = st.selectbox("Factor", sorted(loadings[loadings.modality == modality].factor.unique()))
st.dataframe(
    loadings[(loadings.modality == modality) & (loadings.factor == factor)]
    .assign(magnitude=lambda x: x.loading.abs())
    .nlargest(20, "magnitude"),
    use_container_width=True,
)
