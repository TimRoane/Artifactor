# v0.4.0 implementation map

The release adds frozen public-data registry/retrieval, SEQC2 and CPTAC adapters, preparation manifests and ledgers, preregistered typed evidence, external reports/UI, cross-run parity, and benchmark/cost contracts.

- The v0.3 fixed-seed suite was frozen first; all 33 baseline tests passed.
- Both public source sets were retrieved and checksum-verified, including the full 193 MB SEQC2 processed tier. Prepared fingerprints are `fe2068be53b03f54` (SEQC2 pilot), `4c0d193699592f70` (SEQC2 full), and `3a2ae957d303d500` (CPTAC).
- Native pilot validation is real. Docker, Nextflow, Slurm/Apptainer, and AWS Batch remain configuration-only where runtimes or credentials are unavailable; no execution claim is made.
- PDC000127 replaces the draft plan's erroneous PDC000128 primary-proteome accession through a pre-results deviation record.
- Full-tier sources remain opt-in; no large or paid work starts implicitly.

Machine-readable evidence lives below `external_validation/`; reports rebuild exclusively from those artifacts. Benchmark outputs distinguish measurements, rate-card estimates, and absent observed billing data.
