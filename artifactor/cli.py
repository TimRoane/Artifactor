from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer
from pydantic import ValidationError

from artifactor import __version__
from artifactor.config import load_config
from artifactor.io import validate_inputs, write_json
from artifactor.pipeline import analyze as run_analysis
from artifactor.reporting import build_report
from artifactor.simulation import SCENARIOS
from artifactor.simulation import simulate as generate

app = typer.Typer(
    help="Assay-aware technical artifact analysis for multi-omics cohorts.", no_args_is_help=True
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    pass


@app.command()
def simulate(
    scenario: str = typer.Option(..., help=f"One of: {', '.join(SCENARIOS)}"),
    output: Path = typer.Option(...),
    seed: int = typer.Option(20260805),
) -> None:
    """Create a deterministic two-modality synthetic cohort."""
    try:
        generate(scenario, output, seed)
    except (OSError, ValueError) as exc:
        typer.echo(f"Simulation failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(f"Created {scenario} simulation in {output}")


@app.command()
def validate(config: Path = typer.Option(..., exists=True, dir_okay=False)) -> None:
    """Validate configuration, data contracts, and sample alignment."""
    try:
        loaded = load_config(config)
        result, _, _ = validate_inputs(loaded)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(f"Validation failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    output = loaded.project.output_dir / "validation.json"
    write_json(result.model_dump(), output)
    typer.echo(json.dumps(result.model_dump(), indent=2))
    if not result.valid:
        raise typer.Exit(2)


@app.command()
def analyze(
    config: Path = typer.Option(..., exists=True, dir_okay=False),
    resume: bool = typer.Option(False, "--resume"),
) -> None:
    """Run the complete Python-native analysis workflow."""
    try:
        destination = run_analysis(config, resume)
    except Exception as exc:
        typer.echo(f"Analysis failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(str(destination))


@app.command()
def report(run: Path = typer.Option(..., exists=True, file_okay=False)) -> None:
    """Rebuild the standalone report exclusively from persisted artifacts."""
    try:
        destination = build_report(run)
    except (OSError, ValueError, KeyError) as exc:
        typer.echo(f"Report build failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(str(destination))


@app.command("inspect")
def inspect_run(run: Path = typer.Option(..., exists=True, file_okay=False)) -> None:
    """Print a concise completed-run summary for humans and CI."""
    try:
        payload = json.loads((run / "run.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        typer.echo(f"Inspection failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(
        f"run={payload['run_fingerprint']} status={payload['status']} samples={payload['sample_count']} design={payload['design_status']} recommendation={payload['recommendation']['method']}"
    )
    for warning in payload.get("warnings", []):
        typer.echo(f"warning: {warning}")


@app.command()
def serve(
    run: Path = typer.Option(..., exists=True, file_okay=False), port: int = typer.Option(8501)
) -> None:
    """Launch the read-only Streamlit application for a completed run."""
    if not (run / "run.json").exists():
        typer.echo("Serve failed: run.json is missing; analyze the cohort first.", err=True)
        raise typer.Exit(2)
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(Path(__file__).parent.parent / "app/Home.py"),
        "--server.port",
        str(port),
        "--",
        "--run",
        str(run.resolve()),
    ]
    try:
        raise typer.Exit(subprocess.call(command))
    except FileNotFoundError as exc:
        typer.echo(
            "Streamlit is unavailable. Install with: pip install 'artifactor-omics[ui]'", err=True
        )
        raise typer.Exit(2) from exc


if __name__ == "__main__":
    app()
