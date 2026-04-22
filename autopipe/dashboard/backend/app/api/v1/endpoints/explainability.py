"""Explainability endpoints — SHAP and LIME.

STUB: These endpoints return deterministic mock data based on model_id hashing.
They do NOT call real SHAP/LIME libraries. Replace with actual computation
once integrated with shap/lime Python packages.
"""

import random
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status

from app.schemas import (
    ExplainabilityRequest,
    ShapResponse,
    ShapValuePoint,
    LimeResponse,
    LimeExplanationPoint,
)

router = APIRouter()


def _extract_features(data: List[Dict[str, Any]]) -> List[str]:
    """Extract feature names from data payload."""
    if not data:
        return []
    return [k for k in data[0].keys() if isinstance(data[0][k], (int, float))]


@router.post("/shap", response_model=ShapResponse)
async def compute_shap_values(request: ExplainabilityRequest) -> ShapResponse:
    """Compute SHAP feature importance for a model on given data.

    STUB: Returns deterministic mock SHAP values. Real implementation should
    instantiate shap.Explainer with the model and data.
    # TODO: integrate with actual SHAP computation libraries
    """
    features = _extract_features(request.data)
    if not features:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No numeric features found in data payload",
        )

    rng = random.Random(hash(request.model_id))
    shap_values = [
        ShapValuePoint(
            feature=f,
            value=round(rng.gauss(0, 1), 4),
            impact=round(abs(rng.gauss(0, 1)), 4),
            base_value=round(rng.gauss(0, 0.5), 4),
        )
        for f in features
    ]
    return ShapResponse(model_id=request.model_id, feature_importance=shap_values)


@router.post("/lime", response_model=LimeResponse)
async def compute_lime_explanation(request: ExplainabilityRequest) -> LimeResponse:
    """Compute LIME feature importance for a model on given data.

    STUB: Returns deterministic mock LIME weights. Real implementation should
    instantiate lime.lime_tabular.LimeTabularExplainer with the model and data.
    # TODO: integrate with actual LIME computation libraries
    """
    features = _extract_features(request.data)
    if not features:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No numeric features found in data payload",
        )

    rng = random.Random(hash(request.model_id))
    lime_explanation = [
        LimeExplanationPoint(
            feature=f,
            weight=round(rng.gauss(0, 0.5), 4),
        )
        for f in features
    ]
    return LimeResponse(model_id=request.model_id, feature_importance=lime_explanation)