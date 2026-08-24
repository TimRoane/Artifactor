import streamlit as st
from common import choose_another_run, downloads, json_file

choose_another_run()
st.title("Reproducibility and Downloads")
st.json(json_file("provenance/run_manifest.json"))
st.subheader("Resource use")
st.json(json_file("telemetry/resources.json"))
st.subheader("Input checksums")
st.json(json_file("input_checksums.json"))
downloads()
