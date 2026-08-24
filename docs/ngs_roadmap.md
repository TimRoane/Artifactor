# Targeted-NGS roadmap

Artifactor v0.2.0 does not process reads, alignments, or variant-call files. FASTQ, BAM, CRAM, VCF, and BCF inputs are rejected with a remediation message. The only current genomic path is an analysis-ready `genomic_continuous` summary matrix satisfying the existing continuous-data contract; reports label it as a generic continuous genomic summary and make no variant-level support claim.

The planned v0.3.0 targeted-NGS plugin will introduce family-aware contracts for binary variants, copy-number segments, allele fractions, and sparse events. It is expected to preserve caller/build/panel provenance, missing-versus-reference semantics, callability, depth and quality fields, sample identity checks, and assay-specific diagnostic and correction rules. These are roadmap intentions, not shipped capabilities.

Potential biological variables such as ancestry, clonality, tumor purity, copy number, allele-specific imbalance, and true somatic structure must be declared and protected according to the scientific objective; they are not ordinary removable batch effects.
