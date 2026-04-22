"""Feature Engineering endpoints."""

import random
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from app.schemas import (
    FeatureExtractRequest,
    FeatureExtractResponse,
    FeaturePreviewResponse,
    FeatureStats,
    TransformStep,
)

router = APIRouter()

_FEATURES = [
    "age", "income", "score", "tenure", "balance",
    "transactions", "credit_score", "debt_ratio",
]

_SAMPLE_PIPELINE: List[TransformStep] = [
    TransformStep(name="impute_median", type="imputer", params={"strategy": "median"}),
    TransformStep(name="scale_standard", type="scaler", params={"method": "standard"}),
    TransformStep(name="encode_onehot", type="encoder", params={"method": "onehot"}),
]


def _make_stats(rng: random.Random, prefix: str = "") -> List[FeatureStats]:
    stats = []
    for f in _FEATURES:
        stats.append(FeatureStats(
            name=f"{prefix}{f}" if prefix else f,
            dtype=rng.choice(["float64", "int64"]),
            nulls=rng.randint(0, 50),
            mean=round(rng.gauss(50, 20), 2),
            std=round(rng.gauss(15, 5), 2),
            min=round(rng.uniform(0, 10), 2),
            max=round(rng.uniform(90, 100), 2),
            unique=rng.randint(10, 500),
        ))
    return stats


@router.post("/extract", response_model=FeatureExtractResponse)
async def extract_features(request: FeatureExtractRequest) -> FeatureExtractResponse:
    """Apply feature transforms and return before/after stats."""
    if not request.data and not request.pipeline_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pipeline_id or data required",
        )

    rng = random.Random(hash(request.pipeline_id))
    before = _make_stats(rng)
    after = _make_stats(rng, prefix="transformed_")
    sample_keys = rng.sample(_FEATURES, 4)
    sample_values = {
        k: [round(rng.gauss(50, 20), 2) for _ in range(5)]
        for k in sample_keys
    }
    return FeatureExtractResponse(
        pipeline_id=request.pipeline_id,
        before_count=len(_FEATURES),
        after_count=len(_FEATURES) + 3,
        before=before,
        after=after,
        sample_values=sample_values,
    )


@router.get("/preview/{pipeline_id}", response_model=FeaturePreviewResponse)
async def preview_features(pipeline_id: str) -> FeaturePreviewResponse:
    """Preview feature transform pipeline stats."""
    rng = random.Random(hash(pipeline_id))
    return FeaturePreviewResponse(
        pipeline_id=pipeline_id,
        pipeline=_SAMPLE_PIPELINE,
        before=_make_stats(rng),
        after=_make_stats(rng, prefix="transformed_"),
    )