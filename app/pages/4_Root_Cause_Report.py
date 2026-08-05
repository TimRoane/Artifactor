import streamlit as st
from common import json_file

st.title("Root-Cause Report")
st.warning("These are calibrated hypotheses, not causal or clinical conclusions.")
for finding in json_file("interpretation/findings.json"):
    st.subheader(finding["title"])
    st.write(finding["interpretation"])
    st.json(finding["evidence"])
    st.caption("Limitation: " + finding["limitation"])
    st.write("Proposed confirmation: " + finding["follow_up"])
