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
            p_value = raw_value.get("p_value")
            drift_score = raw_value.get("drift_score")
            if drift_score is None and p_value is not None:
                drift_score = max(0.0, min(1.0, 1.0 - float(p_value)))
            drift_score = float(drift_score or 0.0)

            is_drifted = raw_value.get("is_drifted")
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
                "test_type": raw_value.get("test_type", "psi"),
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
