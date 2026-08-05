from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, spearmanr

from artifactor.config import ArtifactorConfig
from artifactor.contracts import EligibilityResult


def encoded_design(metadata: pd.DataFrame, variables: list[str]) -> tuple[np.ndarray, list[str]]:
    parts = [pd.Series(1.0, index=metadata.index, name="intercept")]
    for variable in dict.fromkeys(variables):
        values = metadata[variable]
        if pd.api.types.is_numeric_dtype(values):
            parts.append(
                pd.to_numeric(values, errors="coerce").fillna(values.median()).rename(variable)
            )
        else:
            dummies = pd.get_dummies(
                values.astype("string").fillna("<missing>"),
                prefix=variable,
                drop_first=True,
                dtype=float,
            )
            parts.extend(dummies.iloc[:, i] for i in range(dummies.shape[1]))
    frame = pd.concat(parts, axis=1)
    return frame.to_numpy(float), [str(c) for c in frame.columns]


def _eta_squared(categories: pd.Series, values: pd.Series) -> float:
    valid = categories.notna() & values.notna()
    cats, vals = categories[valid], pd.to_numeric(values[valid])
    grand = vals.mean()
    total = float(((vals - grand) ** 2).sum())
    if total <= 0:
        return 0.0
    between = sum(len(group) * float(group.mean() - grand) ** 2 for _, group in vals.groupby(cats))
    return min(1.0, max(0.0, between / total))


def association_score(left: pd.Series, right: pd.Series) -> float:
    left_num = pd.api.types.is_numeric_dtype(left)
    right_num = pd.api.types.is_numeric_dtype(right)
    if left_num and right_num:
        corr = spearmanr(left, right, nan_policy="omit").statistic
        return 0.0 if math.isnan(corr) else abs(float(corr))
    if left_num != right_num:
        return _eta_squared(right if left_num else left, left if left_num else right)
    table = pd.crosstab(left, right)
    if min(table.shape) < 2:
        return 1.0
    chi2 = chi2_contingency(table, correction=False)[0]
    n = table.to_numpy().sum()
    phi2 = chi2 / n
    correction = ((table.shape[1] - 1) * (table.shape[0] - 1)) / max(n - 1, 1)
    phi2 = max(0.0, phi2 - correction)
    denom = max(1e-12, min(table.shape[1] - 1, table.shape[0] - 1) - correction)
    return min(1.0, math.sqrt(phi2 / denom))


def audit_design(
    metadata: pd.DataFrame, config: ArtifactorConfig
) -> tuple[pd.DataFrame, EligibilityResult, dict[str, float | int | bool]]:
    variables = list(
        dict.fromkeys(
            config.variables.biological + config.variables.protected + config.variables.technical
        )
    )
    design, _ = encoded_design(metadata, variables)
    rank = int(np.linalg.matrix_rank(design))
    condition = float(np.linalg.cond(design))
    rank_deficient = rank < design.shape[1]
    rows: list[dict[str, object]] = []
    blocked = rank_deficient and config.corrections.refuse_if_rank_deficient
    reasons: list[str] = []
    for biological in config.variables.biological:
        for technical in config.variables.technical:
            score = association_score(metadata[biological], metadata[technical])
            if not pd.api.types.is_numeric_dtype(
                metadata[biological]
            ) and not pd.api.types.is_numeric_dtype(metadata[technical]):
                table = pd.crosstab(metadata[biological], metadata[technical])
                supported = (table > 0).sum(axis=1)
                overlap = float((supported >= min(2, table.shape[1])).mean())
            else:
                overlap = 1.0 - score
            if score >= 0.999 or overlap == 0:
                status = "non_identifiable"
            elif score >= config.corrections.maximum_confounding_score:
                status = "highly_confounded"
            elif overlap < 0.75:
                status = "weak_overlap"
            else:
                status = "separable"
            if status == "non_identifiable" and biological in config.variables.protected:
                blocked = True
                reasons.append(f"protected {biological} is non-identifiable from {technical}")
            rows.append(
                {
                    "biological_variable": biological,
                    "technical_variable": technical,
                    "association_score": score,
                    "overlap_score": overlap,
                    "identifiability_status": status,
                    "reason": f"association={score:.3f}, overlap={overlap:.3f}",
                }
            )
    if rank_deficient:
        reasons.append(f"combined design is rank deficient ({rank}/{design.shape[1]})")
    status = (
        "non_identifiable"
        if blocked
        else (
            "warning"
            if any(r["identifiability_status"] != "separable" for r in rows)
            else "separable"
        )
    )
    eligibility = EligibilityResult(eligible=not blocked, status=status, reasons=reasons)
    return (
        pd.DataFrame(rows),
        eligibility,
        {
            "rank": rank,
            "columns": design.shape[1],
            "condition_number": condition,
            "rank_deficient": rank_deficient,
        },
    )
