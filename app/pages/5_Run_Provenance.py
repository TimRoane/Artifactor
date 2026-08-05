import streamlit as st
from common import downloads, json_file

st.title("Run Provenance")
st.json(json_file("run.json"))
st.subheader("Resource use")
st.json(json_file("telemetry/resources.json"))
st.subheader("Input checksums")
st.json(json_file("input_checksums.json"))
downloads()
