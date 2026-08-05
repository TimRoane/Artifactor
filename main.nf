nextflow.enable.dsl=2

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
  output:
  path 'workflow-complete.txt'
  script:
  """
  artifactor analyze --config ${config_path} --resume
  artifactor validate --config ${config_path}
  touch workflow-complete.txt
  """
}

workflow {
  if (!params.config_path) error 'Provide --config_path <path>'
  def resolved_config = file(params.config_path, checkIfExists: true).toAbsolutePath().toString()
  ANALYZE(resolved_config)
}
