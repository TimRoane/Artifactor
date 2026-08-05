# HPC and cloud execution

Local execution uses `nextflow run main.nf -profile local --config_path <absolute-config> -resume`. The Docker profile runs the pinned Artifactor release image. The Slurm profile enables Apptainer-compatible Singularity execution; adapt queue and cluster directives in a site-specific config.

The AWS Batch profile is intentionally inert until `ARTIFACTOR_AWS_QUEUE`, `ARTIFACTOR_S3_WORKDIR`, credentials, region, and a published container are supplied. It creates no resources. Keep input data outside images, use immutable object versions, encrypt storage, and apply least-privilege IAM. Real cloud cost collection is future work; stage runtime and observed memory are recorded now.
