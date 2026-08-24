process VALIDATE_INPUTS {
  cpus 1; memory '2 GB'; time '10m'; container 'artifactor:0.3.0'
  input: val config_path
  output: path 'validated.txt'
  script: """artifactor validate --config '${config_path}' && touch validated.txt"""
}
