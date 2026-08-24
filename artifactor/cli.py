from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import typer
from pydantic import ValidationError

from artifactor import __version__
from artifactor.config import load_config
from artifactor.datasets import (
    dataset_entry,
    dataset_status,
    expected_size,
    fetch_dataset,
    load_registry,
    prepare_dataset,
    verify_dataset,
)
from artifactor.datasets.operations import Tier, default_data_root
from artifactor.external import validate_external as run_external_validation
from artifactor.io import validate_inputs, write_json
from artifactor.modalities import capability_rows
from artifactor.onboarding import ModalityKind, initialize_project, preflight_project
from artifactor.pipeline import analyze as run_analysis
from artifactor.reporting import build_benchmark_report, build_external_report, build_report
from artifactor.simulation import SCENARIOS
from artifactor.simulation import simulate as generate

app = typer.Typer(
    help="Assay-aware technical artifact analysis for multi-omics cohorts.", no_args_is_help=True
)
datasets_app = typer.Typer(help="Manage frozen public dataset sources and prepared adapters.")
benchmark_app = typer.Typer(help="Plan and measure reproducible resource benchmarks.")
app.add_typer(datasets_app, name="datasets")
app.add_typer(benchmark_app, name="benchmark")


def _echo_json(value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    typer.echo(json.dumps(value, indent=2, default=str))


def _dataset_tier(value: str) -> Tier:
    if value not in {"fixture", "pilot", "full"}:
        raise ValueError("tier must be fixture, pilot, or full")
    return cast(Tier, value)


@datasets_app.command("list")
def datasets_list() -> None:
    """List frozen dataset registry entries."""
    _echo_json([{"dataset_id": item.dataset_id, "display_name": item.display_name, "access_level": item.access_level, "snapshot": item.release_or_snapshot} for item in load_registry().datasets])


@datasets_app.command("describe")
def datasets_describe(dataset_id: str) -> None:
    """Describe one registry entry and its frozen source files."""
    try:
        _echo_json(dataset_entry(dataset_id))
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc


@datasets_app.command("fetch")
def datasets_fetch(dataset_id: str, tier: str = typer.Option("pilot"), data_root: Path = typer.Option(default_data_root()), confirm_large: bool = typer.Option(False, "--confirm-large")) -> None:
    """Download sources with resume, checksum verification, and no overwrite."""
    try:
        entry = dataset_entry(dataset_id)
        parsed_tier = _dataset_tier(tier)
        typer.echo(f"expected_size_bytes={expected_size(dataset_id, parsed_tier)} access_terms={entry.license_or_terms}")
        _echo_json(fetch_dataset(dataset_id, parsed_tier, data_root, confirm_large))
    except (KeyError, OSError, PermissionError, ValueError) as exc:
        typer.echo(f"Dataset fetch failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@datasets_app.command("verify")
def datasets_verify(dataset_id: str, tier: str = typer.Option("pilot"), data_root: Path = typer.Option(default_data_root())) -> None:
    """Read and checksum sources without modifying them."""
    try:
        status = verify_dataset(dataset_id, _dataset_tier(tier), data_root)
        _echo_json(status)
        if not status.verified:
            raise typer.Exit(2)
    except (KeyError, OSError, ValueError) as exc:
        typer.echo(f"Dataset verification failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@datasets_app.command("prepare")
def datasets_prepare(dataset_id: str, tier: str = typer.Option("pilot"), data_root: Path = typer.Option(default_data_root())) -> None:
    """Create fingerprinted prepared data from verified immutable sources."""
    try:
        destination = prepare_dataset(dataset_id, _dataset_tier(tier), data_root)
        _echo_json({"schema_version": "4.0", "status": "prepared", "path": str(destination)})
    except (KeyError, OSError, ValueError) as exc:
        typer.echo(f"Dataset preparation failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@datasets_app.command("status")
def datasets_status(dataset_id: str, tier: str = typer.Option("pilot"), data_root: Path = typer.Option(default_data_root())) -> None:
    """Report source verification and prepared snapshots."""
    try:
        _echo_json(dataset_status(dataset_id, _dataset_tier(tier), data_root))
    except (KeyError, OSError, ValueError) as exc:
        typer.echo(f"Dataset status failed: {exc}", err=True)
        raise typer.Exit(2) from exc


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
    """Create a deterministic continuous multi-omics or targeted-NGS cohort."""
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
        if any(item.kind.startswith("targeted_ngs_") for item in loaded.modalities):
            from artifactor.ngs import validate_ngs_inputs

            result, _ = validate_ngs_inputs(loaded)
        else:
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
def report(
    run: Path = typer.Option(..., exists=True, file_okay=False),
    standalone: bool = typer.Option(True, "--standalone/--linked"),
) -> None:
    """Rebuild the standalone report exclusively from persisted artifacts."""
    try:
        if (run / "external_validation").exists():
            destination = build_external_report(run)
        elif (run / "run_resources.parquet").exists() or (run / "benchmarks/run_resources.parquet").exists():
            destination = build_benchmark_report(run)
        else:
            destination = build_report(run, standalone=standalone)
    except (OSError, ValueError, KeyError) as exc:
        typer.echo(f"Report build failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(str(destination))


@app.command("inspect")
def inspect_run(
    run: Path = typer.Option(..., exists=True, file_okay=False),
    section: str | None = typer.Option(
        None, help="Optional section: design, factors, corrections, ground-truth, ngs-qc, coverage, variants, or ngs-ground-truth."
    ),
) -> None:
    """Print a concise completed-run summary for humans and CI."""
    try:
        payload = json.loads((run / "run.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        typer.echo(f"Inspection failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    section_paths = {
        "design": "design/design_summary.json",
        "factors": "factors/factor_summary.parquet",
        "corrections": "corrections/method_eligibility.parquet",
        "ground-truth": "ground_truth/recovery_summary.json",
        "ngs-qc": "ngs/sample_qc_summary.parquet",
        "coverage": "ngs/coverage_representation_metrics.parquet",
        "variants": "ngs/variant_model_results.parquet",
        "ngs-ground-truth": "ground_truth/ngs_coverage_recovery.json",
    }
    if section:
        if section not in section_paths:
            typer.echo(f"Inspection failed: unknown section {section!r}", err=True)
            raise typer.Exit(2)
        path = run / section_paths[section]
        if not path.exists():
            typer.echo(f"section={section} status=omitted reason=artifact_not_present")
            return
        if path.suffix == ".parquet":
            import pandas as pd

            typer.echo(pd.read_parquet(path).to_string(index=False))
        else:
            typer.echo(json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2))
        return
    typer.echo(
        f"run={payload['run_fingerprint']} status={payload['status']} samples={payload['sample_count']} design={payload['design_status']} recommendation={payload['recommendation']['method']}"
    )
    for warning in payload.get("warnings", []):
        typer.echo(f"warning: {warning}")


@app.command()
def capabilities(
    modality: str | None = typer.Option(None, help="Show one modality kind."),
) -> None:
    """List accepted measurement families, transforms, diagnostics, and corrections."""
    try:
        rows = capability_rows(modality)
    except ValueError as exc:
        typer.echo(f"Capabilities failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(rows, indent=2))


@app.command("init")
def initialize_command(
    inputs: list[Path] = typer.Option(
        ..., "--input", exists=True, dir_okay=False, help="Measurement matrix; repeat for multiple modalities."
    ),
    metadata: Path = typer.Option(..., exists=True, dir_okay=False),
    project: Path = typer.Option(..., help="New project directory."),
    name: str = typer.Option("My Artifactor Study"),
    sample_id: str | None = typer.Option(None, help="Metadata sample-ID column; inferred when omitted."),
    biological: list[str] | None = typer.Option(None, "--biological"),
    technical: list[str] | None = typer.Option(None, "--technical"),
    protected: list[str] | None = typer.Option(None, "--protected"),
    identifier: list[str] | None = typer.Option(None, "--identifier"),
    kinds: list[str] | None = typer.Option(
        None, "--kind", help="Modality kind in --input order; repeat when needed."
    ),
    budget: str = typer.Option("quick", help="quick, standard, or full"),
) -> None:
    """Create a ready-to-review project from metadata and one or more matrices."""
    if budget not in {"quick", "standard", "full"}:
        typer.echo("Project initialization failed: budget must be quick, standard, or full", err=True)
        raise typer.Exit(2)
    valid_kinds = {
        "generic_continuous", "rna_continuous", "proteomics_continuous", "genomic_continuous"
    }
    if kinds and (len(kinds) != len(inputs) or not set(kinds) <= valid_kinds):
        typer.echo(
            "Project initialization failed: repeat --kind once per --input using a supported continuous kind",
            err=True,
        )
        raise typer.Exit(2)
    try:
        config = initialize_project(
            project,
            name,
            metadata,
            inputs,
            sample_id_column=sample_id,
            biological=biological,
            technical=technical,
            protected=protected,
            identifier=identifier,
            kinds=dict(
                zip(
                    (path.name for path in inputs),
                    cast(list[ModalityKind], kinds),
                    strict=True,
                )
            )
            if kinds
            else None,
            budget=cast(Any, budget),
        )
        preflight = json.loads((project / "preflight.json").read_text(encoding="utf-8"))
        _echo_json(
            {
                "schema_version": "4.1",
                "status": "project_created",
                "config": str(config),
                "preflight": preflight,
                "next_command": f"artifactor analyze --config {config}",
            }
        )
    except (OSError, ValueError) as exc:
        typer.echo(f"Project initialization failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("preflight")
def preflight_command(config: Path = typer.Option(..., exists=True, dir_okay=False)) -> None:
    """Validate inputs and show the correction design gate before a full analysis."""
    try:
        result = preflight_project(config)
        _echo_json(result)
        if not result["valid"]:
            raise typer.Exit(2)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(f"Preflight failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("outputs")
def outputs_command(run: Path = typer.Option(..., exists=True, file_okay=False)) -> None:
    """Show exactly where the report and any corrected datasets were written."""
    export_path = run / "exports/corrected_data.json"
    if not export_path.exists():
        _echo_json(
            {
                "schema_version": "4.1",
                "status": "not_available",
                "reason": "This run predates corrected-data export metadata or is not a continuous-matrix run.",
                "report": str(run / "report/artifactor-report.html"),
            }
        )
        return
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    payload["report"] = str(run / "report/artifactor-report.html")
    payload["files"] = [str(run / item) for item in payload.get("files", [])]
    _echo_json(payload)


@app.command("start")
def start(
    port: int = typer.Option(8501),
    project_root: Path = typer.Option(Path("projects")),
) -> None:
    """Open the guided Analyze / Demo / Completed-run home screen."""
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(Path(__file__).parent.parent / "app/Home.py"),
        "--server.port",
        str(port),
        "--",
        "--project-root",
        str(project_root.resolve()),
    ]
    try:
        raise typer.Exit(subprocess.call(command))
    except FileNotFoundError as exc:
        typer.echo(
            "Streamlit is unavailable. Install with: pip install 'artifactor-omics[ui]'",
            err=True,
        )
        raise typer.Exit(2) from exc


@app.command("validate-external")
def validate_external_command(
    config: Path = typer.Option(..., exists=True, dir_okay=False),
    preregistration: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path | None = typer.Option(None),
) -> None:
    """Verify a frozen public-data method snapshot and evaluate its questions."""
    try:
        destination = run_external_validation(config, preregistration, output)
        _echo_json({"schema_version": "4.0", "status": "complete", "run": str(destination)})
    except (KeyError, OSError, ValidationError, ValueError) as exc:
        typer.echo(f"External validation failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command("compare-runs")
def compare_runs_command(
    run_a: Path = typer.Argument(..., exists=True, file_okay=False),
    run_b: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Path | None = typer.Option(None),
    rtol: float = typer.Option(1e-6),
    atol: float = typer.Option(1e-8),
) -> None:
    """Compare two runs using exact, numeric, decision, and environment parity classes."""
    from artifactor.reproducibility import compare_runs

    try:
        comparison = compare_runs(run_a, run_b, rtol, atol)
        if output:
            write_json(comparison.model_dump(mode="json"), output)
        _echo_json(comparison)
        if comparison.overall_status in {"not_equivalent", "not_comparable"}:
            raise typer.Exit(2)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        typer.echo(f"Run comparison failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@benchmark_app.command("plan")
def benchmark_plan_command(profile: str = typer.Option(...)) -> None:
    """Print a read-only resource plan; this never starts paid work."""
    from artifactor.benchmarking import benchmark_plan

    try:
        _echo_json(benchmark_plan(profile))
    except ValueError as exc:
        typer.echo(f"Benchmark plan failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@benchmark_app.command("run")
def benchmark_run_command(
    profile: str = typer.Option(...),
    executor: str = typer.Option("native"),
    output: Path = typer.Option(...),
    repeats: int = typer.Option(3, min=1),
) -> None:
    """Measure a real native benchmark; unavailable executors are never simulated."""
    from artifactor.benchmarking import benchmark_run

    try:
        _echo_json({"schema_version": "4.0", "status": "complete", "output": str(benchmark_run(profile, executor, output, repeats))})
    except (OSError, ValueError) as exc:
        typer.echo(f"Benchmark run failed: {exc}", err=True)
        raise typer.Exit(2) from exc


@benchmark_app.command("summarize")
def benchmark_summarize_command(
    runs: list[Path] = typer.Option(..., "--runs", exists=True, file_okay=False),
    output: Path = typer.Option(...),
) -> None:
    """Summarize measured benchmark directories without inventing billing data."""
    from artifactor.benchmarking import summarize_benchmarks

    try:
        _echo_json({"schema_version": "4.0", "status": "complete", "output": str(summarize_benchmarks(runs, output))})
    except (OSError, ValueError) as exc:
        typer.echo(f"Benchmark summary failed: {exc}", err=True)
        raise typer.Exit(2) from exc


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
