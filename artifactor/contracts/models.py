from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["warning", "error"]
    code: str
    message: str
    remediation: str | None = None


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valid: bool
    issues: list[ValidationIssue] = []
    sample_count: int = 0
    modality_samples: dict[str, int] = {}


class EligibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eligible: bool
    status: str
    reasons: list[str] = []


@dataclass(frozen=True)
class OmicsMatrix:
    name: str
    sample_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    values: np.ndarray
    missing_mask: np.ndarray
    kind: str = "generic_continuous"

    def to_frame(self) -> pd.DataFrame:
        frame = pd.DataFrame(self.values, columns=self.feature_names)
        frame.insert(0, "sample_id", self.sample_ids)
        return frame


@dataclass(frozen=True)
class RunArtifact:
    artifact_type: str
    path: Path
    checksum: str
    schema_version: str
    producer: str
