# Artifactor: Codex-Ready Implementation Plan

> Historical planning document: its original MIT licensing task is superseded by the current proprietary [Source Inspection License](LICENSE).

> Implementation status (2026-08-05): phases 0–10 are implemented in v0.1.0. The
> Python CLI, four deterministic simulations, design gate, diagnostics, correction
> comparison, preservation audit, reports, six-page UI, portable workflow profiles,
> tests, documentation, and benchmark are present. Environment-dependent release
> verification is tracked by CI.

Repository name: `artifactor-omics`

Tagline: **An assay-aware platform for identifying technical artifacts while preserving biological signal in multi-omics cohorts.**

## 1. Mission

Build a portfolio-quality prototype that accepts cohort metadata and two or more analysis-ready omics matrices, identifies the major sources of variation, classifies those sources as biological, technical, mixed, or unexplained, compares candidate mitigation methods, and generates a scientist-facing root-cause report.

The prototype must demonstrate five capabilities:

1. Cohort-level statistical reasoning rather than sample-by-sample QC alone.
2. Separation of technical and biological variation without blindly correcting every batch effect.
3. Assay-aware interpretation that leads to testable wet-lab follow-up recommendations.
4. Reproducible execution locally, on HPC, and on cloud batch infrastructure.
5. Efficient analysis of high-dimensional data with measurable runtime and resource use.

The central product claim is deliberately narrow:

> Artifactor helps determine whether an observed multi-omic signal is likely biological, technical, mixed, or not identifiable from the current study design.

Artifactor is a research prototype. It must not make clinical claims or imply that an association proves an assay root cause.

## 2. Portfolio Demo Outcome

The finished repository must support this demonstration:

```bash
git clone <repository-url>
cd artifactor-omics
uv sync --all-extras

artifactor simulate --scenario separable --output demo/separable
artifactor analyze --config demo/separable/config.yaml
artifactor serve --run results/<run_id>
```

Within five minutes, a reviewer must be able to see:

- A biological condition driving one latent factor.
- A reagent-lot or processing-batch artifact driving another factor.
- The amount of variance attributed to each source.
- A comparison of uncorrected, residualized, and ComBat-corrected data.
- A recommendation selected from a biological-preservation versus technical-removal Pareto analysis.
- A wet-lab-oriented explanation and proposed confirmation experiment.
- Runtime, peak-memory, and reproducibility information.

A second command must demonstrate a deliberately confounded experiment:

```bash
artifactor simulate --scenario confounded --output demo/confounded
artifactor analyze --config demo/confounded/config.yaml
```

Expected result:

> Correction not recommended. Biological condition and processing batch are not independently identifiable from this cohort.

## 3. Scope

### 3.1 MVP modalities

- Bulk RNA expression, represented as normalized continuous values for the primary MVP.
- Protein abundance, represented as normalized continuous values.
- A generic continuous-matrix modality for additional assay types.

RNA counts may be accepted as an optional input type, but the initial correction comparison operates on transformed continuous data. Do not silently run continuous-data correction on raw counts.

### 3.2 MVP inputs

- One cohort manifest.
- Two or more sample-by-feature matrices.
- One YAML configuration file.
- Optional cross-modality feature map, such as gene-to-protein mappings.
- Optional feature annotations and known biological signatures.

### 3.3 Explicit non-goals

- Raw FASTQ processing.
- Full differential-expression or pathway-enrichment platforms.
- Single-cell integration.
- Causal inference from observational metadata.
- Automated deletion of samples.
- Automatic application of a correction when biological and technical variables are inseparable.
- Production authentication, multi-tenancy, or PHI handling.
- Deployment of real paid cloud infrastructure as part of the default demo.

## 4. Product Principles

1. **Audit before correction.** Run study-design and confounding checks first.
2. **Preserve biology explicitly.** Every correction method is evaluated against declared biological variables and known signals.
3. **Treat correction as a model comparison problem.** There is no universally preferred method.
4. **Keep technical and scientific evidence inspectable.** Every result links to its inputs, parameters, and method.
5. **Refuse unsupported conclusions.** Confounded designs produce warnings or a no-correction recommendation.
6. **Generate hypotheses, not causal declarations.** Root-cause statements must use calibrated language.
7. **Keep core analysis independent of the UI.** CLI, workflow, and UI all call the same Python package.
8. **Make the demo deterministic.** Every stochastic method uses a recorded seed.

## 5. Technology Decisions

### 5.1 Core stack

