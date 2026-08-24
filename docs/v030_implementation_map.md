# v0.3.0 implementation map

Implementation status (2026-08-07): targeted-NGS phases 0–10 are implemented. Analysis-ready count and allele tables pass typed schema, reference/panel, consistency, provenance, and capability gates before analysis. The existing continuous RNA/protein path remains independently dispatched.

The coverage tournament evaluates declared fixed exploratory representations using grouped resampled predictors, which is the documented alternative permitted when safe unseen technical-level transforms are unavailable. Scaling and PCA prediction preprocessing are deterministic; replicate subjects are never split between folds. Simulator truth is loaded only after modeling and representation selection.

Safety is structural: NGS capabilities permit no continuous correction; source checksums are verified after analysis; output representations live under `ngs/representations/`; VAF is always reconstructed from retained alt count and total depth; call state is copied only as immutable evidence. Panel structural absence and observed numeric zero remain distinct.

The fixed-seed release audit covers `ngs_separable`, `ngs_confounded`, `ffpe_damage`, and `bridge_controls`. Default dimensions are 384 samples, 800 targets, and 200 loci. Docker and Nextflow definitions are version-aligned to 0.3.0; runtime container verification requires those runtimes on the target host.
