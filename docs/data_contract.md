# Data contract

The manifest contains one unique `sample_id` per row. YAML explicitly assigns variables to biological, technical, protected, identifier, or ignored roles. Each modality is a numeric sample-by-feature Parquet, CSV, or TSV table, or a declared feature-by-sample table that is transposed once. Values may be missing but never infinite; feature names and sample IDs are unique. At least three shared samples and two modalities are required. Unknown YAML keys are rejected.

Raw RNA counts require an explicit transform. No correction silently imputes data: decomposition uses median fill and all corrected outputs restore the input missingness pattern. Output Parquet tables carry `schema_version`.

Targeted-NGS uses two long-form modalities. Coverage requires `sample_id`, `target_id`, and nonnegative integer `raw_count`; target annotations declare coordinates, length, GC, panel version, reference build, and structural membership. Allele counts require `sample_id`, `variant_id`, `alt_count`, and depth (or consistent reference count), with optional strand, orientation, quality, read-position, insert-size, and immutable upstream call state. Numeric zero means an observed zero; panel structural absence is represented in annotations and never coerced to zero.
