# v0.2.0 implementation map

Implementation status (2026-08-06): phases 0–10 are complete. The fixed-seed scientific suite, interface tests, offline/size checks, schema validation, lint, and type checks pass. Container execution remains dependent on a Docker runtime being available on the target machine; the image and Nextflow module tags are aligned to 0.2.0.

Baseline captured on 2026-08-06 from tag `v0.1.0`: 15 tests passed. Fixed-seed comparison runs are retained under ignored `demo/v010_baseline`; tolerance values are committed in `tests/fixtures/v010_baseline.json`.

## Existing evidence flow

| v0.1.0 value | Calculation | Saved source | v0.2.0 disposition |
|---|---|---|---|
| Design status | rank, pairwise association, overlap gate | `design/audit.json`, `design/confounding.parquet` | Extend with typed summary, cells, diagnostics, and explanations |
| Factor variance/classification | deterministic randomized PCA plus thresholded metadata associations | `diagnostics/factors.parquet`, associations, loadings | Preserve numerical values; add scores, confidence, stability, evidence columns, and canonical aliases |
| Technical predictability | cross-validated logistic/Ridge prediction, averaged over modalities and technical variables | `evaluation/method_metrics.parquet` | Add fold/per-variable long-form evidence and metric registry |
| Biological retention | cross-validated logistic/Ridge prediction, averaged over modalities and biological variables | same | Add fold/per-variable long-form evidence and effect-retention table |
| Technical removal | `1 - corrected / baseline` with `1e-12` denominator floor | same | Return not-applicable at near-zero baseline and persist reason |
| Biological loss | `1 - corrected / baseline` with `1e-12` denominator floor | same | Preserve formula; add explanation and interval metadata |
| RNA-protein concordance | median pairwise Pearson correlation for supplied feature map | same | Preserve calculation and add guardrail evidence |
| Recommendation | design gate, 5% biological-loss guardrail, material technical reduction, best removal | recommendation JSON | Persist eligibility, exclusions, frontier, and selection trail |
| Ground-truth recovery | top partial-technical-R² features versus planted technical labels | ground-truth metrics JSON | Replace with versioned four-class feature audit and injected-versus-estimated evidence |

## Current cross-validation boundary

Prediction is currently cross-validated, but feature selection/scaling and correction occur before prediction splits. v0.2.0 records this as `resampled_prediction_on_fixed_representation`, rather than falsely labeling it fully held-out correction evaluation. The correction implementations do not expose safe unseen-batch transforms, so the documented alternative resampling strategy is retained while fold-level prediction evidence is persisted.

## Artifact inventory gap

v0.1.0 already saves corrected matrices, diagnostics, aggregate metrics, findings, provenance, and HTML. Missing v0.2.0 evidence includes typed report contracts, factor scores/stability, contingency cells, long-form per-variable metrics, effect retention, method eligibility/frontier evidence, four-class simulator recovery, report manifest/checksums, visualization samples, and NGS-safe modality capabilities.
