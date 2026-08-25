"""Feature Engineering endpoints.

NOT IMPLEMENTED: these endpoints previously returned random statistics
regardless of submitted data. Real feature-transform execution against
uploaded datasets is planned (ROADMAP P2). The handlers below are honest
501s / previews of the transform vocabulary only.
"""

from typing import List

from app.schemas import (
    FeatureExtractRequest,
    FeaturePreviewResponse,
    TransformStep,
)
from fastapi import APIRouter, HTTPException, status

router = APIRouter()

_NOT_IMPLEMENTED_DETAIL = (
    "Feature extraction is not implemented yet; this endpoint no longer "
    "returns simulated statistics."
)

_SAMPLE_PIPELINE: List[TransformStep] = [
    TransformStep(name="impute_median", type="imputer", params={"strategy": "median"}),
    TransformStep(name="scale_standard", type="scaler", params={"method": "standard"}),
    TransformStep(name="encode_onehot", type="encoder", params={"method": "onehot"}),
]


@router.post("/extract")
async def extract_features(request: FeatureExtractRequest):
    """Apply feature transforms and return before/after stats (501)."""
    if not request.data and not request.pipeline_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pipeline_id or data required",
        )
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_DETAIL)


@router.get("/preview/{pipeline_id}", response_model=FeaturePreviewResponse)
async def preview_features(pipeline_id: str) -> FeaturePreviewResponse:
    """Preview the feature transform pipeline definition (no fake stats)."""
    return FeaturePreviewResponse(
        pipeline_id=pipeline_id,
        pipeline=_SAMPLE_PIPELINE,
        before=[],
        after=[],
    )
