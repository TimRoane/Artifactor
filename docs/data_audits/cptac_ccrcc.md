# CPTAC CCRCC public-data audit

Audit date: 2026-08-07. Frozen study: `PDC000127-v1-publication-supplements`.

The official [PDC API](https://proteomic.datacommons.cancer.gov/pdc/publicapi-documentation/) identifies PDC000127 as the CPTAC CCRCC Discovery Proteome. The draft v0.4 plan named PDC000128, which is the phosphoproteome; the adapter corrects this before results and records `DEV-CPTAC-001`. The [Cell study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7331093/) supplies the scientific context.

- Proteome TMT archive: 15,052,030 bytes, MD5 `0fa5f5b83969d0b12a177c912a206a77`.
- Transcriptome RPKM archive: 26,807,229 bytes, MD5 `e3125e51cf2fb6553cd0d486a95d6a63`.
- Release-4 clinical and release-2 TMT mapping workbooks are checksum-frozen.
- The TMT map exposes participant, specimen/aliquot, plex, channel, center, instrument, and operator. RNA data expose subject, tissue, and modality sample ID. Identities are retained without implicit replicate collapse.
- The source protein matrix and publication document upstream ComBat adjustment and imputation. Artifactor labels that state and refuses a new correction. The RNA supplement lacks sufficient per-sample technical covariates, making diagnostic-only/partial validation appropriate.
- No external identifier service is queried during preparation. A primary one-to-one cross-modal analysis is `not_evaluable` until a versioned mapping is frozen.
