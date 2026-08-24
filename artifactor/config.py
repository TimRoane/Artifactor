from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectConfig(StrictModel):
    name: str
    output_dir: Path = Path("results")
    random_seed: int = 20260805


class ManifestConfig(StrictModel):
    path: Path
    sample_id_column: str = "sample_id"
    subject_id_column: str | None = None


class VariablesConfig(StrictModel):
    biological: list[str] = []
    technical: list[str] = []
    protected: list[str] = []
    identifier: list[str] = []
    ignore: list[str] = []
    controls: list[str] = []

    @model_validator(mode="after")
    def roles_are_disjoint(self) -> VariablesConfig:
        if set(self.biological) & set(self.technical):
            raise ValueError("variables cannot be both biological and technical")
        return self


class ModalityConfig(StrictModel):
    name: str
    kind: Literal[
        "rna_continuous",
        "rna_counts",
        "proteomics_continuous",
        "generic_continuous",
        "genomic_continuous",
        "count_matrix",
        "fraction_matrix",
        "variant_binary",
        "segment_matrix",
        "sparse_event",
        "targeted_ngs_coverage",
        "targeted_ngs_allele_counts",
    ]
    path: Path
    measurement_family: (
        Literal["continuous", "count", "fraction", "binary", "segment", "sparse_event"] | None
    ) = None
    annotations: Path | None = None
    sample_qc: Path | None = None
    truth: Path | None = None
    orientation: Literal["samples_by_features", "features_by_samples"] = "samples_by_features"
    transform: Literal["none", "log1p"] = "none"
    max_features: int | None = Field(default=None, ge=2)

    @model_validator(mode="after")
    def counts_require_transform(self) -> ModalityConfig:
        if self.kind == "rna_counts" and self.transform == "none":
            raise ValueError("raw RNA counts require an explicit transform such as log1p")
        return self


class AnalysisConfig(StrictModel):
    sample_join: Literal["intersection", "union"] = "intersection"
    latent_components: int = Field(default=10, ge=1)
    p_adjust_method: Literal["fdr_bh"] = "fdr_bh"
    permutations: int = Field(default=999, ge=0)
    cross_validation_folds: int = Field(default=5, ge=2)
    bootstrap_iterations: int = Field(default=100, ge=0)
    analysis_budget: Literal["quick", "standard", "full"] = "standard"
    association_effect_threshold: float = Field(default=0.1, ge=0, le=1)
    association_q_threshold: float = Field(default=0.05, gt=0, le=1)
    factor_stability_bootstraps: int = Field(default=10, ge=0)
    technical_baseline_tolerance: float = Field(default=1e-8, gt=0)
    cross_modal_loss_guardrail: float = Field(default=0.10, ge=0, le=1)


class CorrectionsConfig(StrictModel):
    methods: list[Literal["none", "residualize", "combat"]] = ["none", "residualize", "combat"]
    refuse_if_rank_deficient: bool = True
    maximum_confounding_score: float = Field(default=0.85, ge=0, le=1)


class ReportConfig(StrictModel):
    title: str = "Artifactor Report"
    include_interactive_plots: bool = True
    browser_embedding_limit: int = Field(default=1000, ge=50)
    embed_full_plotly: bool = False


class NGSConfig(StrictModel):
    reference_build: str
    panel_version_column: str = "panel_version"
    minimum_total_depth: int = Field(default=100, ge=1)
    minimum_alt_count_for_diagnostics: int = Field(default=2, ge=1)
    low_vaf_threshold: float = Field(default=0.05, gt=0, lt=1)
    use_beta_binomial: bool = True
    minimum_callable_target_fraction: float = Field(default=0.8, ge=0, le=1)
    require_pipeline_version: bool = True


