from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

SCENARIOS = ("separable", "confounded", "cross_modal", "plate_drift")


def _matrix(
    rng: np.random.Generator,
    shared: np.ndarray,
    batch: np.ndarray,
    rin: np.ndarray,
    features: int,
    modality: str,
    scenario: str,
) -> tuple[np.ndarray, list[dict[str, object]]]:
    values = rng.normal(0, 1, (len(shared), features))
    truth: list[dict[str, object]] = []
    bio_count = min(max(5, int(features * 0.4)), features // 2)
    tech_count = min(max(5, features // 10), features - bio_count)
    values[:, :bio_count] += shared[:, None] * rng.uniform(1.2, 2.0, bio_count)
    for index in range(bio_count):
        truth.append(
            {
                "modality": modality,
                "feature": f"F{index:04d}",
                "signal": "biological_condition",
                "affected": True,
            }
        )
    tech_effect = batch if scenario != "plate_drift" else np.linspace(-1, 1, len(batch))
    if scenario != "cross_modal" or modality == "rna":
        values[:, bio_count : bio_count + tech_count] += tech_effect[:, None] * rng.uniform(
            1.5, 2.5, tech_count
        )
        for index in range(bio_count, bio_count + tech_count):
            truth.append(
                {
                    "modality": modality,
                    "feature": f"F{index:04d}",
                    "signal": "processing_artifact",
                    "affected": True,
                }
            )
    quality_count = min(20, features)
    values[:, -quality_count:] += ((rin - rin.mean()) / rin.std())[:, None] * rng.uniform(
        0.5, 1.0, quality_count
    )
    if modality == "protein":
        probability = 0.01 + 0.08 / (1 + np.exp(values))
        if scenario == "plate_drift":
            probability += (np.arange(len(shared)) % 12 == 0)[:, None] * 0.12
        values[rng.random(values.shape) < probability] = np.nan
    return values, truth


def simulate(
    scenario: str,
    output: Path,
    seed: int = 20260805,
    samples: int = 240,
    rna_features: int = 2000,
    protein_features: int = 500,
) -> None:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {', '.join(SCENARIOS)}")
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    condition = np.repeat(["control", "treated"], samples // 2)
    if len(condition) < samples:
        condition = np.append(condition, "treated")
    if scenario == "confounded":
        batch = np.where(condition == "control", "B1", "B2")
    else:
        batch = np.resize(np.array(["B1", "B2", "B3"]), samples)
        rng.shuffle(batch)
    lot = np.resize(np.array(["L1", "L2"]), samples)
    rng.shuffle(lot)
    sex = np.resize(np.array(["F", "M"]), samples)
    rng.shuffle(sex)
    rin = np.clip(rng.normal(8, 0.7, samples), 5, 10)
    shared = (condition == "treated").astype(float) + rng.normal(0, 0.25, samples)
    batch_numeric = pd.Categorical(batch).codes.astype(float)
    manifest = pd.DataFrame(
        {
            "sample_id": [f"S{i + 1:03d}" for i in range(samples)],
            "subject_id": [f"P{i + 1:03d}" for i in range(samples)],
            "condition": condition,
            "sex": sex,
            "extraction_batch": batch,
            "reagent_lot": lot,
            "RIN": rin,
            "run_order": np.arange(1, samples + 1),
        }
    )
    truth = []
    modality_frames = {}
    for name, count in [("rna", rna_features), ("protein", protein_features)]:
        values, rows = _matrix(rng, shared, batch_numeric, rin, count, name, scenario)
        features = [f"F{i:04d}" for i in range(count)]
        frame = pd.DataFrame(values, columns=features)
        frame.insert(0, "sample_id", manifest.sample_id)
        modality_frames[name] = frame
        truth.extend(rows)
    manifest.to_parquet(output / "manifest.parquet", index=False)
    for name, frame in modality_frames.items():
        frame.to_parquet(output / f"{name}.parquet", index=False)
    shared_features = min(200, protein_features, rna_features)
    pd.DataFrame(
        {
            "rna_feature": [f"F{i:04d}" for i in range(shared_features)],
            "protein_feature": [f"F{i:04d}" for i in range(shared_features)],
        }
    ).to_parquet(output / "feature_map.parquet", index=False)
    pd.DataFrame(truth).to_parquet(output / "ground_truth.parquet", index=False)
    technical = ["extraction_batch", "reagent_lot", "RIN"] + (
        ["run_order"] if scenario == "plate_drift" else []
    )
    config = {
        "project": {"name": f"{scenario}-demo", "output_dir": "results", "random_seed": seed},
        "manifest": {
            "path": "manifest.parquet",
            "sample_id_column": "sample_id",
            "subject_id_column": "subject_id",
        },
        "variables": {
            "biological": ["condition", "sex"],
            "technical": technical,
            "protected": ["condition", "sex"],
        },
        "modalities": [
            {
                "name": "rna",
                "kind": "rna_continuous",
                "path": "rna.parquet",
                "orientation": "samples_by_features",
                "transform": "none",
                "max_features": 2000,
            },
            {
                "name": "protein",
                "kind": "proteomics_continuous",
                "path": "protein.parquet",
                "orientation": "samples_by_features",
                "transform": "none",
                "max_features": 500,
            },
        ],
        "analysis": {
            "sample_join": "intersection",
            "latent_components": 10,
            "p_adjust_method": "fdr_bh",
            "permutations": 99,
            "cross_validation_folds": 5,
            "bootstrap_iterations": 20,
            "analysis_budget": "quick",
        },
        "corrections": {
            "methods": ["none", "residualize", "combat"],
            "refuse_if_rank_deficient": True,
            "maximum_confounding_score": 0.85,
        },
        "report": {
            "title": f"Artifactor {scenario.replace('_', ' ').title()} Demo",
            "include_interactive_plots": True,
        },
        "feature_map": "feature_map.parquet",
        "ground_truth": "ground_truth.parquet",
    }
    (output / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output / "README.md").write_text(
        f"# {scenario.replace('_', ' ').title()} simulation\n\nDeterministic synthetic cohort generated with seed {seed}. This dataset is synthetic; its ground truth is known by construction.\n",
        encoding="utf-8",
    )
