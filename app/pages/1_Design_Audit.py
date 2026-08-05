import streamlit as st
from common import json_file, table

st.title("Design Audit")
audit = json_file("design/audit.json")
st.json(audit["design"])
st.dataframe(table("design/confounding.parquet"), use_container_width=True)
if not audit["eligibility"]["eligible"]:
    st.error("Correction is refused: " + "; ".join(audit["eligibility"]["reasons"]))
else:
    st.success("The configured correction design is eligible.")
