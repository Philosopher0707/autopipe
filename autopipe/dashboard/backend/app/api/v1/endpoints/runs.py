"""Run management endpoints."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ActivityLog, Pipeline, Project, Run, RunStatus, Step
from app.db.session import get_db
from app.executor.registry import cancel_run as signal_cancel
from app.utils.datetime_utils import safe_duration_seconds
from app.schemas import RunResponse, RunUpdate, RunList, TrainingConfigResponse, CheckpointsResponse, CheckpointPromoteRequest
from app.schemas import (
    RunCompareRequest,
    RunCompareResponse,
    RunSummaryForComparison,
    ParameterComparisonRow,
    MetricComparison,
    MetricComparisonRow,
    RunDiffSummary,
)

router = APIRouter()


@router.get("", response_model=RunList)
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pipeline_id: Optional[str] = Query(None, description="Filter by pipeline"),
    status: Optional[str] = Query(None, description="Filter by status"),
    experiment_id: Optional[str] = Query(None, description="Filter by experiment"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    search: Optional[str] = Query(None, description="Search by run ID or pipeline name"),
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
    if project_id:
        query = query.where(Run.project_id == project_id)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            Run.id.ilike(search_filter) | Pipeline.name.ilike(search_filter)
        )
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Run.created_at.desc())
    
    result = await db.execute(query)
    runs = result.scalars().unique().all()
    
    # Get pipeline names
    pipeline_ids = set(r.pipeline_id for r in runs)
    pipeline_result = await db.execute(
        select(Pipeline.id, Pipeline.name).where(Pipeline.id.in_(pipeline_ids))
    )
    pipeline_names = {id: name for id, name in pipeline_result.fetchall()}

    # Get project names
    project_ids = set(r.project_id for r in runs if r.project_id)
    project_names = {}
    if project_ids:
        project_result = await db.execute(
            select(Project.id, Project.name).where(Project.id.in_(project_ids))
        )
        project_names = {id: name for id, name in project_result.fetchall()}

    items = []
    for r in runs:
        run_dict = {
            "id": r.id,
            "pipeline_id": r.pipeline_id,
            "status": r.status.value if hasattr(r.status, 'value') else r.status,
            "run_number": r.run_number,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "duration_seconds": r.duration_seconds,
            "metrics": r.metrics,
            "error_message": r.error_message,
            "created_by": r.created_by,
            "created_at": r.created_at,
            "pipeline_name": pipeline_names.get(r.pipeline_id, "Unknown"),
            "project_id": r.project_id,
            "project_name": project_names.get(r.project_id) if r.project_id else None,
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
        project_id=run.project_id,
        status=run.status,
        run_number=run.run_number,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        metrics=run.metrics,
        error_message=run.error_message,
        created_by=run.created_by,
        created_at=run.created_at,
        pipeline_name=pipeline.name if pipeline else "Unknown",
    )


@router.get("/{run_id}/config", response_model=TrainingConfigResponse)
async def get_run_config(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get structured training config for a run."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    cfg = run.config or {}
    return TrainingConfigResponse(
        run_id=run.id,
        architecture=cfg.get("architecture"),
        optimizer=cfg.get("optimizer"),
        learning_rate=cfg.get("learning_rate"),
        weight_decay=cfg.get("weight_decay"),
        batch_size=cfg.get("batch_size"),
        epochs=cfg.get("epochs"),
        early_stopping=cfg.get("early_stopping"),
        lr_scheduler=cfg.get("lr_scheduler"),
        amp=cfg.get("amp"),
        gradient_clip=cfg.get("gradient_clip"),
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
    
    old_status = run.status.value if hasattr(run.status, "value") else str(run.status)
    
    # Update fields
    if update.status:
        run.status = RunStatus(update.status)
        if update.status == RunStatus.RUNNING and not run.started_at:
            run.started_at = datetime.now(timezone.utc)
        if update.status in [RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED]:
            run.completed_at = datetime.now(timezone.utc)
            if run.started_at:
                run.duration_seconds = safe_duration_seconds(run.started_at, run.completed_at)
        # Signal the executor thread to stop if cancelling
        if update.status == RunStatus.CANCELLED.value:
            signal_cancel(run_id)
    
    if update.config is not None:
        run.config = update.config
    
    if update.metrics:
        run.metrics = update.metrics
    
    if update.error_message:
        run.error_message = update.error_message
    
    await db.commit()
    await db.refresh(run)
    
    # Log activity
    if update.status and update.status != old_status:
        activity_action = {
            RunStatus.PENDING.value: "run_pending",
            RunStatus.RUNNING.value: "run_started",
            RunStatus.SUCCESS.value: "run_completed",
            RunStatus.FAILED.value: "run_failed",
            RunStatus.CANCELLED.value: "run_cancelled",
        }.get(update.status, f"run_{update.status}")

        activity = ActivityLog(
            action=activity_action,
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
        project_id=run.project_id,
        status=run.status,
        run_number=run.run_number,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        metrics=run.metrics,
        error_message=run.error_message,
        created_by=run.created_by,
        created_at=run.created_at,
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


@router.get("/{run_id}/checkpoints", response_model=CheckpointsResponse)
async def get_run_checkpoints(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get saved checkpoints for a run. Returns seeded mock data until checkpoint model is added."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    # Mock checkpoints derived from run config or defaults
    epochs = (run.config or {}).get("epochs", 10) if isinstance(run.config, dict) else 10
    checkpoints = []
    for i in range(1, epochs + 1):
        loss = max(0.01, 1.0 - i * 0.08 + 0.02 * ((-1) ** i))
        acc = min(0.99, 0.5 + i * 0.045)
        checkpoints.append({
            "id": f"ckpt-{run_id[:8]}-{i}",
            "run_id": run_id,
            "epoch": i,
            "val_loss": round(loss, 4),
            "val_accuracy": round(acc, 4),
            "file_path": f"/checkpoints/{run_id[:8]}/epoch_{i}.pt",
            "is_best": i == epochs,
            "restored": False,
            "promoted": False,
            "created_at": run.completed_at,
        })
    return CheckpointsResponse(run_id=run_id, checkpoints=checkpoints)


@router.patch("/{run_id}/checkpoints/{checkpoint_id}", response_model=dict)
async def promote_checkpoint(
    run_id: str,
    checkpoint_id: str,
    body: CheckpointPromoteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Mark a checkpoint as restored or promoted. Stub — returns ack."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")
    return {
        "run_id": run_id,
        "checkpoint_id": checkpoint_id,
        "restored": body.restored,
        "promoted": body.promoted,
    }


@router.post("/compare")
async def compare_multiple_runs(
    request: RunCompareRequest,
    db: AsyncSession = Depends(get_db),
) -> RunCompareResponse:
    """Compare multiple runs side-by-side with parameter and metric diffs.
    
    Accepts 2-10 run IDs and returns a structured comparison including:
    - Run summaries with full config and metrics
    - Parameter rows showing which values differ across runs
    - Metric rows with percentage deltas from baseline (first run)
    - Summary of total differences and best runs per metric
    """
    if len(request.run_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 run IDs required for comparison",
        )
    
    if len(request.run_ids) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 runs can be compared at once",
        )
    
    # Fetch runs with pipeline info
    result = await db.execute(
        select(Run, Pipeline.name.label("pipeline_name"))
        .join(Pipeline, Run.pipeline_id == Pipeline.id)
        .where(Run.id.in_(request.run_ids))
    )
    rows = result.all()
    
    if len(rows) != len(request.run_ids):
        found_ids = {r.Run.id for r in rows}
        missing = set(request.run_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runs not found: {missing}",
        )
    
    # Build run map preserving input order
    run_map: Dict[str, Run] = {}
    pipeline_names: Dict[str, str] = {}
    for row in rows:
        run_map[row.Run.id] = row.Run
        pipeline_names[row.Run.id] = row.pipeline_name
    
    runs_ordered = [run_map[rid] for rid in request.run_ids if rid in run_map]
    
    # Build run summaries
    run_summaries = [
        RunSummaryForComparison(
            id=r.id,
            run_number=r.run_number,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            pipeline_name=pipeline_names.get(r.id),
            pipeline_id=r.pipeline_id,
            experiment_id=r.experiment_id,
            created_at=r.created_at,
            started_at=r.started_at,
            completed_at=r.completed_at,
            duration_seconds=r.duration_seconds,
            config=r.config or {},
            metrics=r.metrics or {},
        )
        for r in runs_ordered
    ]
    
    # Build parameter comparison rows
    all_param_keys: set[str] = set()
    for r in runs_ordered:
        all_param_keys.update((r.config or {}).keys())
    
    param_rows: List[ParameterComparisonRow] = []
    for key in sorted(all_param_keys):
        values: Dict[str, Optional[Any]] = {}
        vals_seen: set = set()
        for r in runs_ordered:
            val = (r.config or {}).get(key)
            values[r.id] = val
            # Use string representation for comparison
            try:
                vals_seen.add(json.dumps(val, sort_keys=True) if isinstance(val, (dict, list)) else str(val))
            except (TypeError, ValueError):
                vals_seen.add(str(val))
        
        param_rows.append(ParameterComparisonRow(
            name=key,
            values=values,
            is_different=len(vals_seen) > 1,
        ))
    
    # Build metric comparison rows
    all_metric_keys: set[str] = set()
    for r in runs_ordered:
        all_metric_keys.update((r.metrics or {}).keys())
    
    # Define which metrics are better when higher (for determining best run)
    higher_is_better_metrics = {
        "accuracy", "precision", "recall", "f1", "f1_score", "f1-score",
        "auc", "roc_auc", "ap", "average_precision", "r2", "r_squared",
        "score", "reward", "return", "sharpe", "win_rate",
    }
    lower_is_better_metrics = {
        "loss", "error", "mse", "rmse", "mae", "mape", "latency", 
        "duration", "time", "cost", "kl_divergence",
    }
    
    metric_rows: list[MetricComparisonRow] = []
    best_metric_per_key: Dict[str, str] = {}
    
    for key in sorted(all_metric_keys):
        values: Dict[str, MetricComparison] = {}
        baseline_value: Optional[float] = None
        
        # Get baseline (first run) value
        baseline_metrics = runs_ordered[0].metrics or {}
        baseline_raw = baseline_metrics.get(key)
        try:
            baseline_value = float(baseline_raw) if baseline_raw is not None else None
        except (ValueError, TypeError):
            baseline_value = None
        
        metric_vals: Dict[str, float] = {}
        for r in runs_ordered:
            raw = (r.metrics or {}).get(key)
            try:
                val = float(raw) if raw is not None else None
            except (ValueError, TypeError):
                val = None
            
            delta = None
            if val is not None and baseline_value is not None and baseline_value != 0:
                delta = ((val - baseline_value) / abs(baseline_value)) * 100
            elif val is not None and baseline_value is not None and baseline_value == 0:
                delta = float('inf') if val > 0 else float('-inf') if val < 0 else 0
            
            values[r.id] = MetricComparison(value=val, delta_from_baseline=delta)
            if val is not None:
                metric_vals[r.id] = val
        
        # Determine if higher is better for this metric
        key_lower = key.lower().replace("-", "_")
        is_higher_better = any(b in key_lower for b in higher_is_better_metrics)
        is_lower_better = any(b in key_lower for b in lower_is_better_metrics)
        higher_is_better = is_higher_better or (not is_lower_better)  # default to higher
        
        # Find best run
        best_run_id: Optional[str] = None
        if metric_vals:
            if higher_is_better:
                best_run_id = max(metric_vals.items(), key=lambda x: x[1])[0]
            else:
                best_run_id = min(metric_vals.items(), key=lambda x: x[1])[0]
            best_metric_per_key[key] = best_run_id
        
        metric_rows.append(MetricComparisonRow(
            name=key,
            values=values,
            best_run_id=best_run_id,
            higher_is_better=higher_is_better,
        ))
    
    # Calculate diff summary
    different_params = sum(1 for p in param_rows if p.is_different)
    
    diff_summary = RunDiffSummary(
        total_params=len(param_rows),
        different_params=different_params,
        total_metrics=len(metric_rows),
        best_metric_per_key=best_metric_per_key,
    )
    
    return RunCompareResponse(
        runs=run_summaries,
        parameters=param_rows,
        metrics=metric_rows,
        diff_summary=diff_summary,
    )
