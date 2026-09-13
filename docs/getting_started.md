# Getting started with a new study

These instructions are for maintainers and users with separate written permission to install and run Artifactor. The public [source inspection license](../LICENSE) permits review of the authors' work; it does not grant execution or modification rights.

Artifactor's normal input is much simpler than its public validation case studies. You need:

1. A metadata table with one row per sample.
2. At least one numeric measurement matrix in CSV, TSV, or Parquet format.

The matrix may have samples in rows:

```text
sample_id,gene_1,gene_2,gene_3
S01,4.2,8.1,0.7
S02,5.0,7.8,0.9
```

Or features in rows, with sample IDs as column names:

```text
feature_id,S01,S02
gene_1,4.2,5.0
gene_2,8.1,7.8
```

Metadata should describe the study design:

```text
sample_id,condition,processing_batch,sex
S01,control,B1,F
S02,treated,B2,M
```

## Guided application

Install the UI extra and start the app:

```powershell
uv sync --all-extras
uv run artifactor start
```

The home screen offers:

- **Analyze my data** — upload tables, confirm sample matching, classify metadata, run preflight, and launch the analysis.
- **Try a demonstration** — see both a safe correction and a confounded study where correction is refused.
- **Open a completed run** — choose a recent project or enter a run directory.

Classify metadata carefully:

- **Biological**: variation the study is intended to measure, such as treatment, disease, tissue, or timepoint.
- **Technical**: processing variables to investigate, such as batch, plate, lane, site, instrument, or reagent lot.
- **Protected**: biological variables that correction must not remove. The guided workflow initially protects every selected biological variable.
- **Identifier**: subject, specimen, or aliquot labels retained for traceability but not modeled as effects.

Artifactor suggests roles from column names, but it requires confirmation because a column's meaning is study-specific.

## Command-line setup

```powershell
uv run artifactor init `
  --input expression.csv `
  --metadata metadata.csv `
  --project projects/my-study `
  --name "My study" `
  --biological condition `
  --technical processing_batch `
  --protected condition

uv run artifactor preflight --config projects/my-study/config.yaml
uv run artifactor analyze --config projects/my-study/config.yaml
```

Repeat `--input` for multiple modalities. Optional `--kind` values, in input order, are `rna_continuous`, `proteomics_continuous`, `genomic_continuous`, or `generic_continuous`. Filenames are used for safe kind suggestions when `--kind` is omitted.

`init` never edits the supplied files. It creates normalized Parquet copies, `config.yaml`, `project_setup.json`, and `preflight.json` inside the new project.

## Understanding the outputs

The `analyze` command prints the exact completed run directory. To locate the deliverables later:

```powershell
uv run artifactor outputs --run <run-directory>
```

Every continuous-matrix run contains:

- `report/artifactor-report.html` — standalone results report.
- `exports/corrected_data.json` — machine-readable statement of whether corrected data were generated and why.

When correction passes the design and preservation gates:

- `exports/corrected/<modality>.csv` — the selected corrected measurement matrix.
- `exports/corrected/sample_metadata.csv` — aligned metadata.

When correction is unsafe or not beneficial, the directory is deliberately absent and the export manifest explains the refusal. Candidate representations remain under `corrections/` for auditing, but only the selected method is presented as the corrected-data deliverable.

Start with normalized or otherwise analysis-ready continuous measurements. Raw FASTQ/BAM/VCF data and upstream read processing remain outside this workflow.
