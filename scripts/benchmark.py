"""Compare deterministic quick and standard runs on a compact synthetic cohort."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import yaml

from artifactor.pipeline import analyze
from artifactor.simulation import simulate


def main() -> None:
    root = Path("benchmark")
    simulate(
        "separable",
        root / "quick",
        seed=20260805,
        samples=80,
        rna_features=500,
        protein_features=150,
    )
    results = []
    for budget in ("quick", "standard"):
        cohort = root / budget
        if budget == "standard":
            shutil.copytree(root / "quick", cohort, dirs_exist_ok=True)
        path = cohort / "config.yaml"
        config = yaml.safe_load(path.read_text())
        config["project"]["name"] = f"benchmark-{budget}"
        config["analysis"]["analysis_budget"] = budget
        if budget == "standard":
            config["analysis"].update({"permutations": 199, "bootstrap_iterations": 50})
        path.write_text(yaml.safe_dump(config, sort_keys=False))
        started = time.perf_counter()
        run = analyze(path)
        telemetry = json.loads((run / "telemetry/resources.json").read_text())
        results.append(
            {"budget": budget, "wall_seconds": time.perf_counter() - started, **telemetry}
        )
    (root / "results.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
