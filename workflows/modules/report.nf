process BUILD_REPORT {
  cpus 1; memory '1 GB'; time '10m'; container 'artifactor:0.1.0'
  input: path run_path_file
  output: path 'reported.txt'
  script:
  """
  run_dir=\$(tail -n 1 ${run_path_file})
  artifactor report --run "\$run_dir"
  touch reported.txt
  """
}
