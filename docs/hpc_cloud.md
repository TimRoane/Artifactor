# HPC and cloud execution

v0.4 tracks native, Docker, Nextflow-local, Slurm/Apptainer, and AWS Batch separately. A checked configuration is not a completed execution. Conditional executors must say `configuration validated only` when unavailable. No dataset, benchmark, or report command starts paid execution implicitly.

External validation can be launched with `nextflow run main.nf -profile local --external_config <config> --preregistration <snapshot>`. This command is documented but remains unvalidated on machines without Nextflow. Executor claim state is machine-readable in `configs/executor_validation.yaml`.

Local execution uses `nextflow run main.nf -profile local --config_path <absolute-config> -resume`. The Docker profile runs the pinned Artifactor release image. The Slurm profile enables Apptainer-compatible Singularity execution; adapt queue and cluster directives in a site-specific config.

The AWS Batch profile is intentionally inert until `ARTIFACTOR_AWS_QUEUE`, `ARTIFACTOR_S3_WORKDIR`, credentials, region, and a published container are supplied. It creates no resources. Keep input data outside images, use immutable object versions, encrypt storage, and apply least-privilege IAM. Real cloud cost collection is future work; stage runtime and observed memory are recorded now.
