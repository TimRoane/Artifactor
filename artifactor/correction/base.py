from __future__ import annotations

from typing import Protocol

from artifactor.contracts import EligibilityResult, OmicsMatrix


class AnalysisContext(Protocol):
    random_seed: int


class FittedCorrection(Protocol):
    method: str


class CorrectionMethod(Protocol):
    name: str

    def validate_design(self, context: AnalysisContext) -> EligibilityResult: ...

    def fit(self, train: OmicsMatrix, context: AnalysisContext) -> FittedCorrection: ...

    def transform(self, data: OmicsMatrix, fitted: FittedCorrection) -> OmicsMatrix: ...
