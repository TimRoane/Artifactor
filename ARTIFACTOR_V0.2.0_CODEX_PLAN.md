# Artifactor v0.2.0 Codex Implementation Plan

Release name: **Explainable Artifact Investigation**

Repository: `artifactor-omics`

Target version: `0.2.0`

Primary objective:

> Turn the v0.1.0 correction decision into an inspectable scientific evidence chain, while introducing safe extension points for future genomic NGS modalities.

This plan assumes Artifactor v0.1.0 already accepts analysis-ready continuous RNA and protein matrices, runs a study-design audit, calculates modality-specific and joint latent factors, compares `none`, `residualize`, and `combat`, produces a Biological Preservation Audit, and generates a standalone HTML report.

---

## 1. Codex Operating Instructions

Implement this plan in the existing repository. Do not recreate the project or replace working v0.1.0 components without first inspecting them.

Before changing code:

1. Read `README.md`, `IMPLEMENTATION_PLAN.md`, `pyproject.toml`, the report generator, data contracts, diagnostics, correction evaluation, simulator, tests, and CLI entry points.
2. Run the complete existing test suite and record the baseline result.
3. Generate the seeded v0.1.0 `separable` report and retain it as a comparison artifact.
4. Inventory existing output files and schemas before adding new ones.
5. Map every requirement in this plan to existing code, a modification, or a new component.

Implementation rules:

- Preserve v0.1.0 numerical behavior unless a documented bug is fixed.
- Keep all scientific logic in the Python package, not in Jinja templates, Streamlit pages, or notebooks.
- Have the HTML report and Streamlit interface read saved artifacts; they must not recompute analysis.
- Fit preprocessing, prediction, and correction models on training folds only during evaluation.
- Never describe association as causation.
- Never apply a correction rejected by the study-design gate.
- Never apply continuous-expression correction methods to raw genomic counts, genotypes, or variant calls.
- Store thresholds and plain-language labels in versioned configuration or typed models, not scattered through templates.
- Use deterministic seeds for every stochastic procedure.
- Add or update tests in the same change that adds behavior.
- Keep commits phase-scoped and leave the repository runnable after each phase.

---

## 2. Release Outcome

After v0.2.0, a scientist unfamiliar with Artifactor must be able to open a completed report and answer these questions within approximately one minute:

1. Can the declared biology be distinguished from the suspected technical variables in this cohort?
2. What are the major patterns of variation?
3. Which patterns are biological, technical, mixed, or unexplained?
4. What did each correction method remove?
5. What declared biology did each method preserve or damage?
6. Why was the recommended output selected?
7. What evidence supports the leading artifact hypothesis?
8. What experiment should the wet-lab team run next?

The release must demonstrate two complementary outcomes:

### Separable demonstration

- Biological condition is balanced across processing batches.
- A biological factor and a technical factor are visible.
- Residualization or another eligible method removes the technical signature.
- The declared biological condition remains detectable.
- Mapped RNA-protein concordance is preserved.
- The planted technical and biological features are evaluated against simulator ground truth.

### Confounded demonstration

- Biological condition and processing batch are aligned.
- The study-design gate classifies the pair as highly confounded or non-identifiable.
- Automated correction is refused regardless of downstream apparent score improvement.
- The report explains how correction could erase true biology.
- The report proposes reprocessing, bridge controls, or study redesign.

---

## 3. Scope

### 3.1 Required v0.2.0 work

- A redesigned, scientist-facing standalone HTML report.
- Plain-language explanations for every primary result.
- A visual study-design and identifiability audit.
- A modality-specific and joint Factor Explorer.
- Before-and-after correction evidence.
- Ground-truth recovery metrics for simulated datasets.
- Traceable root-cause evidence cards.
- Downloadable machine-readable evidence artifacts.
- A typed modality capability contract that makes the core NGS-ready.
- Explicit rejection of unsupported genomic input and correction combinations.
- Updated Streamlit pages that consume the same saved evidence as the report.
- Scientific regression tests for both correction and refusal behavior.

### 3.2 Explicit non-goals

- FASTQ, BAM, CRAM, or VCF processing.
- Variant calling.
- Alignment or read-level QC calculation.
- A production-ready targeted-NGS correction method.
- Direct correction of genotypes or binary variant calls.
- A new batch-correction algorithm.
- Differential expression or pathway enrichment as a major new product area.
- Causal identification of wet-lab root causes.
- Authentication, multi-tenancy, or PHI support.
- Replacing the existing workflow engine or deployment stack.