- Python 3.12.
- `uv` for dependency and environment management.
- Polars and PyArrow for tabular I/O.
- NumPy and SciPy for numerical work.
- scikit-learn for decomposition, prediction, cross-validation, and preprocessing.
- statsmodels or vectorized NumPy linear models for statistical tests.
- Pydantic v2 for configuration and data contracts.
- Typer for the CLI.
- Plotly for interactive plots.
- Streamlit for the portfolio UI.
- Jinja2 plus Plotly HTML fragments for a standalone report.
- pytest, Hypothesis, Ruff, and mypy for quality checks.
- Nextflow DSL2 for portable orchestration.
- Docker for local/cloud containers and Apptainer compatibility for HPC.

### 5.2 Optional integrations

- `inmoose` or another maintained Python implementation for ComBat.
- MOFA2 through a separately isolated optional environment after the Python-native MVP works.
- psutil for local resource telemetry.

Optional integrations must never be required to run the default demo.

### 5.3 Dependency policy

- Commit `pyproject.toml` and `uv.lock`.
- Pin the Python base container by digest before the final release.
- Record package versions in every run manifest.
- Keep optional heavy dependencies behind extras such as `artifactor[mofa]`.

## 6. Repository Layout

```text
artifactor-omics/
â”œâ”€â”€ README.md
â”œâ”€â”€ LICENSE
â”œâ”€â”€ CITATION.cff
â”œâ”€â”€ CONTRIBUTING.md
â”œâ”€â”€ pyproject.toml
â”œâ”€â”€ uv.lock
â”œâ”€â”€ Dockerfile
â”œâ”€â”€ compose.yaml
â”œâ”€â”€ nextflow.config
â”œâ”€â”€ main.nf
â”œâ”€â”€ conf/
â”‚   â”œâ”€â”€ base.config
â”‚   â”œâ”€â”€ local.config
â”‚   â”œâ”€â”€ docker.config
â”‚   â”œâ”€â”€ slurm.config
â”‚   â””â”€â”€ awsbatch.config
â”œâ”€â”€ artifactor/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ cli.py
â”‚   â”œâ”€â”€ config.py
â”‚   â”œâ”€â”€ logging.py
â”‚   â”œâ”€â”€ contracts/
â”‚   â”‚   â”œâ”€â”€ manifest.py
â”‚   â”‚   â”œâ”€â”€ matrix.py
â”‚   â”‚   â””â”€â”€ validation.py
â”‚   â”œâ”€â”€ io/
â”‚   â”‚   â”œâ”€â”€ matrices.py
â”‚   â”‚   â”œâ”€â”€ tables.py
â”‚   â”‚   â””â”€â”€ provenance.py
â”‚   â”œâ”€â”€ modalities/
â”‚   â”‚   â”œâ”€â”€ base.py
â”‚   â”‚   â”œâ”€â”€ generic.py
â”‚   â”‚   â”œâ”€â”€ rna.py
â”‚   â”‚   â””â”€â”€ proteomics.py
â”‚   â”œâ”€â”€ design/
â”‚   â”‚   â”œâ”€â”€ confounding.py
â”‚   â”‚   â”œâ”€â”€ overlap.py
â”‚   â”‚   â””â”€â”€ design_matrix.py
â”‚   â”œâ”€â”€ diagnostics/
â”‚   â”‚   â”œâ”€â”€ latent.py
â”‚   â”‚   â”œâ”€â”€ associations.py
â”‚   â”‚   â”œâ”€â”€ variance.py
â”‚   â”‚   â”œâ”€â”€ missingness.py
â”‚   â”‚   â””â”€â”€ outliers.py
â”‚   â”œâ”€â”€ correction/
â”‚   â”‚   â”œâ”€â”€ base.py
â”‚   â”‚   â”œâ”€â”€ none.py
â”‚   â”‚   â”œâ”€â”€ residualize.py
â”‚   â”‚   â””â”€â”€ combat.py
â”‚   â”œâ”€â”€ evaluation/
â”‚   â”‚   â”œâ”€â”€ technical.py
â”‚   â”‚   â”œâ”€â”€ biological.py
â”‚   â”‚   â”œâ”€â”€ concordance.py
â”‚   â”‚   â”œâ”€â”€ stability.py
â”‚   â”‚   â””â”€â”€ pareto.py
â”‚   â”œâ”€â”€ interpretation/
â”‚   â”‚   â”œâ”€â”€ evidence.py
â”‚   â”‚   â”œâ”€â”€ rules.py
â”‚   â”‚   â””â”€â”€ recommendations.py
â”‚   â”œâ”€â”€ simulation/
â”‚   â”‚   â”œâ”€â”€ generator.py
â”‚   â”‚   â”œâ”€â”€ artifacts.py
â”‚   â”‚   â””â”€â”€ scenarios.py
â”‚   â”œâ”€â”€ reporting/
â”‚   â”‚   â”œâ”€â”€ builder.py
â”‚   â”‚   â”œâ”€â”€ plots.py
â”‚   â”‚   â””â”€â”€ templates/
â”‚   â””â”€â”€ telemetry/
â”‚       â”œâ”€â”€ resources.py
â”‚       â””â”€â”€ nextflow_trace.py
â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ Home.py
â”‚   â””â”€â”€ pages/
â”‚       â”œâ”€â”€ 1_Design_Audit.py
â”‚       â”œâ”€â”€ 2_Factor_Explorer.py
â”‚       â”œâ”€â”€ 3_Correction_Comparison.py
â”‚       â”œâ”€â”€ 4_Root_Cause_Report.py
â”‚       â””â”€â”€ 5_Run_Provenance.py
â”œâ”€â”€ workflows/
â”‚   â””â”€â”€ modules/
â”‚       â”œâ”€â”€ validate.nf
â”‚       â”œâ”€â”€ preprocess.nf
â”‚       â”œâ”€â”€ diagnose.nf
â”‚       â”œâ”€â”€ correct.nf
â”‚       â”œâ”€â”€ evaluate.nf
â”‚       â””â”€â”€ report.nf
â”œâ”€â”€ configs/
â”‚   â”œâ”€â”€ example.yaml
â”‚   â””â”€â”€ schemas/
â”œâ”€â”€ demo/
â”œâ”€â”€ tests/
â”‚   â”œâ”€â”€ unit/
â”‚   â”œâ”€â”€ integration/
â”‚   â”œâ”€â”€ regression/
â”‚   â””â”€â”€ fixtures/
â”œâ”€â”€ docs/
â”‚   â”œâ”€â”€ architecture.md
â”‚   â”œâ”€â”€ methods.md
â”‚   â”œâ”€â”€ data_contract.md
â”‚   â”œâ”€â”€ interpretation_guide.md
â”‚   â””â”€â”€ demo_script.md
â””â”€â”€ .github/workflows/
    â”œâ”€â”€ test.yml
    â””â”€â”€ container.yml
```

