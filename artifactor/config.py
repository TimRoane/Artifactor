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

    @model_validator(mode="after")
    def roles_are_disjoint(self) -> VariablesConfig:
        if set(self.biological) & set(self.technical):
            raise ValueError("variables cannot be both biological and technical")
        return self


class ModalityConfig(StrictModel):
    name: str
    kind: Literal["rna_continuous", "rna_counts", "proteomics_continuous", "generic_continuous"]
    path: Path
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
    analysis_budget: Literal["quick", "standard"] = "standard"
    association_effect_threshold: float = Field(default=0.1, ge=0, le=1)
    association_q_threshold: float = Field(default=0.05, gt=0, le=1)


class CorrectionsConfig(StrictModel):
    methods: list[Literal["none", "residualize", "combat"]] = ["none", "residualize", "combat"]
    refuse_if_rank_deficient: bool = True
    maximum_confounding_score: float = Field(default=0.85, ge=0, le=1)


class ReportConfig(StrictModel):
    title: str = "Artifactor Report"
    include_interactive_plots: bool = True


class ArtifactorConfig(StrictModel):
    project: ProjectConfig
    manifest: ManifestConfig
    variables: VariablesConfig
    modalities: list[ModalityConfig] = Field(min_length=2)
    analysis: AnalysisConfig = AnalysisConfig()
    corrections: CorrectionsConfig = CorrectionsConfig()
    report: ReportConfig = ReportConfig()
    feature_map: Path | None = None
    feature_annotations: Path | None = None
    known_signatures: Path | None = None
    ground_truth: Path | None = None

    @model_validator(mode="after")
    def unique_modalities(self) -> ArtifactorConfig:
        names = [m.name for m in self.modalities]
        if len(names) != len(set(names)):
            raise ValueError("modality names must be unique")
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
            path = Path(modality["path"])
            if not path.is_absolute():
                modality["path"] = root / path
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
