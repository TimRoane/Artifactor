from __future__ import annotations

from typing import Protocol

import pandas as pd

from artifactor.config import ModalityConfig
from artifactor.contracts import OmicsMatrix, ValidationResult


class FeatureEvidence(Protocol):
    feature: str
    effect_size: float


class Hypothesis(Protocol):
    title: str
    limitation: str
    follow_up: str


class ModalityPlugin(Protocol):
    name: str

    def validate(self, matrix: OmicsMatrix, metadata: pd.DataFrame) -> ValidationResult: ...

    def preprocess(self, matrix: OmicsMatrix, config: ModalityConfig) -> OmicsMatrix: ...

    def qc_metrics(self, matrix: OmicsMatrix, metadata: pd.DataFrame) -> pd.DataFrame: ...

    def interpret_feature_pattern(self, evidence: FeatureEvidence) -> list[Hypothesis]: ...