## 7. Input Data Contract

### 7.1 Manifest

The manifest is one row per sample. Required fields:

```text
sample_id
```

Optional but recognized fields:

```text
subject_id
condition
sex
age
collection_site
extraction_batch
library_prep_batch
sequencing_run
plate
plate_row
plate_column
operator
instrument
reagent_lot
RIN
DV200
freeze_thaw_cycles
```

The configuration, not column naming heuristics, defines each variable's role:

- `biological`: variables whose signal should be retained.
- `technical`: known or suspected artifact sources.
- `protected`: variables that must not be regressed out.
- `identifier`: sample or subject identifiers.
- `ignore`: metadata not included in modeling.

### 7.2 Modality matrices

Internal representation is sample-by-feature:

```text
sample_id,feature_001,feature_002,...
S001,4.2,8.1,...
S002,3.9,7.8,...
```

Requirements:

- Sample IDs are unique.
- Feature names are unique within a modality.
- Numeric values are finite or explicitly missing.
- Every matrix has at least three samples after overlap filtering.
- Input orientation is declared. A reader may transpose feature-by-sample input once during ingestion.
- All analyses operate on the intersection or configured union of samples; the selected policy is recorded.

Prefer Parquet. CSV and TSV are accepted for convenience and converted to cached Parquet during ingestion.

### 7.3 Configuration schema

Implement and document this minimum configuration:

```yaml
project:
  name: separable-demo
  output_dir: results
  random_seed: 20260805

manifest:
  path: demo/separable/manifest.parquet
  sample_id_column: sample_id
  subject_id_column: subject_id

variables:
  biological: [condition, sex]
  technical: [extraction_batch, reagent_lot, RIN]
  protected: [condition, sex]

modalities:
  - name: rna
    kind: rna_continuous
    path: demo/separable/rna.parquet
    orientation: samples_by_features
    transform: none
    max_features: 5000
  - name: protein
    kind: proteomics_continuous
    path: demo/separable/protein.parquet
    orientation: samples_by_features
    transform: none
    max_features: 2000

analysis:
  sample_join: intersection
  latent_components: 10
  p_adjust_method: fdr_bh
  permutations: 999
  cross_validation_folds: 5
  bootstrap_iterations: 100
  analysis_budget: standard

corrections:
  methods: [none, residualize, combat]
  refuse_if_rank_deficient: true
  maximum_confounding_score: 0.85

report:
  title: Artifactor Separable Demo
  include_interactive_plots: true
```

Pydantic must reject unknown configuration keys by default so spelling errors cannot silently alter an analysis.

## 8. Stable Python Interfaces

Define these interfaces before implementing analytical modules.

```python
class ModalityPlugin(Protocol):
    name: str

    def validate(self, matrix: OmicsMatrix, metadata: pl.DataFrame) -> ValidationResult: ...
    def preprocess(self, matrix: OmicsMatrix, config: ModalityConfig) -> OmicsMatrix: ...
    def qc_metrics(self, matrix: OmicsMatrix, metadata: pl.DataFrame) -> pl.DataFrame: ...
    def interpret_feature_pattern(self, evidence: FeatureEvidence) -> list[Hypothesis]: ...
```

