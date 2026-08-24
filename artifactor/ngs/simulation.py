from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

NGS_SCENARIOS = ("ngs_separable", "ngs_confounded", "ffpe_damage", "bridge_controls")


def _negative_binomial(
    rng: np.random.Generator, mean: np.ndarray, dispersion: float = 0.18
) -> np.ndarray:
    size = 1.0 / dispersion
    probability = size / (size + np.maximum(mean, 1e-8))
    return rng.negative_binomial(size, probability)


def _beta_binomial(
    rng: np.random.Generator, depth: np.ndarray, probability: np.ndarray, rho: float = 0.02
) -> np.ndarray:
    concentration = max(2.0, 1.0 / rho - 1.0)
    alpha = np.maximum(probability * concentration, 1e-5)
    beta = np.maximum((1 - probability) * concentration, 1e-5)
    sampled = rng.beta(alpha, beta)
    sampled = np.where(probability < 1e-4, probability, sampled)
    return rng.binomial(depth.astype(int), sampled)


def simulate_ngs(
    scenario: str,
    output: Path,
    seed: int = 20260806,
    samples: int = 384,
    targets: int = 800,
    loci: int = 200,
) -> None:
    if scenario not in NGS_SCENARIOS:
        raise ValueError(f"unknown targeted-NGS scenario {scenario!r}")
    if samples < 16 or targets < 20 or loci < 12:
        raise ValueError(
            "targeted-NGS simulation requires at least 16 samples, 20 targets, and 12 loci"
        )
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    sample_ids = np.array([f"N{i + 1:04d}" for i in range(samples)])
    run = np.resize(np.array(["RUN1", "RUN2", "RUN3", "RUN4"]), samples)
    prep = np.resize(np.array(["PREP1", "PREP2", "PREP3", "PREP4"]), samples)
    lot = np.resize(np.array(["LOT1", "LOT2"]), samples)
    condition = np.resize(np.array(["control", "treated"]), samples)
    panel = np.resize(np.array(["PANEL_A", "PANEL_B"]), samples)
    if scenario == "ngs_confounded":
        condition = np.where(np.isin(run, ["RUN1", "RUN2"]), "control", "treated")
        panel = np.where(condition == "control", "PANEL_A", "PANEL_B")
    else:
        rng.shuffle(run)
        rng.shuffle(prep)
        rng.shuffle(lot)
        rng.shuffle(panel)
    ffpe = np.resize(np.array(["FFPE", "fresh"]), samples)
    rng.shuffle(ffpe)
    dv200 = np.where(ffpe == "FFPE", rng.normal(45, 10, samples), rng.normal(85, 5, samples)).clip(
        15, 100
    )
    control_type = np.full(samples, "study_sample", dtype=object)
    control_count = max(8, samples // 8)
    control_type[:control_count] = np.resize(
        np.array(["positive_control", "negative_control"]), control_count
    )
    if scenario == "bridge_controls":
        control_type[: max(16, samples // 4)] = "reference_control"
    replicate_group = np.array([None] * samples, dtype=object)
    for index in range(0, control_count - 1, 2):
        replicate_group[index : index + 2] = f"REP{index // 2 + 1:03d}"
    subject_ids = np.array([f"SUB{i + 1:04d}" for i in range(samples)], dtype=object)
    for index in range(0, control_count - 1, 2):
        subject_ids[index : index + 2] = f"REP_SUB{index // 2 + 1:03d}"
    exposure = rng.lognormal(np.log(1_500_000), 0.25, samples)
    exposure *= (
        pd.Series(run).map({"RUN1": 0.75, "RUN2": 0.95, "RUN3": 1.10, "RUN4": 1.25}).to_numpy()
    )
    sex = np.resize(np.array(["F", "M"]), samples)
    ancestry = np.resize(np.array(["group_A", "group_B"]), samples)
    rng.shuffle(sex)
    rng.shuffle(ancestry)
    manifest = pd.DataFrame(
        {
            "sample_id": sample_ids,
            "subject_id": subject_ids,
            "condition": condition,
            "sample_type": "synthetic_reference"
            if scenario == "bridge_controls"
            else "synthetic_specimen",
            "sex": sex,
            "ancestry_group": ancestry,
            "tumor_purity": rng.uniform(0.2, 0.8, samples),
            "ffpe_status": ffpe,
            "DV200": dv200,
            "input_mass_ng": rng.uniform(20, 100, samples),
            "extraction_batch": np.resize(np.array(["EXT1", "EXT2"]), samples),
            "library_prep_batch": prep,
            "capture_batch": lot,
            "sequencing_run": run,
            "lane": np.resize(np.array(["L1", "L2"]), samples),
            "operator": np.resize(np.array(["OP1", "OP2"]), samples),
            "instrument": np.resize(np.array(["INST1", "INST2"]), samples),
            "instrument_chemistry": "CHEM_A",
            "reagent_lot": lot,
            "panel_version": panel,
            "pipeline_version": "synthetic-pipeline-1.0",
            "reference_build": "GRCh38",
            "replicate_group": replicate_group,
            "control_type": control_type,
        }
    )

    target_ids = np.array([f"T{i + 1:04d}" for i in range(targets)])
    target_length = rng.integers(80, 260, targets)
    gc = rng.uniform(0.25, 0.75, targets)
    efficiency = rng.lognormal(0, 0.35, targets)
    bio_count = max(4, int(targets * 0.20))
    tech_count = max(4, int(targets * 0.15))
    mixed_count = max(2, int(targets * 0.05))
    bio_effect = np.zeros(targets)
    tech_effect = np.zeros(targets)
    bio_effect[:bio_count] = rng.uniform(0.45, 0.75, bio_count)
    tech_effect[bio_count : bio_count + tech_count] = rng.uniform(0.55, 0.9, tech_count)
    bio_effect[bio_count + tech_count : bio_count + tech_count + mixed_count] = rng.uniform(
        0.4, 0.65, mixed_count
    )
    tech_effect[bio_count + tech_count : bio_count + tech_count + mixed_count] = rng.uniform(
        0.5, 0.8, mixed_count
    )
    if scenario == "bridge_controls":
        tech_effect *= 1.4
    absent_b = set(target_ids[-max(1, targets // 20) :])
    annotation_rows = []
    for panel_name in ("PANEL_A", "PANEL_B"):
        for index, target in enumerate(target_ids):
            if panel_name == "PANEL_B" and target in absent_b:
                continue
            annotation_rows.append(
                {
                    "target_id": target,
                    "panel_version": panel_name,
                    "chromosome": str(index % 22 + 1),
                    "start": 1_000_000 + index * 500,
                    "end": 1_000_000 + index * 500 + int(target_length[index]),
                    "gene": f"GENE{index % 100:03d}",
                    "transcript": None,
                    "exon": str(index % 12 + 1),
                    "target_length": int(target_length[index]),
                    "gc_fraction": float(gc[index]),
                    "mappability": float(rng.uniform(0.85, 1.0)),
                    "expected_copy_number_class": "diploid",
                    "reference_build": "GRCh38",
                }
            )
    target_annotations = pd.DataFrame(annotation_rows)
    coverage_rows = []
    sample_gc_slope = rng.normal(0, 0.55, samples) + np.where(ffpe == "FFPE", 0.25, 0)
    for sample_index, sample_id in enumerate(sample_ids):
        supported = (
            target_ids
            if panel[sample_index] == "PANEL_A"
            else np.array([x for x in target_ids if x not in absent_b])
        )
        indices = np.array([int(item[1:]) - 1 for item in supported])
        linear = (
            np.log(exposure[sample_index] / 1_500_000)
            + np.log(efficiency[indices])
            + (condition[sample_index] == "treated") * bio_effect[indices]
            + (lot[sample_index] == "LOT2") * tech_effect[indices]
            + sample_gc_slope[sample_index] * (gc[indices] - 0.5)
        )
        mean = np.exp(linear) * target_length[indices] * 0.9
        counts = _negative_binomial(rng, mean)
        low_depth = rng.random(len(indices)) < np.where(
            exposure[sample_index] < 1_000_000, 0.03, 0.005
        )
        counts[low_depth] = 0
        for local, target_index in enumerate(indices):
            coverage_rows.append(
                {
                    "sample_id": sample_id,
                    "target_id": target_ids[target_index],
                    "raw_count": int(counts[local]),
                    "callable_bases": int(target_length[target_index]),
                    "mean_depth": float(counts[local] / target_length[target_index]),
                    "median_depth": float(counts[local] / target_length[target_index] * 0.92),
                }
            )
    coverage = pd.DataFrame(coverage_rows)
    coverage_by_sample = (
        coverage.groupby("sample_id")
        .agg(
            total_target_counts=("raw_count", "sum"),
            mean_target_depth=("mean_depth", "mean"),
            median_target_depth=("median_depth", "median"),
            callable_target_fraction=("raw_count", lambda x: float((x > 0).mean())),
        )
        .reindex(sample_ids)
    )
    sample_qc = pd.DataFrame(
        {
            "sample_id": sample_ids,
            "total_reads": exposure.astype(int),
            "mapped_reads": (exposure * rng.uniform(0.92, 0.98, samples)).astype(int),
            "usable_fragments": (exposure * rng.uniform(0.55, 0.72, samples)).astype(int),
            "mean_target_depth": coverage_by_sample.mean_target_depth.to_numpy(),
            "median_target_depth": coverage_by_sample.median_target_depth.to_numpy(),
            "coverage_uniformity": rng.uniform(0.78, 0.94, samples) - (lot == "LOT2") * 0.04,
            "duplicate_rate": rng.uniform(0.08, 0.28, samples),
            "on_target_rate": rng.uniform(0.65, 0.88, samples),
            "insert_size_median": rng.normal(185, 18, samples),
            "gc_bias_score": sample_gc_slope,
            "contamination_estimate": rng.uniform(0, 0.025, samples),
            "callable_target_fraction": coverage_by_sample.callable_target_fraction.to_numpy(),
        }
    )

    refs = np.resize(np.array(["C", "G", "A", "T"]), loci)
    alts = np.resize(np.array(["T", "A", "G", "C"]), loci)
    variant_ids = np.array([f"V{i + 1:04d}" for i in range(loci)])
    contexts = np.array([f"A{ref}G" for ref in refs])
    variant_annotations = pd.DataFrame(
        {
            "variant_id": variant_ids,
            "reference_build": "GRCh38",
            "chromosome": [str(i % 22 + 1) for i in range(loci)],
            "position": [2_000_000 + i * 100 for i in range(loci)],
            "reference_allele": refs,
            "alternate_allele": alts,
            "gene": [f"GENE{i % 100:03d}" for i in range(loci)],
            "variant_class": [f"{r}>{a}" for r, a in zip(refs, alts, strict=True)],
            "trinucleotide_context": contexts,
            "expected_control_state": [
                "positive" if i < max(4, loci // 10) else "negative" for i in range(loci)
            ],
            "lod_bin": np.resize(np.array(["low", "medium", "high"]), loci),
        }
    )
    allele_rows = []
    truth_rows = []
    known_truth_rows = []
    positive_count = max(4, loci // 10)
    biological_loci = max(3, loci // 12)
    for sample_index, sample_id in enumerate(sample_ids):
        depth = rng.poisson(np.maximum(80, exposure[sample_index] / 5000), loci).astype(int)
        true_vaf = np.zeros(loci)
        true_vaf[:positive_count] = np.linspace(0.03, 0.30, positive_count)
        if condition[sample_index] == "treated":
            true_vaf[positive_count : positive_count + biological_loci] = 0.12
        artifact = np.zeros(loci)
        context_mask = np.isin(variant_annotations.variant_class.to_numpy(), ["C>T", "G>A"])
        if scenario == "ffpe_damage" and ffpe[sample_index] == "FFPE":
            artifact_mask = context_mask & (np.arange(loci) >= positive_count + biological_loci)
            artifact[artifact_mask] = 0.012 + (100 - dv200[sample_index]) / 5000
        probability = np.clip(true_vaf + artifact, 1e-6, 0.95)
        alt = _beta_binomial(rng, depth, probability, rho=0.015)
        ref = depth - alt
        alt_forward = rng.binomial(alt, np.where(artifact > 0, 0.72, 0.5))
        alt_f1r2 = rng.binomial(alt, np.where(artifact > 0, 0.75, 0.5))
        for locus_index, variant_id in enumerate(variant_ids):
            observed_vaf = alt[locus_index] / depth[locus_index] if depth[locus_index] else 0.0
            call = (
                "called"
                if depth[locus_index] >= 50 and alt[locus_index] >= 3 and observed_vaf >= 0.02
                else "not_called"
            )
            allele_rows.append(
                {
                    "sample_id": sample_id,
                    "variant_id": variant_id,
                    "ref_count": int(ref[locus_index]),
                    "alt_count": int(alt[locus_index]),
                    "total_depth": int(depth[locus_index]),
                    "ref_forward": int(rng.binomial(ref[locus_index], 0.5)),
                    "ref_reverse": None,
                    "alt_forward": int(alt_forward[locus_index]),
                    "alt_reverse": int(alt[locus_index] - alt_forward[locus_index]),
                    "alt_f1r2": int(alt_f1r2[locus_index]),
                    "alt_f2r1": int(alt[locus_index] - alt_f1r2[locus_index]),
                    "base_quality_mean": float(
                        rng.normal(34 if artifact[locus_index] == 0 else 27, 2)
                    ),
                    "mapping_quality_mean": float(rng.normal(57, 2)),
                    "read_position_mean": float(
                        np.clip(rng.normal(0.5 if artifact[locus_index] == 0 else 0.25, 0.08), 0, 1)
                    ),
                    "insert_size_mean": float(
                        np.clip(rng.normal(145 if artifact[locus_index] == 0 else 105, 15), 30, None)
                    ),
                    "existing_call_state": call,
                }
            )
            truth_state = "positive" if true_vaf[locus_index] > 0 else "negative"
            truth_rows.append(
                {
                    "schema_version": "3.0",
                    "sample_id": sample_id,
                    "variant_id": variant_id,
                    "truth_state": truth_state,
                    "true_vaf": float(true_vaf[locus_index]),
                    "artifact_state": "artifact" if artifact[locus_index] > 0 else "none",
                    "artifact_type": "FFPE_C>T_G>A" if artifact[locus_index] > 0 else None,
                    "artifact_effect_size": float(artifact[locus_index]),
                    "expected_callable": bool(depth[locus_index] >= 100),
                }
            )
            known_truth_rows.append(
                {
                    "sample_id": sample_id,
                    "variant_id": variant_id,
                    "truth_state": truth_state,
                    "expected_vaf": float(true_vaf[locus_index]),
                    "truth_source": "simulator",
                    "confidence_region": None,
                }
            )
    allele_counts = pd.DataFrame(allele_rows)
    # Fill ref_reverse after ref_forward exists, preserving exact integer totals.
    allele_counts["ref_reverse"] = allele_counts.ref_count - allele_counts.ref_forward
    target_truth = pd.DataFrame(
        {
            "schema_version": "3.0",
            "target_id": target_ids,
            "is_biological": (bio_effect != 0) & (tech_effect == 0),
            "is_technical": (bio_effect == 0) & (tech_effect != 0),
            "is_mixed": (bio_effect != 0) & (tech_effect != 0),
            "is_null": (bio_effect == 0) & (tech_effect == 0),
            "biological_effect_size": bio_effect,
            "technical_effect_size": tech_effect,
            "technical_variable": [
                "reagent_lot" if effect != 0 else None for effect in tech_effect
            ],
            "gc_sensitivity": gc - 0.5,
            "baseline_efficiency": efficiency,
        }
    )
    sample_truth = manifest[
        [
            "sample_id",
            "condition",
            "sequencing_run",
            "reagent_lot",
            "ffpe_status",
            "DV200",
            "replicate_group",
            "control_type",
        ]
    ].copy()
    sample_truth.insert(0, "schema_version", "3.0")

    tables = {
        "manifest.parquet": manifest,
        "sample_qc.parquet": sample_qc,
        "target_coverage.parquet": coverage,
        "target_annotations.parquet": target_annotations,
        "variant_counts.parquet": allele_counts,
        "variant_annotations.parquet": variant_annotations,
        "known_truth.parquet": pd.DataFrame(known_truth_rows),
        "target_ground_truth.parquet": target_truth,
        "variant_ground_truth.parquet": pd.DataFrame(truth_rows),
        "sample_ground_truth.parquet": sample_truth,
    }
    for filename, frame in tables.items():
        frame.to_parquet(output / filename, index=False)
    technical = ["library_prep_batch", "sequencing_run", "reagent_lot", "DV200", "ffpe_status"]
    config = {
        "project": {
            "name": scenario.replace("_", "-"),
            "output_dir": "results",
            "random_seed": seed,
        },
        "manifest": {
            "path": "manifest.parquet",
            "sample_id_column": "sample_id",
            "subject_id_column": "subject_id",
        },
        "variables": {
            "biological": ["condition"],
            "technical": technical,
            "protected": ["condition", "sex", "ancestry_group", "tumor_purity"],
            "controls": ["control_type", "replicate_group"],
        },
        "modalities": [
            {
                "name": "targeted_coverage",
                "kind": "targeted_ngs_coverage",
                "measurement_family": "count",
                "path": "target_coverage.parquet",
                "annotations": "target_annotations.parquet",
                "sample_qc": "sample_qc.parquet",
            },
            {
                "name": "allele_counts",
                "kind": "targeted_ngs_allele_counts",
                "measurement_family": "fraction",
                "path": "variant_counts.parquet",
                "annotations": "variant_annotations.parquet",
                "truth": "known_truth.parquet",
            },
        ],
        "ngs": {
            "reference_build": "GRCh38",
            "panel_version_column": "panel_version",
            "minimum_total_depth": 100,
            "minimum_alt_count_for_diagnostics": 2,
            "low_vaf_threshold": 0.05,
            "use_beta_binomial": True,
        },
        "coverage_analysis": {
            "candidates": ["raw_offset", "median_ratio", "gc_normalized", "nb_technical_residual"],
            "latent_features": "deviance_residuals",
            "dispersion_policy": "targetwise_shrunk",
        },
        "allele_analysis": {
            "preserve_calls": True,
            "context_artifacts": True,
            "strand_bias": "when_available",
            "orientation_bias": "when_available",
        },
        "evaluation": {
            "cross_validation_folds": 5,
            "bootstrap_iterations": 20,
            "group_column": "subject_id",
        },
        "analysis": {
            "analysis_budget": "quick",
            "latent_components": 5,
            "permutations": 99,
            "cross_validation_folds": 3,
            "bootstrap_iterations": 20,
        },
        "corrections": {
            "methods": ["none"],
            "refuse_if_rank_deficient": True,
            "maximum_confounding_score": 0.85,
        },
        "report": {
            "title": f"Artifactor {scenario.replace('_', ' ').title()} Targeted-NGS Demo",
            "include_interactive_plots": True,
        },
    }
    (output / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (output / "README.md").write_text(
        f"# {scenario.replace('_', ' ').title()} targeted-NGS simulation\n\nDeterministic analysis-ready targeted-NGS coverage and allele counts generated with seed {seed}. Original counts and call states are immutable. Expected conclusion: {'mitigation refusal and bridge controls' if scenario == 'ngs_confounded' else 'FFPE-like low-VAF context diagnosis without call rewriting' if scenario == 'ffpe_damage' else 'localization of a shifted lot using repeated controls' if scenario == 'bridge_controls' else 'eligible count-aware exploratory coverage mitigation with protected biology retained'}.\n",
        encoding="utf-8",
    )
