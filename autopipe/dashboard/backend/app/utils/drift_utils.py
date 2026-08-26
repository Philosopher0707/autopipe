"""Shared drift normalization utilities."""

from typing import Any, Dict, Optional


def normalize_feature_drifts(
    feature_drifts: Optional[Dict[str, Any]],
    default_threshold: float = 0.05,
) -> Dict[str, Dict[str, Any]]:
    """Normalize drift details into a stable, frontend-friendly shape."""
    normalized: Dict[str, Dict[str, Any]] = {}

    for feature_name, raw_value in (feature_drifts or {}).items():
        if isinstance(raw_value, dict):
            threshold = float(raw_value.get("threshold", default_threshold))

            # Verdict precedence: the detector's own decision wins. Core's
            # DriftReport.to_dict() stores `drift_detected`; older payloads
            # may carry `is_drifted`. Only when neither was stored do we
            # re-derive from p_value/score so legacy rows keep rendering.
            is_drifted = raw_value.get("drift_detected", raw_value.get("is_drifted"))
            p_value = raw_value.get("p_value")
            metric_value = raw_value.get("metric_value")
            drift_score = raw_value.get("drift_score")
            if drift_score is None and metric_value is not None:
                drift_score = float(metric_value)
            if drift_score is None and p_value is not None:
                drift_score = max(0.0, min(1.0, 1.0 - float(p_value)))
            drift_score = float(drift_score or 0.0)

            if is_drifted is None:
                if p_value is not None:
                    is_drifted = float(p_value) < threshold
                else:
                    is_drifted = drift_score > threshold

            normalized[feature_name] = {
                "drift_score": drift_score,
                "p_value": float(p_value) if p_value is not None else None,
                "threshold": threshold,
                "is_drifted": bool(is_drifted),
                "test_type": raw_value.get("test_type", raw_value.get("metric_name", "psi")),
            }
            continue

        drift_score = float(raw_value)
        normalized[feature_name] = {
            "drift_score": drift_score,
            "p_value": None,
            "threshold": default_threshold,
            "is_drifted": drift_score > default_threshold,
            "test_type": "psi",
        }

    return normalized


def count_drifted_features(feature_drifts: Optional[Dict[str, Any]]) -> int:
    """Count drifted features using the same interpretation as rendering.

    Single source of truth: this delegates to normalize_feature_drifts()
    instead of re-deriving verdicts with its own thresholds (the previous
    private copy in dashboard.py used a different score fallback).
    """
    return sum(
        1 for stats in normalize_feature_drifts(feature_drifts).values() if stats["is_drifted"]
    )
