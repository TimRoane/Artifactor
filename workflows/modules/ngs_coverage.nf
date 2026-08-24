process NGS_COVERAGE {
  cpus 1; memory '1 GB'; time '10m'; container 'artifactor:0.3.0'
  input:
  path run_path_file
  path qc_marker
  output: path 'ngs_coverage_checked.txt'
  script:
  """
  run_dir=\$(tail -n 1 ${run_path_file})
  artifactor inspect --run "\$run_dir" --section coverage > ngs_coverage_checked.txt
  """
}
