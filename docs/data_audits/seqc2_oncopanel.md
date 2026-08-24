# SEQC2 oncopanel public-data audit

Audit date: 2026-08-07. Registry snapshot: `figshare-collection-5842112-v2`.

The authoritative [Scientific Data record](https://www.nature.com/articles/s41597-022-01359-6) describes eight panels, multiple laboratories, four reference samples, technical-library replicates, submitted VCF callsets, reporting regions, and reference truth. The frozen processed-data collection is [Figshare collection 5842112](https://doi.org/10.6084/m9.figshare.c.5842112.v2); reporting regions are [Figshare 19128005](https://doi.org/10.6084/m9.figshare.19128005.v2).

- Submitted VCF archives, truth positives, truth negatives, and eight reporting-region BEDs are directly downloadable under CC BY 4.0. Every registry source has an exact byte count and MD5.
- The IGT pilot exposes `DP`, `RD`, and `AD` consistently at submitted positive calls. Allele-count output therefore contains source-supported IGT records only.
- Positive-only VCF absence does not establish per-site depth or callability. The adapter never converts absence into a negative call. Truth-negative rates and missed-truth-by-depth are `not_evaluable` without all-sites evidence.
- File names support reference sample, panel, laboratory, input mass, and library replicate. Platform and UMI status are not silently inferred.
- The pilot covers IGT across three laboratories. Cross-panel questions remain partial until the full processed tier is prepared.
- Sample AIS is retained but excluded from the primary A/B/C/AC5 comparison with a recorded reason.
- Raw sequencing is multiple terabytes and outside v0.4; the processed full tier is about 193 MB.

Public sources remain in ignored immutable storage; only synthetic structural fixtures belong in the repository.