```python
class CorrectionMethod(Protocol):
    name: str

    def validate_design(self, context: AnalysisContext) -> EligibilityResult: ...
    def fit(self, train: OmicsMatrix, context: AnalysisContext) -> FittedCorrection: ...
    def transform(self, data: OmicsMatrix, fitted: FittedCorrection) -> OmicsMatrix: ...
```

```python
@dataclass(frozen=True)
class RunArtifact:
    artifact_type: str
    path: Path
    checksum: str
    schema_version: str
    producer: str
```

Core algorithms must accept typed inputs and return typed result objects. They must not read global configuration or write files directly. I/O belongs in orchestration layers.

## 9. Analytical Design

### 9.1 Preprocessing

For each modality:

1. Align samples to the manifest.
2. Calculate missingness by sample and feature.
3. Remove invariant features.
4. Apply only the configured transformation.
5. Standardize features using robust centering and scaling for latent analysis.
6. Retain the original transformed matrix for correction and output.
7. Select the most variable features when `max_features` is set.

Use median and MAD-based scaling for the default latent analysis. If MAD is zero, fall back to standard deviation; if both are zero, remove the invariant feature.

Never silently impute missing values. The initial latent implementation may use median imputation solely for decomposition, but must emit an imputation mask and state that the corrected data matrix still preserves missingness.

### 9.2 Modality-specific latent factors

Use randomized PCA for each modality:

- Components are deterministic given the seed.
- Record explained variance ratios.
- Store sample scores and feature loadings.
- Orient each component deterministically by making the largest absolute loading positive.

### 9.3 Joint multi-omic factors

Implement a Python-native joint factor baseline:

1. Robustly standardize features within each modality.
2. Scale each modality block to unit Frobenius norm so the modality with the most features does not dominate.
3. Concatenate blocks by matched sample.
4. Run randomized PCA on the concatenated matrix.
5. Report the contribution of each modality to every joint factor from squared loadings.

Call this method `block_pca`, not MOFA. Add MOFA2 later as an optional adapter and compare its factors against `block_pca`.

### 9.4 Metadata association testing

For every latent factor and declared metadata variable:

- Categorical variable: calculate effect size using eta-squared from a one-way model and a permutation p-value.
- Continuous variable: calculate Spearman correlation and a permutation p-value.
- Binary variable: additionally report standardized mean difference.
- Adjust p-values within each analysis family using Benjamini-Hochberg FDR.

Output a tidy association table:

```text
modality,factor,variable,role,variable_type,effect_size,p_value,q_value,n
```

Classification rules:

- `biological`: strongest supported associations are biological and no technical association exceeds the mixed threshold.
- `technical`: strongest supported associations are technical and no protected association exceeds the mixed threshold.
- `mixed`: both biological/protected and technical evidence exceed configured thresholds.
- `unexplained`: no declared variable has sufficient evidence.

Thresholds must be configuration values and included in the report.

### 9.5 Feature-wise variance attribution

For each feature, fit nested linear models in matrix form:

```text
reduced: feature ~ biological + protected covariates
full:    feature ~ biological + protected covariates + technical covariates
```

Compute partial technical variance:

```text
partial_R2_technical = (SSE_reduced - SSE_full) / SSE_reduced
```

Also calculate partial variance for each technical variable by comparing full and variable-dropped models.

Implementation requirements:

- Construct the design matrix once.
- Solve all features in blocks using NumPy linear algebra.
- Detect rank deficiency before fitting.
- Do not report negative partial R-squared values; retain raw values internally and clamp presentation values to zero with a warning count.
- Record features with insufficient observations.

### 9.6 Confounding and identifiability audit

This gate runs before any correction.

Checks:

- Rank and condition number of the combined design matrix.
- Cross-tabulation and support overlap for categorical biology versus categorical technical variables.
- Corrected Cramer's V for categorical pairs.
- Eta-squared for categorical versus continuous pairs.
- Absolute Spearman correlation for continuous pairs.
- Minimum samples per biological-by-batch cell.
- Whether each biological level appears in at least two technical levels when possible.

Produce one result per biological-technical pair:

```text
biological_variable
technical_variable
association_score
overlap_score
identifiability_status
reason
```

Statuses:

- `separable`
- `weak_overlap`
- `highly_confounded`
- `non_identifiable`

Correction eligibility rules:

- Reject correction if the relevant design matrix is rank deficient.
- Reject correction when a protected biological variable is non-identifiable from the requested technical variable.
- Permit correction with a prominent warning for weak overlap.
- Never override the gate automatically based on downstream improvement scores.

