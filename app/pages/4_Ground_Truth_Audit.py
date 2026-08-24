import streamlit as st
from common import choose_another_run, report_model, run_dir, table

choose_another_run()
st.title("Ground-Truth Audit")
model = report_model()
if not model["ground_truth"]["supplied"]:
    st.info("Not included: ground_truth_not_supplied. This page is for synthetic benchmark runs.")
else:
    st.warning("Synthetic recovery evidence is separate from observational evidence.")
    st.json(model["ground_truth"])
    if model.get("analysis_type") == "targeted_ngs":
        if (run_dir() / "ground_truth/ngs_coverage_recovery.json").exists():
            st.subheader("Coverage recovery")
            st.json(
                __import__("json").loads(
                    (run_dir() / "ground_truth/ngs_coverage_recovery.json").read_text()
                )
            )
        if (run_dir() / "ground_truth/ngs_variant_recovery.json").exists():
            st.subheader("Variant and artifact recovery")
            st.json(
                __import__("json").loads(
                    (run_dir() / "ground_truth/ngs_variant_recovery.json").read_text()
                )
            )
    elif (run_dir() / "ground_truth/feature_recovery.parquet").exists():
        st.dataframe(table("ground_truth/feature_recovery.parquet"), use_container_width=True)
