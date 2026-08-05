nextflow.enable.dsl=2

include { VALIDATE_INPUTS } from './workflows/modules/validate'
include { BUILD_REPORT } from './workflows/modules/report'

params.config_path = null
params.outdir = 'nextflow-results'

process ANALYZE {
  tag "${params.config_path}"
  cpus 2
  memory '4 GB'
  time '30m'
  container 'artifactor:0.1.0'
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
  if (!params.config_path) error 'Provide --config_path <path>'
  def resolved_config = file(params.config_path, checkIfExists: true).toAbsolutePath().toString()
  validation = VALIDATE_INPUTS(resolved_config)
  run_path = ANALYZE(resolved_config, validation)
  BUILD_REPORT(run_path)
}