### 9.7 Correction methods

Implement three strategies.

#### No correction

- Pass data through unchanged.
- Establish the baseline for every metric.

#### Covariate-aware residualization

For each feature, fit:

```text
Y = intercept + B * beta_biology + T * beta_technical + error
```

Return:

```text
Y_corrected = Y - T * beta_technical
```

Requirements:

- Prese…1125 tokens truncated…ent processes.

Default dimensions:

- 240 samples.
- 2 biological conditions.
- 3 processing batches.
- 2 reagent lots.
- 2 modalities.
- 2,000 RNA features.
- 500 protein features.
- 200 mapped RNA-protein feature pairs.

Generate:

- Shared biological latent factors.
- Modality-specific biological factors.
- Batch offsets.
- Multiplicative reagent-lot effects.
- Sample-quality effects tied to RIN.
- Plate or run-order drift.
- Abundance-dependent missingness in protein data.
- Unaffected null features.

Scenarios:

1. `separable`: condition is balanced across batches; one removable technical artifact.
2. `confounded`: condition and batch are nearly or completely aligned; correction must be refused.
3. `cross_modal`: a real shared biological factor plus an RNA-only extraction artifact.
4. `plate_drift`: continuous well-order drift and edge-associated missingness.

Each scenario writes:

```text
manifest.parquet
rna.parquet
protein.parquet
feature_map.parquet
ground_truth.parquet
config.yaml
README.md
```

The simulator is part of the tested package, not a notebook-only helper.

## 11. CLI Contract

Implement these commands:

```bash
artifactor --version
artifactor simulate --scenario <name> --output <directory> [--seed <integer>]
artifactor validate --config <config.yaml>
artifactor analyze --config <config.yaml> [--resume]
artifactor report --run <run-directory>
artifactor serve --run <run-directory> [--port 8501]
artifactor inspect --run <run-directory>
```

Behavior:

- `validate` performs schema, sample, feature, and design checks without fitting correction models.
- `analyze` runs the complete Python-native workflow.
- `report` rebuilds the report only from saved analysis artifacts.
- `serve` launches the Streamlit application for a completed run.
- `inspect` prints a concise text summary suitable for CI logs.
- Every failure exits nonzero and prints a specific remediation message.

## 12. Run Output Contract

Use a deterministic run fingerprint based on normalized configuration, input checksums, package version, and seed. Store results under:

```text
results/<project-name>-<fingerprint>/
```

Required outputs:

```text
run.json
resolved_config.yaml
input_checksums.json
validation.json
design/confounding.parquet
design/overlap.parquet
diagnostics/factors.parquet
diagnostics/loadings.parquet
diagnostics/associations.parquet
diagnostics/variance_partition.parquet
diagnostics/outliers.parquet
corrections/<method>/<modality>.parquet
evaluation/method_metrics.parquet
evaluation/bootstrap_metrics.parquet
evaluation/recommendation.json
interpretation/findings.json
telemetry/resources.json
report/index.html
```

`run.json` must include:

- Run fingerprint.
- Start and completion timestamps.
- Git commit when available.
- Artifactor version.
- Python and dependency versions.
- Operating system and CPU architecture.
- Random seed.
- Input checksums.
- Configuration checksum.
- Status of every stage.
- Warnings and failures.

All tabular outputs must include a schema version.

## 13. Streamlit User Experience

The UI reads completed outputs and does not recompute the analysis.

### Page 1: Overview

- Project and cohort summary.
- Sample counts by modality.
- Overall result: separable, warning, or non-identifiable.
- Recommended correction or no-correction decision.
- Top three findings.

### Page 2: Design Audit

- Biological-by-technical contingency tables.
- Confounding heatmap.
- Design-matrix rank and condition information.
- Clear explanation of why a correction is or is not eligible.

### Page 3: Factor Explorer

- PCA/joint-factor scatter plot colored by selectable metadata.
- Factor-to-metadata attribution matrix.
- Per-modality variance contributions.
- Top feature loadings.

### Page 4: Correction Comparison

- Before/after plots.
- Technical predictability versus biological retention plot.
- Metric table with bootstrap intervals.
- Eligibility warnings.
- Recommendation rationale.

### Page 5: Root-Cause Report

- Prioritized findings.
- Supporting plots and quantitative evidence.
- Limitations.
- Suggested wet-lab experiments.

### Page 6: Run Provenance

- Inputs and checksums.
- Configuration.
- Software versions.
- Runtime and memory.
- Download links for machine-readable results.

## 14. Nextflow Workflow

The Nextflow workflow calls the same CLI used locally.

Process graph:

```text
VALIDATE_INPUTS
    -> PREPROCESS_MODALITIES
    -> DESIGN_AUDIT
    -> DISCOVER_FACTORS
    -> FIT_CORRECTIONS
    -> EVALUATE_CORRECTIONS
    -> INTERPRET_FINDINGS
    -> BUILD_REPORT
```

Requirements:

- `PREPROCESS_MODALITIES` fans out by modality.
- Correction fitting fans out by eligible method and modality.
- Reports depend only on persisted outputs.
- Every process declares CPU, memory, time, and container.
- Profiles exist for local, Docker, Slurm/Apptainer, and AWS Batch.
- The AWS profile contains placeholders and documentation but creates no resources.
- Enable Nextflow trace, timeline, report, and DAG outputs.
- Support `-resume`.
- Container and reference versions are pinned for release.

Example:

```bash
nextflow run main.nf \
  -profile docker \
  --config_path demo/separable/config.yaml \
  -resume
```

## 15. Efficiency Strategy

Implement two analysis budgets.

### `quick`

- Maximum 1,000 features per modality.
- 5 latent components.
- 99 permutations.
- 3-fold cross-validation.
- 20 bootstrap iterations.

### `standard`

- Configured feature limit.
- 10 latent components.
- 999 permutations.
- 5-fold cross-validation.
- 100 bootstrap iterations.

Efficiency requirements:

- Convert CSV/TSV to Parquet once and reuse the cache.
- Use randomized decomposition.
- Fit feature-wise linear models in blocks.
- Avoid materializing duplicate matrices where views suffice.
- Parallelize independent modality and correction evaluations.
- Record stage-level runtime and memory.
- Add a benchmark command or script comparing quick and standard budgets.

Do not add Spark, Kubernetes, or a distributed database to the MVP. Demonstrate appropriate scaling decisions rather than infrastructure for its own sake.

## 16. Testing Strategy

### 16.1 Unit tests

Test:

- Configuration validation and rejection of unknown keys.
- Matrix orientation and sample alignment.
- Invariant-feature handling.
- Robust scaling.
- Deterministic PCA orientation.
- Association statistics against small hand-calculated fixtures.
- Benjamini-Hochberg adjustment.
- Design rank and confounding rules.
- Residualization preserves declared biological coefficients.
- Missingness is preserved.
- Pareto selection logic.
- Interpretation wording never emits prohibited causal language.

### 16.2 Property-based tests

Use Hypothesis to verify:

- Reordering samples does not change results after alignment.
- Reordering features changes no scalar metrics.
- Adding a constant to a feature does not change standardized latent results.
- A zero technical effect does not produce systematic technical attribution.
- Increasing an injected batch effect increases expected technical evidence.

### 16.3 Integration tests

- Run `validate`, `analyze`, and `report` on a tiny fixture.
- Confirm every required output exists and satisfies its schema.
- Run the same config twice and compare fingerprints and numerical results.
- Run the Nextflow local profile on the tiny fixture.
- Load every Streamlit page using a completed fixture without recomputation errors.

### 16.4 Scientific regression tests

Use fixed seeds and metric tolerances rather than exact plot snapshots.

`separable` acceptance criteria:

- Injected technical variable appears among the top two technical associations.
- Artifact-feature precision and recall are each at least 0.75.
- Recommended correction reduces technical predictability by at least 40% relative to baseline.
- Biological predictability loss is less than 5%.
- The run recommends an eligible correction or explains why no material improvement exists.

`confounded` acceptance criteria:

- Confounding status is `non_identifiable` or `highly_confounded`.
- Automated correction is refused under the default policy.
- Report proposes a design or bridging experiment.

`cross_modal` acceptance criteria:

- Shared biological factor is detected in both modalities.
- RNA-only artifact is attributed primarily to RNA.
- Correction does not reduce mapped RNA-protein concordance by more than 10%.

`plate_drift` acceptance criteria:

- Run-order or plate-position evidence is detected.
- Root-cause report recommends randomized layout, bridge controls, or plate-position follow-up.

### 16.5 CI gates

Pull requests must pass:

```bash
ruff check .
ruff format --check .
mypy artifactor
pytest -m "not slow"
nextflow run main.nf -profile test,docker
```

Run full scientific regression tests on the main branch or a scheduled workflow.

## 17. Phased Implementation Plan

Each phase ends with working software, tests, documentation, and a focused commit. Do not begin the next phase while acceptance criteria for the current phase fail.

### Phase 0: Repository foundation

Tasks:

1. Initialize Git repository and Python package.
2. Add MIT license, README skeleton, contribution guide, and citation metadata.
3. Configure `uv`, Ruff, mypy, pytest, and pre-commit.
4. Add Typer CLI with `--version`.
5. Add GitHub Actions for linting and unit tests.
6. Add architecture decision records for Streamlit, Nextflow, Parquet, and Python 3.12.

Acceptance criteria:

- `uv sync --all-extras` succeeds.
- `artifactor --version` succeeds.
- Lint, type-check, and an initial test pass locally and in CI.

### Phase 1: Contracts and validation

Tasks:

1. Implement Pydantic configuration models.
2. Implement manifest and matrix readers.
3. Normalize sample-by-feature orientation.
4. Implement sample alignment and validation results.
5. Implement `artifactor validate`.
6. Write the data-contract documentation and tiny fixtures.

Acceptance criteria:

- Valid example inputs pass.
- Duplicate samples, duplicate features, missing declared covariates, nonnumeric data, and unknown YAML keys fail with actionable messages.
- Validation emits machine-readable JSON.

### Phase 2: Deterministic simulator

Tasks:

1. Implement shared biological latent factors.
2. Implement modality-specific noise models.
3. Implement batch, lot, quality, drift, and missingness artifact injectors.
4. Implement all four scenarios.
5. Write ground-truth tables and scenario READMEs.
6. Add `artifactor simulate`.

Acceptance criteria:

- Identical seeds produce byte-equivalent numeric datasets after canonical serialization.
- Different seeds produce different observations but the same schema.
- Ground-truth labels identify every injected signal and affected feature.

### Phase 3: Design audit

Tasks:

1. Build encoded design matrices.
2. Implement design rank and condition-number checks.
3. Implement pairwise confounding and overlap metrics.
4. Implement correction eligibility rules.
5. Produce JSON/Parquet design-audit outputs.
6. Add concise terminal rendering to `inspect`.

Acceptance criteria:

- Separable simulation passes the gate.
- Confounded simulation refuses inappropriate correction.
- Pairwise audit results explain the exact variables and support problem.

### Phase 4: Latent diagnostics and variance attribution

Tasks:

1. Implement modality preprocessing plugins.
2. Implement deterministic randomized PCA.
3. Implement block-scaled joint PCA.
4. Implement metadata association testing and FDR.
5. Implement vectorized feature-wise variance attribution.
6. Implement missingness and sample-outlier summaries.

Acceptance criteria:

- Injected biological and technical factors are detected in the separable scenario.
- Joint factors report modality contributions summing to one within tolerance.
- Results are stable to sample and feature reordering.

### Phase 5: Correction framework

Tasks:

1. Implement correction protocol and eligibility objects.
2. Implement no-correction baseline.
3. Implement covariate-aware residualization.
4. Integrate and validate ComBat.
5. Fit corrections in cross-validation without evaluation leakage.
6. Persist corrected matrices and fitted-method metadata.

Acceptance criteria:

- Protected biological coefficients remain stable in controlled tests.
- Technical effects decrease in the separable simulation.
- Confounded scenario remains blocked.
- Unsupported input types and unseen batch levels fail explicitly.

### Phase 6: Biological Preservation Audit

Tasks:

1. Implement technical predictability metrics.
2. Implement biological retention metrics.
3. Implement cross-modality concordance.
4. Implement bootstrap intervals and stability metrics.
5. Implement simulation ground-truth scoring.
6. Implement eligibility filtering and Pareto recommendation.
7. Add resource telemetry.

Acceptance criteria:

- The recommendation policy selects an acceptable correction for the separable scenario.
- No correction is recommended when candidate methods do not materially improve technical signal.
- Metric tables contain uncertainty estimates and baseline-relative changes.

### Phase 7: Interpretation and standalone report

Tasks:

1. Implement structured evidence and finding models.
2. Implement assay-aware deterministic rules.
3. Add follow-up experiment recommendations.
4. Build Plotly visualizations.
5. Generate a self-contained HTML report.
6. Implement `artifactor report` and `artifactor inspect`.

Acceptance criteria:

- Every high-priority conclusion links to quantitative evidence.
- Every hypothesis includes a limitation and follow-up experiment.
- Synthetic scenarios are the only place causal wording is permitted.
- The HTML report opens without a running backend.

### Phase 8: Streamlit application

Tasks:

1. Implement the six read-only pages.
2. Add run-directory validation.
3. Add filters for modality, factor, and metadata variable.
4. Add downloads for result tables and the HTML report.
5. Add `artifactor serve`.

Acceptance criteria:

- A reviewer can move from overview to supporting evidence in no more than three clicks.
- UI values match persisted result tables.
- Loading the UI performs no model fitting.

### Phase 9: Nextflow portability

Tasks:

1. Wrap CLI stages in DSL2 modules.
2. Add modality and correction fan-out.
3. Add local, Docker, Slurm, and AWS Batch profiles.
4. Capture trace, report, timeline, and DAG.
5. Add a local workflow integration test.
6. Document HPC and cloud configuration without provisioning resources.

Acceptance criteria:

- Local Python and Nextflow executions produce equivalent scientific outputs.
- `-resume` skips completed work.
- Every process declares resources and a container.