### 3.3 Release boundary for NGS

v0.2.0 makes the architecture safe and extensible for genomic results, but full targeted-NGS support belongs in v0.3.0.

v0.2.0 may accept a generic continuous genomic summary matrix only when it satisfies the existing continuous-data contract. The report must label it as a generic continuous modality, not claim variant-level genomic support.

---

## 4. User-Facing Scientific Model

Artifactor must consistently explain its model using these concepts:

| Concept | User-facing meaning |
|---|---|
| Biological signal | Variation associated with the biological variables the analysis was instructed to preserve |
| Technical signature | Variation associated with sample handling, assay execution, instrumentation, or processing metadata |
| Mixed signal | A pattern associated with both declared biology and technical variables |
| Unexplained signal | A reproducible pattern not sufficiently associated with declared metadata |
| Separable design | Biology and technical variables have enough independent support to estimate their effects |
| Confounded design | Biology and technical variables overlap enough that their effects may not be distinguishable |
| Correction | A model-based transformation intended to reduce specified technical variation |
| Preservation | Evidence that declared biological relationships remain present after correction |

Prominently state:

> Artifactor labels patterns using declared metadata and observed associations. It does not independently know which variation is biological, and association does not establish cause.

---

## 5. Target Architecture

Keep the existing layered architecture and add evidence-oriented services.

```text
validated inputs
    -> design and identifiability audit
    -> modality diagnostics and latent factors
    -> factor-to-metadata attribution
    -> eligible correction candidates
    -> cross-validated preservation audit
    -> simulator ground-truth audit, when available
    -> evidence synthesis
    -> saved report model
    -> HTML and Streamlit presentation
```

Suggested additions:

```text
artifactor/
â”œâ”€â”€ contracts/
â”‚   â”œâ”€â”€ evidence.py
â”‚   â”œâ”€â”€ report.py
â”‚   â””â”€â”€ capabilities.py
â”œâ”€â”€ diagnostics/
â”‚   â”œâ”€â”€ factor_evidence.py
â”‚   â””â”€â”€ visualization_data.py
â”œâ”€â”€ evaluation/
â”‚   â”œâ”€â”€ ground_truth.py
â”‚   â”œâ”€â”€ effect_retention.py
â”‚   â””â”€â”€ uncertainty.py
â”œâ”€â”€ interpretation/
â”‚   â”œâ”€â”€ evidence_cards.py
â”‚   â”œâ”€â”€ language.py
â”‚   â””â”€â”€ follow_up_rules.py
â”œâ”€â”€ modalities/
â”‚   â”œâ”€â”€ capabilities.py
â”‚   â””â”€â”€ measurement_family.py
â””â”€â”€ reporting/
    â”œâ”€â”€ report_model.py
    â”œâ”€â”€ explanations.py
    â”œâ”€â”€ figures.py
    â”œâ”€â”€ sections/
    â””â”€â”€ templates/
```

Adapt these names to the existing repository instead of creating duplicate concepts.

---

## 6. Output and Schema Contracts

All new tables must include `schema_version`. All JSON files must validate through Pydantic models before report generation.

### 6.1 Required analysis outputs

```text
results/<run_id>/
â”œâ”€â”€ design/
â”‚   â”œâ”€â”€ design_summary.json
â”‚   â”œâ”€â”€ pairwise_identifiability.parquet
â”‚   â”œâ”€â”€ contingency_cells.parquet
â”‚   â””â”€â”€ design_matrix_diagnostics.json
â”œâ”€â”€ factors/
â”‚   â”œâ”€â”€ factor_summary.parquet
â”‚   â”œâ”€â”€ factor_scores.parquet
â”‚   â”œâ”€â”€ factor_loadings.parquet
â”‚   â”œâ”€â”€ factor_metadata_associations.parquet
â”‚   â””â”€â”€ modality_contributions.parquet
â”œâ”€â”€ corrections/
â”‚   â”œâ”€â”€ method_eligibility.parquet
â”‚   â”œâ”€â”€ correction_metrics.parquet
â”‚   â”œâ”€â”€ correction_metric_intervals.parquet
â”‚   â”œâ”€â”€ effect_retention.parquet
â”‚   â””â”€â”€ visualization_samples.parquet
â”œâ”€â”€ ground_truth/
â”‚   â”œâ”€â”€ feature_recovery.parquet
â”‚   â”œâ”€â”€ recovery_summary.json
â”‚   â””â”€â”€ injected_vs_estimated.parquet
â”œâ”€â”€ interpretation/
â”‚   â”œâ”€â”€ evidence_cards.json
â”‚   â””â”€â”€ recommendation.json
â”œâ”€â”€ report/
â”‚   â”œâ”€â”€ report_model.json
â”‚   â”œâ”€â”€ report_manifest.json
â”‚   â””â”€â”€ artifactor-report.html
â””â”€â”€ provenance/
    â””â”€â”€ run_manifest.json
```

