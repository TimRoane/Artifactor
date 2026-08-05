import pandas as pd

from artifactor.config import ArtifactorConfig
from artifactor.contracts import EligibilityResult
from artifactor.interpretation import build_findings
from tests.unit.test_config import valid_payload


def test_interpretation_avoids_causal_claims() -> None:
    associations = pd.DataFrame(
        [
            {
                "modality": "rna",
                "factor": "PC1",
                "variable": "batch",
                "role": "technical",
                "effect_size": 0.7,
                "q_value": 0.01,
                "n": 10,
            }
        ]
    )
    findings = build_findings(
        associations,
        EligibilityResult(eligible=True, status="separable"),
        {"method": "none", "rationale": "No gain."},
        ArtifactorConfig.model_validate(valid_payload()),
    )
    text = " ".join(str(x) for x in findings).lower()
    assert "caused by" not in text
    assert all(not finding["causal"] for finding in findings)