class CoverageAnalysisConfig(StrictModel):
    candidates: list[
        Literal["raw_offset", "median_ratio", "gc_normalized", "nb_technical_residual"]
    ] = ["raw_offset", "median_ratio", "gc_normalized", "nb_technical_residual"]
    latent_features: Literal["deviance_residuals", "pearson_residuals"] = "deviance_residuals"
    dispersion_policy: Literal["targetwise_shrunk", "fixed"] = "targetwise_shrunk"
    maximum_biological_loss: float = Field(default=0.05, ge=0, le=1)
    minimum_technical_removal: float = Field(default=0.40, ge=0, le=1)
    maximum_replicate_loss: float = Field(default=0.10, ge=0, le=1)


class AlleleAnalysisConfig(StrictModel):
    preserve_calls: bool = True
    context_artifacts: bool = True
    strand_bias: Literal["when_available", "disabled"] = "when_available"
    orientation_bias: Literal["when_available", "disabled"] = "when_available"


class EvaluationConfig(StrictModel):
    cross_validation_folds: int = Field(default=5, ge=2)
    bootstrap_iterations: int = Field(default=100, ge=0)
    group_column: str | None = None


class ArtifactorConfig(StrictModel):
    project: ProjectConfig
    manifest: ManifestConfig
    variables: VariablesConfig
    modalities: list[ModalityConfig] = Field(min_length=1)
    analysis: AnalysisConfig = AnalysisConfig()
    corrections: CorrectionsConfig = CorrectionsConfig()
    report: ReportConfig = ReportConfig()
    feature_map: Path | None = None
    feature_annotations: Path | None = None
    known_signatures: Path | None = None
    ground_truth: Path | None = None
    ngs: NGSConfig | None = None
    coverage_analysis: CoverageAnalysisConfig = CoverageAnalysisConfig()
    allele_analysis: AlleleAnalysisConfig = AlleleAnalysisConfig()
    evaluation: EvaluationConfig = EvaluationConfig()

    @model_validator(mode="after")
    def unique_modalities(self) -> ArtifactorConfig:
        names = [m.name for m in self.modalities]
        if len(names) != len(set(names)):
            raise ValueError("modality names must be unique")
        ngs_kinds = {"targeted_ngs_coverage", "targeted_ngs_allele_counts"}
        if any(item.kind in ngs_kinds for item in self.modalities) and self.ngs is None:
            raise ValueError("targeted-NGS modalities require an ngs configuration section")
        for item in self.modalities:
            if item.kind in ngs_kinds and item.annotations is None:
                raise ValueError(f"{item.name}: targeted-NGS modalities require annotations")
            if item.kind == "targeted_ngs_coverage" and item.sample_qc is None:
                raise ValueError(f"{item.name}: targeted-NGS coverage requires sample_qc")
            expected_family = {
                "targeted_ngs_coverage": "count",
                "targeted_ngs_allele_counts": "fraction",
            }.get(item.kind)
            if expected_family and item.measurement_family not in {None, expected_family}:
                raise ValueError(
                    f"{item.name}: {item.kind} requires measurement_family: {expected_family}"
                )
        if (
            any(item.kind == "targeted_ngs_allele_counts" for item in self.modalities)
            and not self.allele_analysis.preserve_calls
        ):
            raise ValueError("v0.3.0 requires allele_analysis.preserve_calls: true")
        return self

    def resolved(self, config_path: Path) -> ArtifactorConfig:
        root = config_path.resolve().parent
        data = self.model_dump()
        for section, key in [("manifest", "path")]:
            path = Path(data[section][key])
            if not path.is_absolute():
                data[section][key] = root / path
        output = Path(data["project"]["output_dir"])
        if not output.is_absolute():
            data["project"]["output_dir"] = root / output
        for modality in data["modalities"]:
            for key in ("path", "annotations", "sample_qc", "truth"):
                if modality.get(key):
                    path = Path(modality[key])
                    if not path.is_absolute():
                        modality[key] = root / path
        for key in ("feature_map", "feature_annotations", "known_signatures", "ground_truth"):
            if data.get(key):
                path = Path(data[key])
                if not path.is_absolute():
                    data[key] = root / path
        return ArtifactorConfig.model_validate(data)


def load_config(path: Path) -> ArtifactorConfig:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"configuration not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    return ArtifactorConfig.model_validate(payload).resolved(path)