If an equivalent v0.1.0 file already exists, extend it instead of creating a competing artifact.

### 6.2 Design summary

Minimum fields:

```text
schema_version
overall_status
correction_permitted
biological_variables
technical_variables
protected_variables
sample_count
design_rank
design_columns
condition_number
limiting_pairs
summary_text
```

Allowed `overall_status` values:

- `separable`
- `weak_overlap`
- `highly_confounded`
- `non_identifiable`

### 6.3 Factor summary

One row per modality and factor:

```text
schema_version
modality
factor
variance_explained
classification
classification_confidence
leading_biological_variable
leading_biological_effect_size
leading_technical_variable
leading_technical_effect_size
stability
n_samples
```

Allowed classifications:

- `biological`
- `technical`
- `mixed`
- `unexplained`

### 6.4 Correction metrics

One row per method, metric, and evaluation repeat:

```text
schema_version
method
metric_id
metric_family
value
direction
repeat_id
fold_id
n_train
n_test
eligible
ineligibility_reason
```

Store summarized intervals separately or as additional explicitly named columns. Record the interval method and confidence level.

### 6.5 Evidence cards

Each card must validate this structure:

```text
finding_id
priority
severity
classification
title
observation
supporting_evidence[]
alternative_explanations[]
limitations[]
recommended_follow_ups[]
related_modalities[]
related_factors[]
related_variables[]
artifact_links[]
```

Every evidence card must contain at least one limitation and one testable follow-up.

### 6.6 Report manifest

Record:

- Report schema version.
- Report-generation timestamp.
- Analysis run fingerprint.
- Exact source artifact checksums.
- Included and omitted sections.
- Omission reasons.
- Software version.
- Visualization sampling policy.

---

## 7. Report Information Architecture

Build one standalone report with a persistent navigation bar and seven sections. It must remain useful without Streamlit.

### 7.1 Section 1: Decision Overview

Display:

- Project name and run fingerprint.
- Number of samples and modalities.
- Study-design status.
- Recommended method or correction refusal.
- One-sentence recommendation rationale.
- Three prioritized findings.
- A prominent research-use limitation.

Required decision banner examples:

Separable:

> Residualization is recommended because it substantially reduced detectable extraction-batch information while retaining the declared biological condition and RNA-protein concordance.

Confounded:

> Automated correction is not recommended because biological condition and extraction batch cannot be estimated independently from this cohort.

Do not show only internal method names. Use display labels such as `Covariate-aware residualization`, with the internal identifier shown secondarily.

### 7.2 Section 2: Study-Design Audit

Display:

- Biological-by-technical contingency heatmaps.
- Samples per biological-by-technical cell.
- Pairwise confounding status.
- Design-matrix rank and condition number.
- The exact reason correction is permitted, warned, or refused.
- Missing combinations that limit identifiability.

Plain-language example:

> Both condition levels occur in all three extraction batches, with at least 35 samples in each condition-by-batch cell. This provides independent support for estimating condition and batch effects.

For continuous variables, display distributions by biological group and report the relevant association statistic.

Never reduce the design audit to a single green or red icon.

### 7.3 Section 3: Factor Explorer

For every modality and joint factor model, provide:

- PCA or factor-score scatter plot.
- Color selector for declared metadata.
- Variance explained for each displayed factor.
- Factor-to-metadata attribution heatmap.
- Classification badge.
- Strongest biological and technical associations.
- Top positive and negative feature loadings.
- Factor stability across bootstrap resamples.
- Modality contribution for joint factors.

Required default comparisons:

- RNA PC1 versus PC2 colored by condition.
- RNA PC1 versus PC2 colored by extraction batch.
- Protein PC1 versus PC2 colored by condition.
- Protein PC1 versus PC2 colored by extraction batch.
- Joint block-PCA scores colored by both variables.

The report must explain that PC1 is the largest observed axis of variation, PC2 is the next independent axis, and neither is inherently biological or technical.

