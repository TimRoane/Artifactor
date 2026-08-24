# mypy: ignore-errors
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

from artifactor.config import ArtifactorConfig
from artifactor.contracts import DesignSummary, EligibilityResult


def build_design_evidence(
    metadata: pd.DataFrame,
    config: ArtifactorConfig,
    pairwise: pd.DataFrame,
    eligibility: EligibilityResult,
    diagnostics: dict[str, float | int | bool],
) -> tuple[DesignSummary, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    cells: list[dict[str, object]] = []
    enriched = pairwise.copy()
    extra: list[dict[str, object]] = []
    for row in pairwise.itertuples():
        biological = str(row.biological_variable)
        technical = str(row.technical_variable)
        left, right = metadata[biological], metadata[technical]
        details: dict[str, object] = {}
        if not pd.api.types.is_numeric_dtype(left) and not pd.api.types.is_numeric_dtype(right):
            table = pd.crosstab(left, right, dropna=False)
            expected = (
                chi2_contingency(table, correction=False)[3]
                if min(table.shape) >= 2
                else np.zeros(table.shape)
            )
            for i, biological_level in enumerate(table.index):
                for j, technical_level in enumerate(table.columns):
                    cells.append(
                        {
                            "biological_variable": biological,
                            "technical_variable": technical,
                            "biological_level": str(biological_level),
                            "technical_level": str(technical_level),
                            "count": int(table.iloc[i, j]),
                            "expected_count": float(expected[i, j]),
                            "cell_type": "contingency",
                        }
                    )
            details = {
                "minimum_cell_support": int(table.to_numpy().min()),
                "empty_cell_proportion": float((table.to_numpy() == 0).mean()),
                "all_biological_levels_span_two_technical_levels": bool(
                    ((table > 0).sum(axis=1) >= min(2, table.shape[1])).all()
                ),
                "pair_type": "categorical_categorical",
            }
        elif pd.api.types.is_numeric_dtype(left) != pd.api.types.is_numeric_dtype(right):
            categorical = left if not pd.api.types.is_numeric_dtype(left) else right
            continuous = right if categorical is left else left
            ranges = []
            for level, values in pd.to_numeric(continuous).groupby(categorical):
                cells.append(
                    {
                        "biological_variable": biological,
                        "technical_variable": technical,
                        "biological_level": str(level),
                        "technical_level": "continuous_distribution",
                        "count": int(values.notna().sum()),
                        "expected_count": None,
                        "cell_type": "group_distribution",
                        "minimum": float(values.min()),
                        "median": float(values.median()),
                        "maximum": float(values.max()),
                    }
                )
                ranges.append((float(values.min()), float(values.max())))
            overlap = max(0.0, min(x[1] for x in ranges) - max(x[0] for x in ranges))
            span = max(x[1] for x in ranges) - min(x[0] for x in ranges)
            details = {
                "range_overlap": overlap / span if span else 0.0,
                "pair_type": "categorical_continuous",
            }
        else:
            valid = left.notna() & right.notna()
            slope = (
                float(np.polyfit(pd.to_numeric(left[valid]), pd.to_numeric(right[valid]), 1)[0])
                if valid.sum() >= 3
                else 0.0
            )
            details = {
                "robust_slope": slope,
                "range_overlap": float(row.overlap_score),
                "pair_type": "continuous_continuous",
            }
        extra.append(details)
    if extra:
        enriched = pd.concat([enriched.reset_index(drop=True), pd.DataFrame(extra)], axis=1)
    limiting = [
        f"{r.biological_variable} × {r.technical_variable}: {r.identifiability_status}"
        for r in pairwise.itertuples()
        if r.identifiability_status != "separable"
    ]
    status = eligibility.status
    if status == "warning":
        statuses = set(pairwise.identifiability_status)
        status = "highly_confounded" if "highly_confounded" in statuses else "weak_overlap"
    if eligibility.eligible:
        summary_text = "Declared biology and technical variables have sufficient independent support for correction evaluation."
    else:
        summary_text = "Automated correction is refused because protected biology and technical handling cannot be estimated independently."
    summary = DesignSummary(
        overall_status=status,
        correction_permitted=eligibility.eligible,
        biological_variables=config.variables.biological,
        technical_variables=config.variables.technical,
        protected_variables=config.variables.protected,
        sample_count=len(metadata),
        design_rank=int(diagnostics["rank"]),
        design_columns=int(diagnostics["columns"]),
        condition_number=float(diagnostics["condition_number"]),
        limiting_pairs=limiting,
        summary_text=summary_text,
    )
    matrix_diagnostics = {
        "schema_version": "2.0",
        **diagnostics,
        "numerically_ill_conditioned": bool(float(diagnostics["condition_number"]) > 1e8),
        "aliased_terms": eligibility.reasons if bool(diagnostics["rank_deficient"]) else [],
        "interpretation": "Rank deficiency is a structural identifiability problem; a high condition number is numerical instability. They are reported separately.",
    }
    return summary, enriched, pd.DataFrame(cells), matrix_diagnostics
