import streamlit as st
from common import choose_another_run, json_file

choose_another_run()
st.title("Root-Cause Evidence")
st.warning("These are calibrated hypotheses, not causal or clinical conclusions.")
for finding in json_file("interpretation/evidence_cards.json"):
    st.subheader(finding["title"])
    st.write(finding["observation"])
    st.json(finding["supporting_evidence"])
    st.caption("Limitations: " + "; ".join(finding["limitations"]))
    st.write("Proposed confirmation: " + finding["recommended_follow_ups"][0]["experiment"])