### 7.4 Section 4: Correction Comparison

Display a correction tournament containing:

- `No correction` baseline.
- Covariate-aware residualization.
- ComBat when eligible.
- Eligibility and exclusion reasons.
- Technical predictability before and after.
- Biological predictability before and after.
- Cross-modal concordance before and after.
- Known biological effect retention when available.
- Runtime and peak memory.
- Uncertainty intervals.
- Pareto-frontier membership.

Add matched before-and-after views for every eligible method:

- Factor scatter colored by technical variable.
- The same factor scatter colored by biological variable.
- Technical predictability by variable, not only an aggregate.
- Biological predictability by variable, not only an aggregate.
- Effect-size retention for protected variables.

Plot convention:

- Horizontal axis: technical removal; farther right is better.
- Vertical axis: biological loss; lower is better.
- Mark the configured biological-loss guardrail.
- Label every method directly or provide an unambiguous legend.
- Explain that relative removal is a change in predictability, not the literal percentage of physical artifact removed.

### 7.5 Section 5: Ground-Truth Audit

Include this section only when a valid simulator ground-truth artifact is supplied.

Display:

- Biological-feature precision and recall.
- Technical-feature precision and recall.
- False technical attribution among null features.
- Recovery by artifact type and modality.
- Injected versus estimated effect plot.
- Effect RMSE.
- Biological effect retention after each correction.
- Confusion matrix for biological, technical, mixed, and null features.

Explicitly label this as synthetic validation:

> These metrics are possible because the simulator records which effects were injected. Equivalent truth labels are normally unavailable for real cohorts.

If ground truth is absent, omit the section and record `ground_truth_not_supplied` in the report manifest. Do not show empty or zero-valued metrics.

### 7.6 Section 6: Root-Cause Evidence

Present prioritized evidence cards. Each card must include:

- Observation.
- Quantitative support.
- Modalities and factors involved.
- Alternative explanations.
- Limitation.
- One or more proposed confirmation experiments.

Build findings using deterministic rules. Examples:

- Batch association across RNA and protein: consider shared sample handling, cohort allocation, or shared preprocessing.
- RNA-only RIN association: consider RNA quality or degradation.
- RIN association in protein: warn that RIN may proxy broader sample quality or correlated handling; do not imply that RIN directly caused protein changes.
- Plate-position drift: recommend randomized layouts, bridge samples, and edge-versus-center comparisons.
- Condition-batch non-identifiability: recommend reprocessing representative samples across batches.

Every card must link to the tables and figures that support it.

### 7.7 Section 7: Reproducibility and Downloads

Display:

- Artifactor version.
- Git commit, or an explicit `not available` warning.
- Random seed.
- Configuration checksum.
- Input checksums.
- Dependency versions.
- Runtime and peak memory by stage.
- Warnings and failures.
- Download links for report-model JSON and primary evidence tables.

Do not expose large raw tables inline. Provide summarized previews and downloads.

---

## 8. Metric Definitions and Display Language

Create one registry that defines every metric used by analysis and reporting.

Each metric definition must contain:

```text
metric_id
display_name
short_definition
long_definition
direction
range
baseline_interpretation
limitations
aggregation_method
```

Minimum registry entries:

### Technical predictability

- Display name: `Detectability of laboratory signature`.
- Meaning: cross-validated ability to predict declared technical metadata from the analyzed representation.
- Preferred direction after correction: lower.
- Limitation: depends on declared metadata and prediction model.

### Biological retention

- Display name: `Retention of declared biology`.
- Meaning: cross-validated performance for predicting declared biological variables after correction, compared with baseline.
- Preferred direction: higher or unchanged.
- Limitation: does not protect undeclared or unknown biology.

### Technical removal

Define relative technical removal as:

```text
1 - corrected_technical_predictability / baseline_technical_predictability
```

Guard against a zero or near-zero baseline. Mark the metric not applicable when the denominator is below a configured tolerance.

Explain that this is relative reduction in predictability, not a literal percentage of all artifact molecules removed.

### Biological loss

Define relative biological loss as:

```text
1 - corrected_biological_predictability / baseline_biological_predictability
```

A negative value means biological predictability improved after correction. Explain that this can reflect noise removal or evaluation uncertainty and does not mean new biology was created.

### Cross-modal concordance

- Display name: `RNA-protein agreement` when the mapped modalities are RNA and protein.
- Meaning: …2775 tokens truncated…ument that the following may represent true biology and must not be treated as ordinary removable batch effects without an explicit analysis objective:

- Germline genotype.
- Somatic variant state.
- Clonal fraction.
- Tumor purity and ploidy.
- Ancestry or population structure.
- Sex-chromosome composition.
- Copy-number state.

### 14.7 Unsupported input behavior

In v0.2.0:

- FASTQ, BAM, CRAM, and VCF inputs receive an actionable validation error.
- Raw count matrices cannot use continuous residualization or ComBat.
- Binary variant-call matrices cannot be corrected.
- Fraction data require a modality that explicitly supports an appropriate transform and model.
- No method may silently coerce unsupported genomic data into continuous expression-like input.

Error example:

> `variant_calls` uses binary measurements. Covariate-aware continuous residualization is not valid for this modality. Use diagnostic-only analysis or install a future variant-aware plugin.

---

## 15. Planned v0.3.0 Targeted-NGS Plugin

This is architectural guidance, not required implementation for v0.2.0.

Recommended first genomic expansion: targeted-NGS coverage and variant-allele-fraction diagnostics.

Potential inputs:

```text
manifest.parquet
sample_qc.parquet
target_coverage.parquet
variant_counts.parquet
feature_annotations.parquet
config.yaml
```

Potential technical variables:

- Sequencing run and lane.
- Library-preparation batch.
- Capture-kit lot.
- Panel version.
- Instrument.
- Read length.
- Depth.
- Duplicate rate.
- GC bias.
- Insert size.
- FFPE damage metrics.
- Contamination.
- Pipeline version.

Appropriate future models:

- Negative-binomial or overdispersed count models for coverage/counts.
- Binomial or beta-binomial models for allele-supporting reads.
- Logistic models for binary outcomes.
- Segment-aware methods for copy-number data.
- Burden or grouped-feature methods for sparse rare variants.

Do not advertise v0.2.0 as supporting these models until they exist and pass scientific regression tests.

---

## 16. CLI Changes

Retain existing commands and add or extend:

```bash
artifactor analyze --config <config.yaml> [--resume]
artifactor report --run <run-directory> [--standalone]
artifactor inspect --run <run-directory>
artifactor inspect --run <run-directory> --section design
artifactor inspect --run <run-directory> --section factors
artifactor inspect --run <run-directory> --section corrections
artifactor inspect --run <run-directory> --section ground-truth
artifactor capabilities
artifactor capabilities --modality <kind>
artifactor validate --config <config.yaml>
```

`artifactor capabilities` must show measurement family, supported diagnostics, and correction eligibility.

`artifactor report` must rebuild solely from saved artifacts and fail clearly when a required artifact is missing or schema-incompatible.

The CLI must distinguish:

- Analysis failure.
- Correction refusal due to scientific design.
- Unsupported modality-method combination.
- Report-only omission such as absent simulator ground truth.

Scientific refusal is a successful completed analysis, not a process crash.

---

## 17. Streamlit Changes

Mirror the seven HTML report sections:

1. Decision Overview.
2. Study-Design Audit.
3. Factor Explorer.
4. Correction Comparison.
5. Ground-Truth Audit when available.
6. Root-Cause Evidence.
7. Reproducibility and Downloads.

Requirements:

- Read the same `report_model.json` and evidence artifacts used by HTML.
- Do not calculate scientific results in Streamlit callbacks.
- Provide metadata color selectors and factor selectors.
- Preserve warnings when users change views.
- Cache file reads by checksum.
- Handle missing optional sections gracefully.
- Provide direct downloads for machine-readable tables.

The standalone HTML report is the primary deliverable; Streamlit is an investigation interface over the same results.

---

## 18. Performance and Scalability

v0.2.0 adds more evidence but must not materially compromise analysis scalability.

Requirements:

- Reuse previously calculated factor scores, associations, and correction metrics.
- Never recompute analysis during report generation.
- Use columnar Parquet outputs.
- Write compact visualization datasets rather than embedding full matrices.
- Stratify visualization downsampling.
- Block feature-wise ground-truth evaluation.
- Parallelize independent bootstrap repeats only through existing safe execution controls.
- Record analysis and report runtimes separately.
- Add a configurable browser-embedding limit.

Performance targets on the default 240-sample demo:

- Report generation under 10 seconds on a typical developer machine.
- Standalone report size under 15 MiB unless `--embed-full-plotly` is explicitly selected.
- Interactive plot response under approximately one second after page load.
- No full omics matrix embedded in HTML.

