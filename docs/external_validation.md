# External validation workflow

Artifactor v0.4 separates immutable retrieval, deterministic preparation, preregistration, evaluation, and presentation.

```powershell
artifactor datasets fetch seqc2_oncopanel --tier pilot
artifactor datasets verify seqc2_oncopanel --tier pilot
artifactor datasets prepare seqc2_oncopanel --tier pilot
artifactor validate-external --config configs/external/seqc2_pilot.yaml --preregistration configs/external/seqc2_preregistration.yaml
artifactor report --run results/external-seqc2_oncopanel-fe2068be53b03f54
```

Retrieval prints access terms and expected size, resumes through a `.partial` file, validates size/checksum, and atomically promotes the file. Existing mismatched files are never overwritten. Preparation requires verified inputs and reuses an existing fingerprint rather than mutating it.

Results are `pass`, `partial`, `fail`, or `not_evaluable`; evidence levels remain separate. Overall conclusions are mechanically derived. Missing public fields produce limitations or non-evaluable results, never inferred data.

The report is `report/external-validation-report.html`. Corrected matrices are emitted only when input-state and design gates allow mitigation. Both included public pilots correctly refuse correction for their declared inputs.
