"""Experiments endpoints."""

from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Experiment, Run, Pipeline
from app.db.session import get_db
from app.schemas import (
    ExperimentCreate, ExperimentUpdate, ExperimentResponse, ExperimentList,
    RunCreate, RunResponse,
)

router = APIRouter()


@router.get("", response_model=ExperimentList)
async def list_experiments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    db: AsyncSession = Depends(get_db),
):
    """List all experiments with pagination."""
    
    count_query = select(func.count(Experiment.id))
    query = select(Experiment).options(selectinload(Experiment.runs))
    
    if search:
        count_query = count_query.where(Experiment.name.ilike(f"%{search}%"))
        query = query.where(Experiment.name.ilike(f"%{search}%"))
    
    if tags:
        for tag in tags:
            count_query = count_query.where(Experiment.tags.contains([tag]))
            query = query.where(Experiment.tags.contains([tag]))
    
    total = await db.scalar(count_query)
    
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(desc(Experiment.updated_at))
    
    result = await db.execute(query)
    experiments = result.scalars().unique().all()
    
    # Build response items
    items = []
    for e in experiments:
        exp_dict = e.__dict__.copy()
        exp_dict['run_count'] = len(e.runs) if e.runs else 0
        items.append(ExperimentResponse.model_validate(exp_dict))
    
    return ExperimentList(
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=(total or 0) // page_size + (1 if (total or 0) % page_size else 0),
        items=items,
    )


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    experiment: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new experiment."""
    db_experiment = Experiment(
        name=experiment.name,
        description=experiment.description,
        config=experiment.config,
        tags=experiment.tags,
    )
    db.add(db_experiment)
    await db.commit()
    await db.refresh(db_experiment)
    return db_experiment


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get experiment by ID."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id).options(selectinload(Experiment.runs))
    )
    experiment = result.scalar_one_or_none()
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    exp_dict = experiment.__dict__.copy()
    exp_dict['run_count'] = len(experiment.runs) if experiment.runs else 0
    return ExperimentResponse.model_validate(exp_dict)


@router.patch("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: str,
    update_data: ExperimentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update experiment."""
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    experiment = result.scalar_one_or_none()
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if update_data.description is not None:
        experiment.description = update_data.description
    if update_data.config is not None:
        experiment.config = update_data.config
    if update_data.tags is not None:
        experiment.tags = update_data.tags
    
    await db.commit()
    await db.refresh(experiment)
    return experiment


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete experiment."""
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    experiment = result.scalar_one_or_none()
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    await db.delete(experiment)
    await db.commit()
    return None


@router.get("/{experiment_id}/runs")
async def get_experiment_runs(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all runs for an experiment."""
    result = await db.execute(
        select(Run).where(Run.experiment_id == experiment_id)
        .options(selectinload(Run.pipeline))
        .order_by(desc(Run.created_at))
    )
    runs = result.scalars().unique().all()
    
    return {
        "items": [
            {
                "id": r.id,
                "status": r.status,
                "pipeline_name": r.pipeline.name if r.pipeline else None,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "duration_seconds": r.duration_seconds,
                "metrics": r.metrics,
            }
            for r in runs
        ]
    }


@router.get("/{experiment_id}/compare")
async def compare_experiment_runs(
    experiment_id: str,
    metric: str = Query(..., description="Metric to compare"),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Compare runs in an experiment by a specific metric."""
    result = await db.execute(
        select(Run).where(Run.experiment_id == experiment_id).order_by(desc(Run.created_at)).limit(limit)
    )
    runs = result.scalars().all()
    
    compared_runs = []
    for run in runs:
        run_metrics = run.metrics or {}
        compared_runs.append({
            "id": run.id,
            "metric_value": run_metrics.get(metric),
            "params": run.config,
            "started_at": run.started_at.isoformat() if run.started_at else None,
        })
    
    return {
        "experiment_id": experiment_id,
        "metric": metric,
        "runs": compared_runs,
    }
