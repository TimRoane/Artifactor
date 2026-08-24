from typer.testing import CliRunner

from artifactor.cli import app

runner = CliRunner()


def test_capabilities_and_version_commands() -> None:
    version = runner.invoke(app, ["--version"])
    assert version.exit_code == 0
    assert version.stdout.strip() == "0.5.0"
    capability = runner.invoke(app, ["capabilities", "--modality", "variant_binary"])
    assert capability.exit_code == 0
    assert '"measurement_family": "binary"' in capability.stdout
    assert '"supported_corrections": [' in capability.stdout


def test_unknown_capability_is_a_usage_failure() -> None:
    result = runner.invoke(app, ["capabilities", "--modality", "fastq"])
    assert result.exit_code == 2
    assert "unknown modality kind" in result.stderr
