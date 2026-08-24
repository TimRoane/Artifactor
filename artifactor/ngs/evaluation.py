# mypy: ignore-errors
from __future__ import annotations

import numpy as np
import pandas as pd


def _binary(expected: pd.Series, predicted: pd.Series) -> dict[str, float]:
    tp = int((expected & predicted).sum())
    fp = int((~expected & predicted).sum())
    fn = int((expected & ~predicted).sum())
    tn = int((~expected & ~predicted).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / max(precision + recall, 1e-12),
        "false_positive_rate": fp / max(fp + tn, 1),
        "true_positive_count": tp,
    }


def evaluate_coverage_truth(
    model_results: pd.DataFrame, truth: pd.DataFrame
) -> tuple[dict[str, object], pd.DataFrame]:
    frame = truth.merge(model_results, on="target_id", how="left")
    expected_technical = frame.is_technical | frame.is_mixed
    expected_biological = frame.is_biological | frame.is_mixed
    predicted_technical = frame.classification.isin(["technical", "mixed"])
    predicted_biological = frame.classification.isin(["biological", "mixed"])
    technical = _binary(expected_technical, predicted_technical)
    biological = _binary(expected_biological, predicted_biological)
    fitted = frame.model_status == "fit"
    tech_affected = fitted & expected_technical
    bio_affected = fitted & expected_biological
    tech_rmse = (
        float(
            np.sqrt(
                np.mean(
                    (
                        frame.loc[tech_affected, "technical_effect"]
                        - frame.loc[tech_affected, "technical_effect_size"]
                    )
                    ** 2
                )
            )
        )
        if tech_affected.any()
        else None
    )
    bio_rmse = (
        float(
            np.sqrt(
                np.mean(
                    (
                        frame.loc[bio_affected, "biological_effect"]
                        - frame.loc[bio_affected, "biological_effect_size"]
                    )
                    ** 2
                )
            )
        )
        if bio_affected.any()
        else None
    )
    summary = {
        "schema_version": "3.0",
        "supplied": True,
        "truth_source": "simulator",
        "technical_target_precision": technical["precision"],
        "technical_target_recall": technical["recall"],
        "technical_target_f1": technical["f1"],
        "biological_target_precision": biological["precision"],
        "biological_target_recall": biological["recall"],
        "biological_target_f1": biological["f1"],
        "null_false_positive_rate": float(
            ((predicted_technical | predicted_biological) & frame.is_null).sum()
            / max(int(frame.is_null.sum()), 1)
        ),
        "technical_effect_rmse": tech_rmse,
        "biological_effect_rmse": bio_rmse,
        "model_fit_fraction": float(fitted.mean()),
    }
    return summary, frame


def evaluate_variant_truth(
    callable_status: pd.DataFrame,
    annotations: pd.DataFrame,
    manifest: pd.DataFrame,
    truth: pd.DataFrame,
    low_vaf_threshold: float,
    minimum_alt_count: int,
) -> tuple[dict[str, object], pd.DataFrame]:
    frame = (
        truth.merge(callable_status, on=["sample_id", "variant_id"], how="left")
        .merge(annotations[["variant_id", "variant_class"]], on="variant_id", how="left")
        .merge(manifest[["sample_id", "ffpe_status"]], on="sample_id", how="left")
    )
    expected_artifact = frame.artifact_state == "artifact"
    predicted_artifact = (
        frame.variant_class.isin(["C>T", "G>A"])
        & (frame.ffpe_status.astype(str).str.upper() == "FFPE")
        & (frame.alt_count >= minimum_alt_count)
        & (frame.observed_vaf <= low_vaf_threshold)
        & (frame.callability_status == "callable")
    )
    artifact = _binary(expected_artifact, predicted_artifact)
    expected_event = frame.truth_state == "positive"
    predicted_event = frame.existing_call_state == "called"
    event = _binary(expected_event, predicted_event)
    null_rows = (frame.truth_state != "positive") & (frame.artifact_state != "artifact")
    null_false_event_rate = float(
        (predicted_event & null_rows).sum() / max(int(null_rows.sum()), 1)
    )
    callable_accuracy = float(
        ((frame.callability_status == "callable") == frame.expected_callable.astype(bool)).mean()
    )
    summary = {
        "schema_version": "3.0",
        "supplied": True,
        "truth_source": "simulator",
        "artifact_event_precision": artifact["precision"],
        "artifact_event_recall": artifact["recall"],
        "artifact_event_f1": artifact["f1"],
        "true_event_precision": event["precision"],
        "true_event_recall": event["recall"],
        "null_false_event_rate": null_false_event_rate,
        "callability_classification_accuracy": callable_accuracy,
        "original_calls_changed": False,
    }
    frame["predicted_artifact"] = predicted_artifact
    return summary, frame
