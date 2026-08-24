process NGS_QC {
  cpus 1; memory '1 GB'; time '10m'; container 'artifactor:0.3.0'
  input: path run_path_file
  output: path 'ngs_qc_checked.txt'
  script:
  """
  run_dir=\$(tail -n 1 ${run_path_file})
  artifactor inspect --run "\$run_dir" --section ngs-qc > ngs_qc_checked.txt
  """
}