### Phase 10: Portfolio polish

Tasks:

1. Replace README skeleton with a decision-focused project narrative.
2. Add architecture and workflow diagrams.
3. Record a three-to-five-minute demo GIF or video.
4. Add benchmark results for quick versus standard modes.
5. Add example screenshots and the generated demo report.
6. Add limitations, future work, and scientific references.
7. Create release `v0.1.0`.

Acceptance criteria:

- A new user can run the separable demo from a clean clone using README instructions.
- The demo completes on a typical laptop.
- CI is green and the release container is pinned.
- Repository landing page explains the scientific decision before listing technologies.

## 18. Required Documentation

### README

Order:

1. One-sentence problem statement.
2. Screenshot or short animation.
3. Example finding and decision.
4. Quick start.
5. What the method does.
6. Architecture.
7. Reproducibility and scaling.
8. Validation results.
9. Limitations.
10. Development commands.

### Methods document

Must explain:

- Why confounding is assessed before correction.
- Latent factor construction.
- Metadata association statistics.
- Partial variance calculation.
- Cross-validation boundaries.
- Biological-preservation metrics.
- Recommendation rules.
- Interpretation limitations.

### Demo script

Write a spoken three-to-five-minute walkthrough:

1. State the scientific question.
2. Show the study-design audit.
3. Identify biological and technical factors.
4. Compare correction candidates.
5. Show why biology was preserved.
6. Translate the evidence into a wet-lab follow-up.
7. Show Nextflow provenance and cost telemetry.

## 19. Definition of Done for v0.1.0

The release is complete only when all conditions are met:

- Two-modality analysis works from CLI, Nextflow, and Streamlit.
- Four deterministic simulator scenarios exist.
- Design audit can refuse unsafe correction.
- Three correction strategies are compared.
- Biological Preservation Audit reports technical removal, biological retention, cross-modal retention, uncertainty, and runtime.
- A Pareto-based recommendation is generated with explicit rationale.
- Root-cause findings include evidence, limitations, and wet-lab follow-up experiments.
- A standalone HTML report is generated.
- Local, Docker, Slurm, and AWS Batch profiles are documented.
- Unit, integration, scientific regression, and workflow tests pass.
- Clean-clone quick start is verified.
- README contains a screenshot or demo animation and benchmark results.
- No core analytical logic exists only in notebooks.
- No report language overstates association as causation.

## 20. Codex Execution Instructions

When handing this plan to an implementation agent, use the following operating instructions:

1. Implement phases in order and keep this plan in the repository as `IMPLEMENTATION_PLAN.md`.
2. Before coding a phase, inspect existing work and update the phase checklist rather than recreating files.
3. Use small, reviewable commits aligned to phase acceptance criteria.
4. Run the narrowest relevant tests after each change and the full non-slow suite at each phase boundary.
5. Do not change analytical definitions or thresholds without updating methods documentation and regression tests.
6. Do not add major infrastructure or modality scope until the Python-native separable and confounded demos pass.
7. Keep the core package free of Streamlit and Nextflow dependencies.
8. Keep all stochastic behavior seeded and provenance-recorded.
9. Treat existing user changes as authoritative and do not overwrite unrelated work.
10. If an implementation detail is ambiguous, choose the simplest option that preserves the contracts and scientific acceptance criteria in this document.

Suggested initial Codex prompt:

```text
Implement Phase 0 and Phase 1 from IMPLEMENTATION_PLAN.md. Work only within
the current repository. Preserve existing files and changes. Build the smallest
complete vertical foundation: packaging, CLI, strict configuration models,
manifest/matrix readers, validation output, tests, and CI. Run all Phase 0 and
Phase 1 acceptance checks before stopping. Update IMPLEMENTATION_PLAN.md with
completed checkboxes and report any remaining blockers; do not begin Phase 2.
```

Suggested subsequent prompt:

```text
Continue with the next incomplete phase in IMPLEMENTATION_PLAN.md. First inspect
the repository and prior test results. Implement every task and acceptance
criterion in that phase, add or update tests and documentation, and run the
relevant validation commands. Do not begin a later phase. Summarize files
changed, tests run, scientific assumptions made, and any blockers.
```

## 21. Future Work After v0.1.0

Only consider these after the MVP is demonstrably complete:

- MOFA2 adapter.
- Raw-count RNA support using count-aware models.
- DNA methylation and metabolomics plugins.
- Negative-control and RUV-based unwanted-variation methods.
- Longitudinal and repeated-measures models.
- Known-control and bridge-sample analysis.
- Automated power recommendations for confirmation experiments.
- Object-store-native input and caching.
- Real AWS Batch cost collection.
- Static deployment of completed reports.
- Plugin SDK for company-specific assay rules.

