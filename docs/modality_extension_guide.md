# Modality extension guide

Every modality kind declares a `MeasurementFamily` and an explicit capability record: accepted matrix formats, transformations, diagnostics, corrections, missingness semantics, protected-variable semantics, and upstream provenance requirements. Inspect the registry with:

```bash
uv run artifactor capabilities
uv run artifactor capabilities --modality genomic_continuous
```

To extend Artifactor, add a capability in `artifactor/modalities/capabilities.py`, validate the analysis-ready matrix contract, and implement family-appropriate diagnostics and correction dispatch. Tests must demonstrate rejection of incompatible corrections and verify that protected variables are never removed implicitly.

The continuous correction methods are valid only for continuous measurements. In v0.2.0, count, fraction, binary, segment, and sparse-event inputs declare their semantics but permit only `none`. A plugin should not relabel a non-continuous matrix as continuous merely to reach an existing correction.
