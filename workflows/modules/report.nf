process BUILD_REPORT {
  cpus 1; memory '1 GB'; time '10m'; container 'artifactor:0.1.0'
  input: val run_dir
  output: path 'reported.txt'
  script: """artifactor report --run '${run_dir}' && touch reported.txt"""
}
