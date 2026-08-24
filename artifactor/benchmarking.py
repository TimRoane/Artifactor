from __future__ import annotations

import json
import platform
import statistics
import time
from pathlib import Path

import psutil

from artifactor.pipeline import analyze
from artifactor.simulation import simulate

PROFILES = {
    "small": {"family": "continuous_multiomic", "samples": 250, "rna_features": 2000, "protein_features": 500, "estimated_memory_gb": 2, "estimated_minutes": 2},
    "medium": {"family": "continuous_multiomic", "samples": 1000, "rna_features": 10000, "protein_features": 5000, "estimated_memory_gb": 8, "estimated_minutes": 15},
    "large": {"family": "continuous_multiomic", "samples": 5000, "rna_features": 25000, "protein_features": 10000, "estimated_memory_gb": 48, "estimated_minutes": 120},
    "stress": {"family": "targeted_ngs", "samples": 10000, "targets": 20000, "monitored_loci": 10000, "estimated_memory_gb": 96, "estimated_minutes": 360},
}


def benchmark_plan(profile: str) -> dict[str, object]:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}")
    return {"schema_version": "4.0", "profile": profile, "read_only": True, "paid_execution_started": False, **PROFILES[profile]}


def estimate_cost(resources: dict[str, float], rates: dict[str, float | str]) -> dict[str, object]:
    def rate(name: str) -> float:
        return float(rates.get(name, 0.0))

    compute = resources.get("cpu_hours", 0.0) * rate("cpu_hour")
    memory = resources.get("memory_gb_hours", 0.0) * rate("memory_gb_hour")
    storage = resources.get("storage_gb_months", 0.0) * rate("storage_gb_month")
    egress = resources.get("egress_gb", 0.0) * rate("egress_gb")
    request = resources.get("requests", 0.0) * rate("request_cost")
    return {"schema_version": "4.0", "estimate_not_observed_cost": True, "currency": rates.get("currency", "USD"), "compute": compute, "memory": memory, "storage": storage, "egress": egress, "requests": request, "total_estimated_cost": compute + memory + storage + egress + request}


def benchmark_run(profile: str, executor: str, output: Path, repeats: int = 3) -> Path:
    if executor != "native":
        raise ValueError(f"executor {executor!r} requires its real runtime; configuration-only claims are not benchmark runs")
    if profile not in {"small", "medium"}:
        raise ValueError("large/stress execution requires an explicitly provisioned runner; benchmark plan remains available")
    output.mkdir(parents=True, exist_ok=True)
    resources: list[dict[str, object]] = []
    scenario = "separable" if profile == "small" else "cross_modal"
    specification = PROFILES[profile]
    for repeat in range(repeats):
        case = output / f"repeat-{repeat + 1}"
        simulate(
            scenario,
            case / "input",
            20260807,
            samples=int(str(specification["samples"])),
            rna_features=int(str(specification["rna_features"])),
            protein_features=int(str(specification["protein_features"])),
        )
        started_wall, started_cpu = time.perf_counter(), time.process_time()
        run = analyze(case / "input" / "config.yaml", resume=False)
        resources.append({"schema_version": "4.0", "profile": profile, "executor": executor, "repeat": repeat + 1, "cache_state": "cold", "wall_seconds": time.perf_counter() - started_wall, "cpu_seconds": time.process_time() - started_cpu, "peak_rss_bytes": psutil.Process().memory_info().rss, "run_directory": str(run), "exit_status": 0})
    import pandas as pd
    pd.DataFrame(resources).to_parquet(output / "run_resources.parquet", index=False)
    walls = [float(str(item["wall_seconds"])) for item in resources]
    (output / "benchmark_manifest.json").write_text(json.dumps({"schema_version": "4.0", "profile": profile, "profile_specification": specification, "executor": executor, "repeats": repeats, "platform": platform.platform(), "python": platform.python_version()}, indent=2), encoding="utf-8")
    (output / "benchmark_conclusion.json").write_text(json.dumps({"schema_version": "4.0", "status": "measured", "median_wall_seconds": statistics.median(walls), "range_wall_seconds": [min(walls), max(walls)], "observed_cost": None, "observed_cost_omission_reason": "No authorized billing export supplied."}, indent=2), encoding="utf-8")
    return output


def summarize_benchmarks(runs: list[Path], output: Path) -> Path:
    import pandas as pd

    frames = [pd.read_parquet(run / "run_resources.parquet").assign(benchmark_run=str(run)) for run in runs]
    if not frames:
        raise ValueError("at least one benchmark run is required")
    combined = pd.concat(frames, ignore_index=True)
    output.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output / "run_resources.parquet", index=False)
    summary = combined.groupby(["profile", "executor"], as_index=False).agg(median_wall_seconds=("wall_seconds", "median"), min_wall_seconds=("wall_seconds", "min"), max_wall_seconds=("wall_seconds", "max"), repeats=("wall_seconds", "count"))
    summary.to_parquet(output / "run_comparison.parquet", index=False)
    (output / "benchmark_conclusion.json").write_text(json.dumps({"schema_version": "4.0", "status": "summarized", "groups": len(summary), "scientific_parity_required_before_cost_preference": True}, indent=2), encoding="utf-8")
    return output
