# Three-to-five-minute demo

1. Ask whether a multi-omic cohort signal is biological, technical, mixed, or unidentifiable.
2. Open Design Audit and show balanced condition-by-batch support.
3. In Factor Explorer, identify condition-associated and batch-associated components plus modality contributions.
4. In Correction Comparison, contrast the baseline, residualization, and batch harmonization on the preservation/removal frontier.
5. Highlight the biological-loss guardrail and cross-modal concordance.
6. Open Root-Cause Report, state the limitation, and propose blinded bridge samples across implicated batches.
7. Finish at Run Provenance with checksums, versions, stage runtime, memory, and the equivalent Nextflow invocation.

## Targeted-NGS demo

1. Generate and analyze `ngs_separable`; state that raw counts and calls are unchanged.
2. Show Design and Callability, the leading coverage factor, and target-level run/lot attribution.
3. Compare the offset baseline with exploratory representations and their technical-removal, biological-loss, and replicate guardrails.
4. Show VAF beside alt count and depth, then controls and replicates.
5. Use `ngs_confounded` for refusal, `ffpe_damage` for confirmatory low-VAF context follow-up, and `bridge_controls` for planted reagent-lot localization.
