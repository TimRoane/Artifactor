import numpy as np
import pandas as pd

from artifactor.config import ArtifactorConfig
from artifactor.contracts import OmicsMatrix
from artifactor.correction import residualize
from artifactor.design import audit_design
from tests.unit.test_config import valid_payload


def config() -> ArtifactorConfig:
    return ArtifactorConfig.model_validate(valid_payload())


def test_confounding_blocks_aligned_protected_biology() -> None:
    metadata = pd.DataFrame({"condition": ["a", "a", "b", "b"], "batch": ["x", "x", "y", "y"]})
    _, eligibility, summary = audit_design(metadata, config())
    assert not eligibility.eligible
    assert eligibility.status == "non_identifiable"
    assert summary["rank_deficient"]


def test_residualization_preserves_missingness_and_biology() -> None:
    metadata = pd.DataFrame(
        {"condition": ["a", "a", "b", "b", "a", "b"], "batch": ["x", "y", "x", "y", "x", "y"]}
    )
    bio = (metadata.condition == "b").to_numpy(float)
    tech = (metadata.batch == "y").to_numpy(float)
    values = (2 * bio + 4 * tech)[:, None]
    values[0, 0] = np.nan
    source = OmicsMatrix("rna", tuple(str(x) for x in range(6)), ("f",), values, np.isnan(values))
    result = residualize(source, metadata, config())
    assert np.isnan(result.values[0, 0])
    assert np.nanmean(result.values[metadata.condition == "b", 0]) > np.nanmean(
        result.values[metadata.condition == "a", 0]
    )