Treat these as initial targets and record benchmark hardware.

---

## 19. Testing Strategy

### 19.1 Unit tests

Add tests for:

- Metric formulas and zero-baseline behavior.
- Metric registry completeness.
- Plain-language explanation lookup.
- Pairwise design-status rules.
- Factor classification rules.
- Sign-invariant factor stability.
- Ground-truth contract validation.
- Precision, recall, false-positive, and RMSE calculations.
- Evidence-card validation.
- Root-cause language restrictions.
- Modality capability resolution.
- Unsupported measurement-family rejection.
- Report-model validation.

### 19.2 Integration tests

- Run the complete `separable` analysis and build the new report.
- Run the complete `confounded` analysis and verify correction refusal.
- Rebuild the report using saved artifacts only.
- Load all Streamlit sections from a completed run.
- Generate a real-cohort-style run without ground truth and verify clean omission.
- Validate that an unsupported binary variant configuration fails before correction.
- Confirm machine-readable downloads match source artifacts.

### 19.3 Scientific regression tests

For the fixed-seed `separable` scenario:

- The expected technical variable is among the top two technical factor associations.
- A biological factor is visibly associated with the planted condition.
- Recommended correction reduces aggregate technical predictability by at least 40% relative to baseline.
- Biological predictability loss remains below 5%.
- Cross-modal concordance loss remains below 10%.
- Technical-feature precision and recall are each at least 0.75.
- Biological-feature precision and recall are each at least 0.75, or the report documents and tests a scientifically justified alternative target.
- Removing the ground-truth file does not change the recommendation.

For the fixed-seed `confounded` scenario:

- The condition-batch pair is highly confounded or non-identifiable.
- Correction is refused.
- The process exits successfully with a completed scientific-refusal status.
- The report recommends a bridging or reprocessing experiment.
- No favorable downstream metric overrides refusal.

For `cross_modal`:

- The shared biological factor appears in both modalities.
- The modality-specific artifact is correctly localized.
- Correction preserves mapped concordance within the configured guardrail.

For `plate_drift`:

- Run-order or plate-position evidence is detected.
- The report recommends layout randomization, bridge controls, or position-based follow-up.

### 19.4 Leakage tests

- Shuffle technical labels and verify technical predictability approaches the appropriate chance or null expectation.
- Shuffle biological labels and verify biological predictability approaches its null expectation.
- Assert that test-fold samples are absent from every fitted preprocessing and correction object.
- Assert that simulator truth labels never enter analysis inputs.

### 19.5 Report tests

- Validate HTML generation from a small fixture.
- Check for every required section heading.
- Check that all figures have titles and explanatory text.
- Check that refusal reports omit recommendation language implying correction.
- Check that absent ground truth produces an omission note rather than zeros.
- Check for prohibited causal phrases.
- Check color contrast, keyboard navigation, and non-color status labels.
- Check that the report opens without network access.

### 19.6 Backward compatibility

- Load a v0.1.0 run and produce either a compatible v0.2.0 report or a precise migration message.
- Keep current CLI commands working.
- Version schemas explicitly.
- Add migrations only where they are deterministic and tested.

---

## 20. Ordered Implementation Phases

### Phase 0: Baseline and gap inventory

Tasks:

1. Run all v0.1.0 tests.
2. Generate the fixed-seed separable and confounded runs.
3. Inventory saved artifacts and schemas.
4. Trace every current report value to its calculation.
5. Document existing cross-validation boundaries.
6. Identify missing outputs required by this plan.
7. Add a v0.1.0 numerical regression fixture with tolerances.

Acceptance criteria:

- Baseline behavior is documented.
- Every value in the current Biological Preservation Audit has a known source.
- Existing failures are distinguished from new work.
- The implementation map identifies reuse versus new code.

### Phase 1: Typed evidence and report contracts

Tasks:

1. Add metric registry models.
2. Add design-summary, factor-summary, evidence-card, and report-model contracts.
3. Version all schemas.
4. Add artifact checksums and omission reasons.
5. Implement serialization and validation tests.

Acceptance criteria:

- A minimal report model validates.
- Invalid evidence cards fail with actionable errors.
- Every primary metric has display language and limitations.
- Report generation cannot proceed from schema-invalid evidence.

### Phase 2: Study-Design Audit evidence

Tasks:

