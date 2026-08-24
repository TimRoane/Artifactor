# Metric definitions

Artifactor stores the complete machine-readable registry in `report/report_model.json`. The same definitions appear in HTML and Streamlit.

| Metric | Direction | Interpretation | Important limitation |
|---|---:|---|---|
| Technical predictability | Lower | Cross-validated detectability of declared laboratory metadata. | Low predictability does not prove every artifact is absent. |
| Biological retention | Higher | Cross-validated detectability of declared biological variables. | Undeclared biology is not protected by this metric. |
| Technical removal | Higher | Relative reduction in technical predictability from the uncorrected baseline. | It is not the physical percentage of artifact molecules removed. |
| Biological loss | Lower | Relative decrease in declared-biological predictability from baseline. | Small changes may be within resampling uncertainty. |
| Cross-modal concordance | Preserve | Median correlation among supplied mapped feature pairs. | It evaluates only supplied mappings. |

Relative metrics are reported as not applicable when their baseline magnitude is below `1e-8`; Artifactor never replaces a zero baseline with a misleading percentage. Fold-level rows state the evaluation strategy, training/test sizes, variable, modality, and fold. Because v0.2.0 correction implementations operate on a fixed corrected representation, the report labels their evaluation as resampled prediction on that representation; prediction preprocessing is learned within each fold.

Selection first requires an identifiable design. Candidate methods must then achieve at least 5% technical improvement, lose no more than 5% declared-biological predictability, and remain within the configured cross-modal concordance guardrail. The selected method must be on the non-dominated preservation/removal frontier.
