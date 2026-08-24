# Targeted-NGS investigation

Artifactor v0.3.0 accepts analysis-ready coverage and variant allele-count tables. It does not ingest reads or VCFs, call variants, change a count or VAF, or remove a call. Its purpose is to separate technical, biological, mixed, and non-identifiable evidence while keeping detection opportunity visible.

Run `artifactor simulate --scenario ngs_separable --output demo/ngs`, then `artifactor analyze --config demo/ngs/config.yaml`. The analyze command prints the exact run directory. Its `report/artifactor-report.html` is standalone; `artifactor serve --run <run>` opens the matching read-only UI. Other scenarios are `ngs_confounded`, `ffpe_damage`, and `bridge_controls`.

The `ngs/` directory contains validation, common-target, callability, sample-QC, coverage-model, factor, GC, representation-frontier, variant-model, context, bias, read-support, control, and replicate tables. `ngs/representations/` contains derived exploratory coverage views, not corrected source data. Ground-truth files are loaded only after fitting and selection.

Interpret results in this order: confirm reference/panel compatibility and common callability; inspect the design gate; review count-aware factors and target attribution; consider only eligible exploratory coverage representations; review VAF with alt count and depth; then read evidence-card alternatives, limitations, and proposed wet-lab follow-up. Low depth is insufficient information, structural panel absence is not zero, and an FFPE-like association is a hypothesis rather than proof of damage.
