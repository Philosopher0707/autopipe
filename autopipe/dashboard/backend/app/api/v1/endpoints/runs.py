"""Run management endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Run, Step, RunStatus, StepStatus, Pipeline, ActivityLog
from app.db.session import get_db
from app.schemas import RunResponse, RunUpdate, RunList

router = APIRouter()


@router.get("", response_model=RunList)
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pipeline_id: Optional[str] = Query(None, description="Filter by pipeline"),
    status: Optional[str] = Query(None, description="Filter by status"),
    experiment_id: Optional[str] = Query(None, description="Filter by experiment"),
    db: AsyncSession = Depends(get_db),
):
    """List runs with pagination and filtering."""
    
    # Build base query
    query = select(Run).join(Pipeline, Run.pipeline_id == Pipeline.id)
    
    # Apply filters
    if pipeline_id:
        query = query.where(Run.pipeline_id == pipeline_id)
    if status:
        query = query.where(Run.status == status)
    if experiment_id:
        query = query.where(Run.experiment_id == experiment_id)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Run.created_at.desc())
    
    result = await db.execute(query.options(selectinload(Run.steps)))
    runs = result.scalars().unique().all()
    
    # Get pipeline names
    pipeline_ids = set(r.pipeline_id for r in runs)
    pipeline_result = await db.execute(
        select(Pipeline.id, Pipeline.name).where(Pipeline.id.in_(pipeline_ids))
    )
    pipeline_names = {id: name for id, name in pipeline_result.fetchall()}
    
    items = []
    for r in runs:
        run_dict = {
            "id": r.id,
            "pipeline_id": r.pipeline_id,
            "status": r.status.value if hasattr(r.status, 'value') else r.status,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "duration_seconds": r.duration_seconds,
            "metrics": r.metrics,
            "error_message": r.error_message,
            "created_by": r.created_by,
            "pipeline_name": pipeline_names.get(r.pipeline_id, "Unknown"),
        }
        items.append(run_dict)
    
    return RunList(
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=(total or 0) // page_size + (1 if (total or 0) % page_size else 0),
        items=items,
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get run details including steps."""
    result = await db.execute(
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.steps))
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    
    # Get pipeline name
    pipe_result = await db.execute(select(Pipeline).where(Pipeline.id == run.pipeline_id))
    pipeline = pipe_result.scalar_one_or_none()
    
    return RunResponse(
        id=run.id,
        pipeline_id=run.pipeline_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        metrics=run.metrics,
        error_message=run.error_message,
        created_by=run.created_by,
        pipeline_name=pipeline.name if pipeline else "Unknown",
    )


@router.patch("/{run_id}", response_model=RunResponse)
async def update_run(
    run_id: str,
    update: RunUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update run status and metrics."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    
    old_status = run.status
    
    # Update fields
    if update.status:
        run.status = update.status
        if update.status == RunStatus.RUNNING and not run.started_at:
            run.started_at = datetime.utcnow()
        if update.status in [RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED]:
            run.completed_at = datetime.utcnow()
            if run.started_at:
                run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
    
    if update.metrics:
        run.metrics = update.metrics
    
    if update.error_message:
        run.error_message = update.error_message
    
    await db.commit()
    await db.refresh(run)
    
    # Log activity
    if update.status and update.status != old_status:
        activity = ActivityLog(
            action=f"run_{update.status}",
            resource_type="run",
            resource_id=run_id,
            details={
                "title": f"Run {run_id} {update.status}",
                "old_status": old_status,
                "new_status": update.status,
            },
        )
        db.add(activity)
        await db.commit()
    
    # Get pipeline name
    pipe_result = await db.execute(select(Pipeline).where(Pipeline.id == run.pipeline_id))
    pipeline = pipe_result.scalar_one_or_none()
    
    return RunResponse(
        id=run.id,
        pipeline_id=run.pipeline_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        metrics=run.metrics,
        error_message=run.error_message,
        created_by=run.created_by,
        pipeline_name=pipeline.name if pipeline else "Unknown",
    )


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a run."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    
    await db.delete(run)
    await db.commit()
    
    return None


@router.get("/{run_id}/logs")
async def get_run_logs(
    run_id: str,
    tail: int = Query(100, ge=1, le=1000, description="Number of recent lines"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    db: AsyncSession = Depends(get_db),
):
    """Get run logs."""
    # Check run exists
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    
    # Get step logs from database
    result = await db.execute(
        select(Step).where(Step.run_id == run_id).order_by(Step.created_at.desc())
    )
    steps = result.scalars().all()
    
    logs = []
    for step in steps:
        if step.logs:
            step_logs = step.logs.split('\n')
            for log_line in step_logs:
                if level and level.upper() not in log_line:
                    continue
                logs.append({
                    "step": step.name,
                    "level": "INFO",  # Parse from log line if structured
                    "message": log_line,
                    "timestamp": step.started_at.isoformat() if step.started_at else None,
                })
    
    # Return last N logs
    return {"logs": logs[-tail:]}


@router.get("/{run_id}/steps")
async def get_run_steps(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get steps for a run."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    
    result = await db.execute(
        select(Step).where(Step.run_id == run_id).order_by(Step.order_index)
    )
    steps = result.scalars().all()
    
    return {
        "items": [
            {
                "id": s.id,
                "run_id": s.run_id,
                "name": s.name,
                "step_type": s.step_type,
                "status": s.status.value if hasattr(s.status, 'value') else s.status,
                "started_at": s.started_at,
                "completed_at": s.completed_at,
                "duration_seconds": s.duration_seconds,
                "metrics": s.metrics,
                "order_index": s.order_index,
            }
            for s in steps
        ]
    }


@router.post("/{run_id}/steps/{step_id}/logs")
async def add_step_log(
    run_id: str,
    step_id: str,
    log_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """Add a log entry to a step (for streaming logs)."""
    result = await db.execute(
        select(Step).where(Step.id == step_id).where(Step.run_id == run_id)
    )
    step = result.scalar_one_or_none()
    
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step {step_id} not found in run {run_id}",
        )
    
    # Append log line
    log_line = log_data.get("message", "")
    if step.logs:
        step.logs = step.logs + "\n" + log_line
    else:
        step.logs = log_line
    
    await db.commit()
    
    return {"message": "Log added"}


@router.get("/{run_id}/compare/{other_run_id}")
async def compare_runs(
    run_id: str,
    other_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Compare two runs."""
    # Get both runs
    result = await db.execute(select(Run).where(Run.id.in_([run_id, other_run_id])))
    runs = result.scalars().all()
    
    if len(runs) != 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both runs not found",
        )
    
    run_a, run_b = runs if runs[0].id == run_id else (runs[1], runs[0])
    
    # Compare metrics
    metrics_a = run_a.metrics or {}
    metrics_b = run_b.metrics or {}
    
    all_metrics = set(metrics_a.keys()) | set(metrics_b.keys())
    comparison = {
        "run_a_id": run_id,
        "run_b_id": other_run_id,
        "run_a_status": run_a.status,
        "run_b_status": run_b.status,
        "run_a_duration": run_a.duration_seconds,
        "run_b_duration": run_b.duration_seconds,
        "metric_comparison": {
            metric: {
                "a": metrics_a.get(metric),
                "b": metrics_b.get(metric),
                "diff": (metrics_b.get(metric, 0) - metrics_a.get(metric, 0)) 
                        if metrics_a.get(metric) is not None and metrics_b.get(metric) is not None 
                        else None,
            }
            for metric in all_metrics
        },
    }
    
    return comparison