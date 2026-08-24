# Artifactor

Version 0.5.0 adds a guided start screen, ordinary single- or multi-matrix project creation, automatic sample-orientation inspection, metadata-role review, preflight design checks, recent-run reopening, and prominent corrected-data downloads. See [getting started](docs/getting_started.md).

## Start here

```powershell
uv sync --all-extras
uv run artifactor start
```

Choose **Analyze my data**, **Try a demonstration**, or **Open a completed run**. Normal studies do not require hand-written YAML or a custom public-dataset adapter.

**Artifactor helps determine whether an observed multi-omic signal is likely biological, technical, mixed, or not identifiable from the current study design.**

Version 0.3.0 adds targeted-NGS artifact investigation from analysis-ready coverage and allele-count tables. It audits callability and panel compatibility, fits count-aware coverage and sampling-aware VAF diagnostics, localizes run/lot and FFPE-like evidence, and refuses unsafe mitigation. Original counts, VAF observations, and call states are immutable. Artifactor is a research prototype: associations are not causal or clinical conclusions.

![Artifactor workflow](docs/workflow.svg)

## Example decision

In the balanced synthetic cohort, a condition-associated latent factor is retained while a processing-batch factor is reduced. In the confounded cohort, Artifactor refuses automated correction and recommends bridge samples or randomized reprocessing.

## Quick start

```bash
uv sync --all-extras
uv run artifactor init --input expression.csv --metadata metadata.csv --project projects/my-study --biological condition --technical batch --protected condition
uv run artifactor preflight --config projects/my-study/config.yaml
uv run artifactor analyze --config projects/my-study/config.yaml
uv run artifactor outputs --run projects/my-study/results/<run>

# Or run the built-in demonstration:
uv run artifactor simulate --scenario separable --output demo/separable
uv run artifactor analyze --config demo/separable/config.yaml
uv run artifactor inspect --run demo/separable/results/separable-demo-<fingerprint>
uv run artifactor inspect --run demo/separable/results/separable-demo-<fingerprint> --section factors
uv run artifactor report --run demo/separable/results/separable-demo-<fingerprint> --standalone
uv run artifactor serve --run demo/separable/results/separable-demo-<fingerprint>
```

Repeat the first two commands with `--scenario confounded --output demo/confounded` to reproduce the safety demonstration: the run completes successfully but refuses correction because biology and batch are not independently identifiable. Use `cross_modal` or `plate_drift` for the other deterministic demonstrations. The `quick` budget uses compact resampling; `standard` is intended for the complete analysis settings.

Open `report/artifactor-report.html` directly in a browser; it has no network dependency. Run `uv run artifactor capabilities` before configuring non-continuous inputs.

For targeted NGS, run `uv run artifactor simulate --scenario ngs_separable --output demo/ngs`, then analyze its `config.yaml`. The analyze command prints the exact run directory; open `<run-directory>/report/artifactor-report.html`. Corrected genomic data is intentionally not emitted: `ngs/representations/` contains explicitly exploratory coverage views while source coverage counts, allele counts, VAFs, and calls remain unchanged.

## What happens

1. Strict YAML and matrix validation aligns samples and rejects raw counts without an explicit transform.
2. A rank, overlap, and pairwise confounding audit gates all correction.
3. Robustly scaled modality PCA and Frobenius-balanced block PCA expose major variation.
4. Metadata association and partial technical variance quantify evidence.
5. Candidate corrections are scored for technical predictability, biological retention, and cross-modal concordance.
6. Targeted-NGS routes add negative-binomial coverage, sampling-aware allele, context, callability, control, and replicate evidence.
7. Persisted artifacts drive both a standalone HTML report and a read-only Streamlit UI.

The Python package contains all scientific logic. Nextflow only orchestrates the same CLI, and the UI never refits models.

## Reproducibility and scaling

Each run directory is named from normalized configuration, input checksums, package version, and seed. `run.json` records timestamps, versions, host details, stage timings, warnings, and checksums. The included Nextflow profiles cover local, Docker, Slurm/Apptainer, and documented AWS Batch placeholders without provisioning infrastructure.

## Limitations

The NGS route accepts analysis-ready long-form coverage and allele-count summaries, not FASTQ, BAM, CRAM, VCF, or BCF. It does not call variants, inspect reads, delete calls, or provide clinical validation. Normalized/residual coverage representations are exploratory and never overwrite input. Continuous-data `combat` is rejected for NGS counts and fractions. Causal inference and clinical use are out of scope.

## Development

```bash
ruff check .
ruff format --check .
mypy artifactor
pytest -m "not slow"
```

See [targeted-NGS guide](docs/targeted_ngs.md), [methods](docs/methods.md), [metric definitions](docs/metric_definitions.md), [data contract](docs/data_contract.md), [modality extension guide](docs/modality_extension_guide.md), [architecture](docs/architecture.md), and the [demo scripts](docs/demo_script.md).
Measured quick/standard results and their test dimensions are in [benchmarks](docs/benchmarks.md).
