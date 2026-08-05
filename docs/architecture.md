# Architecture

The CLI is the single orchestration boundary. It loads strict typed configuration and immutable matrix contracts, runs validation and the design gate, executes diagnostics and eligible corrections, evaluates candidates, persists versioned artifacts, and builds interpretation and reporting outputs. Streamlit reads those outputs without importing the analysis pipeline. Nextflow invokes the same CLI for portable execution.

Decisions: Python 3.12 supplies a typed, broadly deployable scientific runtime; Parquet provides typed columnar interoperability; Streamlit provides a small read-only scientific UI; Nextflow separates execution infrastructure from analytical definitions.
