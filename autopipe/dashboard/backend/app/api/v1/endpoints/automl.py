"""AutoML / Optuna trial endpoints."""

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import (
    AutomlTrialsResponse,
    ParamImportancePoint,
    ParetoFrontPoint,
    PruningHistoryPoint,
    AutomlVisualizationsResponse,
    TrialPoint,
    TrialDetailResponse,
    TrialHistoryPoint,
    TrialHistoryResponse,
)

router = APIRouter()

_SEEDED_RNG = random.Random(42)

_PARAM_NAMES = ["learning_rate", "n_layers", "hidden_size", "dropout", "batch_size", "optimizer"]


def _generate_trial(number: int) -> TrialPoint:
    state = _SEEDED_RNG.choice(["COMPLETE", "COMPLETE", "COMPLETE", "PRUNED", "FAIL"])
    started = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return TrialPoint(
        number=number,
        state=state,
        value=round(_SEEDED_RNG.gauss(0.85, 0.08), 4) if state == "COMPLETE" else None,
        params={p: round(_SEEDED_RNG.uniform(0.001, 1.0), 4) for p in _PARAM_NAMES},
        duration_seconds=round(_SEEDED_RNG.uniform(5, 120), 2) if state != "FAIL" else None,
        started_at=started,
        completed_at=started if state != "FAIL" else None,
    )


_TRIALS_CACHE: Optional[List[TrialPoint]] = None


def _get_trials() -> List[TrialPoint]:
    global _TRIALS_CACHE
    if _TRIALS_CACHE is None:
        _TRIALS_CACHE = [_generate_trial(i) for i in range(50)]
    return _TRIALS_CACHE


@router.get("", response_model=AutomlTrialsResponse)
async def list_trials(
    experiment_id: str = Query("default", description="Experiment ID"),
    state: Optional[str] = Query(None, description="Filter by trial state"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
) -> AutomlTrialsResponse:
    """List Optuna trial records."""
    trials = _get_trials()
    if state:
        trials = [t for t in trials if t.state == state.upper()]
    return AutomlTrialsResponse(
        experiment_id=experiment_id,
        trials=trials[:limit],
    )


@router.get("/{trial_id}", response_model=TrialDetailResponse)
async def get_trial(trial_id: int) -> TrialDetailResponse:
    """Get a single trial by number."""
    trials = _get_trials()
    if trial_id < 0 or trial_id >= len(trials):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    return TrialDetailResponse(trial=trials[trial_id])


@router.get("/{trial_id}/history", response_model=TrialHistoryResponse)
async def get_trial_history(trial_id: int) -> TrialHistoryResponse:
    """Get optimization history for a trial."""
    trials = _get_trials()
    if trial_id < 0 or trial_id >= len(trials):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found",
        )
    rng = random.Random(trial_id)
    history = [
        TrialHistoryPoint(
            step=step,
            value=round(rng.gauss(0.5, 0.15), 4),
            timestamp=datetime(2026, 1, 1, 0, step, 0, tzinfo=timezone.utc),
        )
        for step in range(1, 11)
    ]
    return TrialHistoryResponse(trial_id=str(trial_id), history=history)