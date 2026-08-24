nextflow.enable.dsl=2

include { VALIDATE_INPUTS } from './workflows/modules/validate'
include { NGS_QC } from './workflows/modules/ngs_qc'
include { NGS_COVERAGE } from './workflows/modules/ngs_coverage'
include { NGS_VARIANTS } from './workflows/modules/ngs_variants'
include { NGS_EVALUATE } from './workflows/modules/ngs_evaluate'
include { BUILD_REPORT } from './workflows/modules/report'

params.config_path = null
params.external_config = null
params.preregistration = null
params.outdir = 'nextflow-results'

process EXTERNAL_VALIDATE {
  tag "${params.external_config}"
  cpus 2
  memory '4 GB'
  time '30m'
  container 'artifactor:0.5.0'
  publishDir params.outdir, mode: 'copy', overwrite: true
  input:
  path external_config
  path preregistration
  output:
  path 'external_run_path.txt'
  script:
  """
  artifactor validate-external --config '${external_config}' --preregistration '${preregistration}' > external_run_path.txt
  """
}

process ANALYZE {
  tag "${params.config_path}"
  cpus 2
  memory '4 GB'
  time '30m'
  container 'artifactor:0.5.0'
  publishDir params.outdir, mode: 'copy', overwrite: true
  input:
  val config_path
  path validation_marker
  output:
  path 'run_path.txt'
  script:
  """
  artifactor analyze --config '${config_path}' --resume > run_path.txt
  """
}

workflow {
  if (params.external_config || params.preregistration) {
    if (!params.external_config || !params.preregistration) error 'Provide both --external_config and --preregistration'
    external_config = file(params.external_config, checkIfExists: true)
    preregistration = file(params.preregistration, checkIfExists: true)
    EXTERNAL_VALIDATE(external_config, preregistration)
  } else {
    if (!params.config_path) error 'Provide --config_path <path>'
    def resolved_config = file(params.config_path, checkIfExists: true).toAbsolutePath().toString()
    validation = VALIDATE_INPUTS(resolved_config)
    run_path = ANALYZE(resolved_config, validation)
    qc = NGS_QC(run_path)
    coverage = NGS_COVERAGE(run_path, qc)
    variants = NGS_VARIANTS(run_path, coverage)
    evaluated = NGS_EVALUATE(run_path, variants)
    BUILD_REPORT(run_path, evaluated)
  }
}
