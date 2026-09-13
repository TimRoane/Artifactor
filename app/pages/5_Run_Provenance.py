import pandas as pd
import streamlit as st
from common import downloads, json_file, run_dir, shell
from design import page_heading, section_heading

shell("provenance_and_downloads")
page_heading(
    "THE INVESTIGATION RECORD",
    "A result you can trace.",
    "Review the run identity, resource measurements, and source checksums behind the evidence.",
)
root = run_dir()
if (root / "external_validation").exists():
    with st.expander("Run manifest", expanded=True):
        st.json(json_file("run.json"))
else:
    resources = json_file("telemetry/resources.json")
    left, middle, right = st.columns(3)
    runtime = resources.get("runtime_seconds")
    memory = resources.get("peak_memory_bytes_observed")
    left.metric("Analysis time", f"{runtime:.2f} s" if runtime is not None else "Not recorded")
    middle.metric(
        "Observed peak memory",
        f"{memory / 1024**2:.0f} MiB" if memory is not None else "Not recorded",
    )
    right.metric("Recorded stages", len(resources.get("stages", {})))
    section_heading(
        "01",
        "Where the time went",
        "Observed runtime for each recorded stage of the investigation.",
    )
    stages = resources.get("stages", {})
    if stages:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Stage": name.replace("_", " ").capitalize(),
                        "Time (seconds)": values.get("runtime_seconds"),
                        "Status": values.get("status"),
                    }
                    for name, values in stages.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    with st.expander("Run manifest"):
        st.json(json_file("provenance/run_manifest.json"))
    with st.expander("Full resource record"):
        st.json(resources)
    with st.expander("Input checksums"):
        st.json(json_file("input_checksums.json"))
downloads()
