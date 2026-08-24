from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

ENVIRONMENT_KEYS = {"timestamp", "start_timestamp", "completion_timestamp", "runtime", "runtime_seconds", "peak_rss", "path", "executor", "observed_cost"}


class RunComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "4.0"
    schema_compatibility: bool
    input_fingerprint_match: bool | None
    config_match: bool | None
    exact_artifact_results: list[dict[str, object]]
    numeric_tolerance_results: list[dict[str, object]]
    decision_parity: bool | None
    finding_parity: bool | None
    environment_differences: list[str]
    overall_status: str


def _normalized(value: object) -> object:
    if isinstance(value, dict):
        return {key: _normalized(item) for key, item in sorted(value.items()) if key not in ENVIRONMENT_KEYS}
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    return value


def compare_runs(left: Path, right: Path, rtol: float = 1e-6, atol: float = 1e-8) -> RunComparison:
    left_run = json.loads((left / "run.json").read_text(encoding="utf-8"))
    right_run = json.loads((right / "run.json").read_text(encoding="utf-8"))
    schema_match = left_run.get("schema_version") == right_run.get("schema_version")
    fingerprint_match = left_run.get("input_fingerprint") == right_run.get("input_fingerprint") if "input_fingerprint" in left_run and "input_fingerprint" in right_run else None
    config_match = left_run.get("config_fingerprint") == right_run.get("config_fingerprint") if "config_fingerprint" in left_run and "config_fingerprint" in right_run else None
    decision_left = left_run.get("recommendation", left_run.get("validation_conclusion"))
    decision_right = right_run.get("recommendation", right_run.get("validation_conclusion"))
    decision_parity = _normalized(decision_left) == _normalized(decision_right)
    exact: list[dict[str, object]] = []
    numeric: list[dict[str, object]] = []
    common = sorted({item.relative_to(left) for item in left.rglob("*") if item.is_file()} & {item.relative_to(right) for item in right.rglob("*") if item.is_file()})
    for relative in common:
        if relative.name == "run.json":
            equal = _normalized(left_run) == _normalized(right_run)
            exact.append({"artifact": str(relative), "equal_after_environment_normalization": equal})
        elif relative.suffix == ".json":
            a = _normalized(json.loads((left / relative).read_text(encoding="utf-8")))
            b = _normalized(json.loads((right / relative).read_text(encoding="utf-8")))
            exact.append({"artifact": str(relative), "equal_after_environment_normalization": a == b})
        elif relative.suffix == ".parquet":
            a, b = pd.read_parquet(left / relative), pd.read_parquet(right / relative)
            same_shape = a.shape == b.shape and list(a.columns) == list(b.columns)
            non_numeric_equal = same_shape and all(a[column].fillna("<NA>").astype(str).equals(b[column].fillna("<NA>").astype(str)) for column in a.columns if not pd.api.types.is_numeric_dtype(a[column]))
            numeric_columns = [column for column in a.columns if pd.api.types.is_numeric_dtype(a[column])] if same_shape else []
            numeric_equal = same_shape and all(np.allclose(a[column].to_numpy(float), b[column].to_numpy(float), rtol=rtol, atol=atol, equal_nan=True) for column in numeric_columns)
            exact.append({"artifact": str(relative), "identifiers_and_shape_equal": bool(same_shape and non_numeric_equal)})
            numeric.append({"artifact": str(relative), "columns": numeric_columns, "within_tolerance": bool(numeric_equal), "rtol": rtol, "atol": atol})
    exact_ok = all(bool(item.get("equal_after_environment_normalization", item.get("identifiers_and_shape_equal"))) for item in exact)
    numeric_ok = all(bool(item["within_tolerance"]) for item in numeric)
    if not schema_match:
        status = "not_comparable"
    elif not exact_ok or not numeric_ok or not decision_parity:
        status = "not_equivalent"
    elif left_run == right_run:
        status = "equivalent"
    elif numeric:
        status = "equivalent_within_tolerance"
    else:
        status = "scientifically_equivalent_with_environment_differences"
    return RunComparison(schema_compatibility=schema_match, input_fingerprint_match=fingerprint_match, config_match=config_match, exact_artifact_results=exact, numeric_tolerance_results=numeric, decision_parity=decision_parity, finding_parity=decision_parity, environment_differences=[key for key in sorted(ENVIRONMENT_KEYS) if left_run.get(key) != right_run.get(key) and (key in left_run or key in right_run)], overall_status=status)