1. Persist pairwise support and confounding evidence.
2. Persist contingency-cell data.
3. Persist design-matrix diagnostics.
4. Implement plain-language design explanations.
5. Implement visual data builders.
6. Add separable, weak-overlap, and non-identifiable fixtures.

Acceptance criteria:

- Separable and confounded reports state exactly why correction is allowed or refused.
- All displayed counts match the manifest.
- Refusal invariants pass.

### Phase 3: Factor evidence and visualization

Tasks:

1. Standardize saved scores, loadings, explained variance, and associations.
2. Add factor classifications with stored supporting evidence.
3. Add bootstrap stability.
4. Add modality contribution for joint factors.
5. Build factor-attribution heatmaps and paired color views.
6. Add top-loading tables with feature annotations.

Acceptance criteria:

- The report visibly distinguishes condition-driven and batch-driven factors in the separable demo.
- Low-stability factors are labeled.
- Every factor label is traceable to association rows and thresholds.

### Phase 4: Correction comparison evidence

Tasks:

1. Audit and enforce evaluation boundaries.
2. Save fold-level per-variable metrics.
3. Add effect-retention tables.
4. Add explicit interval metadata.
5. Add before-and-after visualization datasets.
6. Persist method eligibility, Pareto status, and selection reasons.

Acceptance criteria:

- The report shows what changed for each biological and technical variable.
- Technical removal and biological loss are reproducible from saved raw metrics.
- A method cannot be selected without an evidence trail.
- Confounded scenarios refuse correction before method ranking.

### Phase 5: Simulator ground-truth audit

Tasks:

1. Version and validate simulator truth output.
2. Implement feature-level attribution evaluation.
3. Add recovery metrics and uncertainty where appropriate.
4. Add injected-versus-estimated plots.
5. Add ground-truth isolation and leakage tests.

Acceptance criteria:

- The seeded separable demo reports biological, technical, mixed, and null recovery.
- Ground truth never changes analysis behavior.
- Real-data runs omit the section cleanly.

### Phase 6: Root-cause evidence engine

Tasks:

1. Implement structured evidence-card generation.
2. Add calibrated language rules.
3. Add alternative-explanation rules.
4. Add structured wet-lab follow-ups.
5. Link cards to supporting artifacts.
6. Prioritize design safety above artifact findings.

Acceptance criteria:

- Every finding contains support, limitation, and follow-up.
- RIN-protein associations receive appropriately cautious interpretation.
- No observational card uses prohibited causal language.
- Confounded runs prioritize study redesign.

### Phase 7: Standalone HTML report

Tasks:

1. Implement the seven-section navigation structure.
2. Add decision banners and plain-language metric explanations.
3. Add design, factor, correction, ground-truth, and root-cause visuals.
4. Add machine-readable downloads.
5. Add responsive and accessible styling.
6. Optimize Plotly and embedded data size.
7. Verify offline operation.

Acceptance criteria:

- An unfamiliar reviewer can follow the evidence chain without reading source code.
- The report answers all eight release-outcome questions.
- The report works offline and meets the initial size target.
- No full omics matrix is embedded.

### Phase 8: Streamlit alignment

Tasks:

1. Update Streamlit to read the report model.
2. Add factor and metadata selectors.
3. Add evidence-card navigation.
4. Add artifact downloads.
5. Test missing optional sections.

Acceptance criteria:

- Streamlit and HTML display the same decisions and numbers.
- Streamlit performs no scientific recomputation.
- All pages load from a completed fixture.

### Phase 9: NGS-ready capability contract

Tasks:

1. Add measurement-family types.
2. Extend modality plugins with capabilities.
3. Add correction eligibility dispatch.
4. Add genomic provenance fields.
5. Add unsupported-input errors.
6. Add `artifactor capabilities`.
7. Document the v0.3.0 targeted-NGS path.

Acceptance criteria:

- Existing RNA and protein plugins declare capabilities explicitly.
- Unsupported count, fraction, binary, segment, and sparse-event corrections are rejected safely.
- No existing continuous modality regresses.
- Documentation accurately distinguishes current support from future support.

### Phase 10: Documentation, demonstration, and release

Tasks:

1. Update README screenshots and quick start.
2. Add `docs/interpretation_guide.md`.
3. Add `docs/metric_definitions.md`.
4. Add `docs/modality_extension_guide.md`.
5. Add `docs/ngs_roadmap.md`.
6. Write a three-to-five-minute separable demo script.
7. Write a two-minute confounded demo script.
8. Run performance benchmarks.
9. Run clean-clone local and container verification.
10. Tag v0.2.0 only after all release gates pass.

