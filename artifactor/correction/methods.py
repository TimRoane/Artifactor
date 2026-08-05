from __future__ import annotations

import numpy as np
import pandas as pd

from artifactor.config import ArtifactorConfig
from artifactor.contracts import OmicsMatrix
from artifactor.design import encoded_design


def _restore(matrix: OmicsMatrix, values: np.ndarray) -> OmicsMatrix:
    values = values.copy()
    values[matrix.missing_mask] = np.nan
    return OmicsMatrix(
        matrix.name,
        matrix.sample_ids,
        matrix.feature_names,
        values,
        matrix.missing_mask.copy(),
        matrix.kind,
    )


def no_correction(matrix: OmicsMatrix) -> OmicsMatrix:
    return _restore(matrix, matrix.values)


def residualize(
    matrix: OmicsMatrix, metadata: pd.DataFrame, config: ArtifactorConfig
) -> OmicsMatrix:
    biology = list(dict.fromkeys(config.variables.biological + config.variables.protected))
    x_bio, _ = encoded_design(metadata, biology)
    x_full, _ = encoded_design(metadata, biology + config.variables.technical)
    values = matrix.values.copy()
    medians = np.nanmedian(values, axis=0)
    filled = np.where(np.isnan(values), medians, values)
    coefficients = np.linalg.lstsq(x_full, filled, rcond=None)[0]
    bio_columns = x_bio.shape[1]
    technical_signal = x_full[:, bio_columns:] @ coefficients[bio_columns:]
    return _restore(matrix, filled - technical_signal)


def combat(matrix: OmicsMatrix, metadata: pd.DataFrame, config: ArtifactorConfig) -> OmicsMatrix:
    """A deterministic location/scale batch harmonizer with protected covariates.

    This Python-native baseline follows ComBat's core location/scale idea but does not
    claim empirical-Bayes shrinkage. The precise implementation is recorded in outputs.
    """
    if not config.variables.technical:
        return no_correction(matrix)
    batch_name = next(
        (v for v in config.variables.technical if not pd.api.types.is_numeric_dtype(metadata[v])),
        None,
    )
    if batch_name is None:
        return residualize(matrix, metadata, config)
    values = matrix.values.copy()
    medians = np.nanmedian(values, axis=0)
    filled = np.where(np.isnan(values), medians, values)
    x_bio, _ = encoded_design(
        metadata, list(dict.fromkeys(config.variables.biological + config.variables.protected))
    )
    bio_fit = x_bio @ np.linalg.lstsq(x_bio, filled, rcond=None)[0]
    residual = filled - bio_fit
    pooled_mean = residual.mean(axis=0)
    pooled_sd = np.maximum(residual.std(axis=0, ddof=1), 1e-8)
    corrected = residual.copy()
    for level in metadata[batch_name].astype(str).unique():
        rows = metadata[batch_name].astype(str).to_numpy() == level
        batch = residual[rows]
        batch_sd = np.maximum(batch.std(axis=0, ddof=1), 1e-8)
        corrected[rows] = (batch - batch.mean(axis=0)) / batch_sd * pooled_sd + pooled_mean
    return _restore(matrix, corrected + bio_fit)


METHODS = {"none": no_correction, "residualize": residualize, "combat": combat}


def apply_corrections(
    matrices: dict[str, OmicsMatrix],
    metadata: pd.DataFrame,
    config: ArtifactorConfig,
    eligible: bool,
) -> tuple[dict[str, dict[str, OmicsMatrix]], dict[str, str]]:
    output: dict[str, dict[str, OmicsMatrix]] = {}
    statuses: dict[str, str] = {}
    for method in config.corrections.methods:
        if method != "none" and not eligible:
            statuses[method] = "ineligible: design audit refused correction"
            continue
        output[method] = {}
        for name, matrix in matrices.items():
            if method == "none":
                output[method][name] = no_correction(matrix)
            elif method == "residualize":
                output[method][name] = residualize(matrix, metadata, config)
            else:
                output[method][name] = combat(matrix, metadata, config)
        statuses[method] = "eligible"
    return output, statuses
