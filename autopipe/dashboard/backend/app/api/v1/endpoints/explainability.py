"""Explainability endpoints — SHAP and LIME.

NOT IMPLEMENTED: these endpoints previously returned random noise seeded by
`hash(model_id)`. Real SHAP/LIME integration requires resolving a stored
model from the registry and running the `shap`/`lime` packages against
provided data — planned for the correctness phase (ROADMAP P2). The
handlers below are intentionally honest 501s and write nothing.
"""

from typing import Any, Dict, List

from app.schemas import ExplainabilityRequest
from fastapi import APIRouter, HTTPException, status

router = APIRouter()

_NOT_IMPLEMENTED_DETAIL = (
    "Explainability computation is not implemented yet; this endpoint no "
    "longer returns simulated values."
)


def _extract_features(data: List[Dict[str, Any]]) -> List[str]:
    """Extract feature names from a data payload (used to validate input)."""
    if not data:
        return []
    return [k for k in data[0] if isinstance(data[0][k], (int, float))]


@router.post("/shap")
async def compute_shap_values(request: ExplainabilityRequest):
    """Compute SHAP feature importance for a model on given data (501)."""
    if not _extract_features(request.data):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No numeric features found in data payload",
        )
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)


@router.post("/lime")
async def compute_lime_explanation(request: ExplainabilityRequest):
    """Compute LIME feature importance for a model on given data (501)."""
    if not _extract_features(request.data):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No numeric features found in data payload",
        )
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)