Acceptance criteria:

- A reviewer can reproduce both demos from the README.
- Documentation does not overstate NGS support.
- CI, scientific regression tests, and offline report checks pass.
- Version metadata and changelog are complete.

---

## 21. Demonstration Script Requirements

### 21.1 Separable demo narrative

The spoken demonstration must show:

1. The cohort contains RNA and protein measurements for 240 simulated samples.
2. Biological condition is balanced across processing batches.
3. A leading factor follows biological condition.
4. Another factor follows extraction batch.
5. The app compares no correction, residualization, and ComBat.
6. Residualization reduces technical predictability while retaining biology.
7. Synthetic ground truth confirms recovery of planted effects.
8. The evidence card proposes a blinded cross-batch reprocessing experiment.

### 21.2 Confounded demo narrative

The spoken demonstration must show:

1. Disease and batch are aligned.
2. PCA alone cannot determine which variable drives the separation.
3. Artifactor refuses automated correction.
4. A numerically attractive correction is still scientifically ineligible.
5. The app recommends bridge samples or balanced reprocessing.

### 21.3 Portfolio message

The demo should communicate:

> Artifactor does not merely remove batch effects. It determines whether correction is scientifically identifiable, measures what would be removed and preserved, and translates the evidence into a testable assay investigation.

---

## 22. Release Gates

All gates must pass before tagging v0.2.0.

### Scientific gates

- Separable demo detects both declared biology and the planted technical effect.
- Eligible correction meets technical-removal and biological-preservation thresholds.
- Confounded demo refuses correction.
- Simulator truth never enters fitting or selection.
- Factor classifications are evidence-backed and stable enough for their stated confidence.

### Software gates

- Unit, integration, workflow, and scientific regression tests pass.
- CLI, HTML, Streamlit, and Nextflow use the same core artifacts.
- Report generation requires no recomputation.
- Schemas are versioned and validated.
- Backward compatibility or migration behavior is tested.

### Communication gates

- Every primary metric has a plain-language explanation and limitation.
- Every finding has evidence, alternative explanations, and follow-up.
- No observational result is written as causal.
- The report clearly distinguishes simulated validation from real-data inference.
- Current and future NGS support are accurately separated.

### Reproducibility gates

- Seed, code version, configuration checksum, inputs, dependencies, and stage status are recorded.
- Missing Git commit is shown as a warning.
- The report opens offline.
- Both seeded demos reproduce within documented numerical tolerances.

---

## 23. Definition of Done

Artifactor v0.2.0 is complete when:

- The report provides an inspectable chain from study design to factors to correction evidence to recommendation.
- A nontechnical scientific reader can understand biological versus technical signal from the report itself.
- The separable demo visually shows technical removal and biological preservation.
- The confounded demo refuses unsafe correction and explains why.
- Synthetic ground-truth recovery is quantified without leaking into analysis.
- The recommendation can be recomputed from saved machine-readable evidence.
- Root-cause findings include quantitative support, alternatives, limitations, and wet-lab follow-ups.
- HTML and Streamlit agree exactly on decisions and primary numbers.
- Unsupported genomic data and methods fail safely and informatively.
- The modality interface can support future count-, fraction-, binary-, segment-, and sparse-event-aware plugins.
- Documentation presents targeted-NGS support as a v0.3.0 roadmap, not a current capability.
- All release gates pass from a clean clone.

---

## 24. Copy-Ready Initial Codex Prompt

Use this prompt to begin implementation:

> Implement Phase 0 and Phase 1 of `ARTIFACTOR_V0.2.0_CODEX_PLAN.md` in the existing Artifactor repository. First inspect the current v0.1.0 implementation and run its complete test suite. Generate the seeded separable and confounded fixtures, inventory every current analysis artifact, and trace each value in the current Biological Preservation Audit to its source calculation. Preserve current numerical behavior with tolerance-based regression tests. Then add typed, versioned contracts for the metric registry, design summary, factor summary, evidence cards, and report model. Do not redesign unrelated architecture, do not change scientific behavior without documenting a verified defect, and do not implement report presentation before the evidence contracts validate. Run focused and full tests, update the phase checklist, and report changed files, test results, baseline findings, and any blocked assumptions.

Subsequent Codex runs should implement one phase at a time, beginning each run by inspecting completed work and ending with focused tests, the full applicable test suite, and an updated phase checklist.


