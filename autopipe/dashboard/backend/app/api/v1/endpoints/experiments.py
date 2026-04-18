"""Experiments endpoints."""

import random
import uuid
import itertools
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Experiment, Pipeline, Run, RunStatus, Step, StepStatus
from app.db.session import get_db
from app.schemas import (
    ExperimentCreate, ExperimentUpdate, ExperimentResponse, ExperimentList,
    TrialLaunchRequest, TrialLaunchResponse, RunResponse,
)

router = APIRouter()


def _derive_experiment_status(runs: list[Run]) -> str:
    """Derive an experiment status from its runs."""
    statuses = {
        run.status.value if hasattr(run.status, "value") else str(run.status)
        for run in runs
    }
    if not statuses:
        return "pending"
    if RunStatus.RUNNING.value in statuses or RunStatus.PENDING.value in statuses:
        return "running"
    if RunStatus.SUCCESS.value in statuses:
        return "completed"
    if RunStatus.FAILED.value in statuses or RunStatus.CANCELLED.value in statuses:
        return "failed"
    return "pending"


def _serialize_experiment(experiment: Experiment) -> ExperimentResponse:
    """Serialize an experiment with derived status and run count."""
    exp_dict = experiment.__dict__.copy()
    exp_dict["run_count"] = len(experiment.runs) if experiment.runs else 0
    exp_dict["status"] = _derive_experiment_status(experiment.runs or [])
    return ExperimentResponse.model_validate(exp_dict)


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
    
    items = [_serialize_experiment(experiment) for experiment in experiments]
    
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
    return ExperimentResponse.model_validate(
        {
            "id": db_experiment.id,
            "name": db_experiment.name,
            "description": db_experiment.description,
            "config": db_experiment.config,
            "tags": db_experiment.tags,
            "created_at": db_experiment.created_at,
            "updated_at": db_experiment.updated_at,
            "created_by": db_experiment.created_by,
            "best_run_id": db_experiment.best_run_id,
            "best_metric": db_experiment.best_metric,
            "metric_name": db_experiment.metric_name,
            "run_count": 0,
            "status": "pending",
        }
    )


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
    
    return _serialize_experiment(experiment)


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
    refreshed = await db.execute(
        select(Experiment)
        .where(Experiment.id == experiment_id)
        .options(selectinload(Experiment.runs))
    )
    updated_experiment = refreshed.scalar_one()
    return _serialize_experiment(updated_experiment)


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
                "pipeline_id": r.pipeline_id,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
                "run_number": r.run_number,
                "pipeline_name": r.pipeline.name if r.pipeline else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "duration_seconds": r.duration_seconds,
                "metrics": r.metrics,
                "error_message": r.error_message,
                "config": r.config,
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


def _random_configs(search_space: dict, n_trials: int) -> list[dict]:
    """Generate random parameter combinations from a search space."""
    configs = []
    for _ in range(n_trials):
        config = {}
        for param, spec in search_space.items():
            if not isinstance(spec, dict):
                continue
            ptype = spec.get("type", "float")
            if ptype == "int":
                config[param] = random.randint(spec["low"], spec["high"])
            elif ptype == "float":
                config[param] = round(random.uniform(spec["low"], spec["high"]), 4)
            elif ptype == "categorical":
                config[param] = random.choice(spec["values"])
        configs.append(config)
    return configs


def _grid_configs(search_space: dict, max_trials: int) -> list[dict]:
    """Generate grid parameter combinations from a search space."""
    param_values = {}
    for param, spec in search_space.items():
        if not isinstance(spec, dict):
            continue
        ptype = spec.get("type", "float")
        if ptype == "int":
            step = max(1, (spec["high"] - spec["low"]) // min(5, max_trials))
            values = list(range(spec["low"], spec["high"] + 1, step))
            if values[-1] < spec["high"]:
                values.append(spec["high"])
            param_values[param] = values
        elif ptype == "float":
            n_points = min(5, max_trials) + 1
            step = (spec["high"] - spec["low"]) / (n_points - 1)
            param_values[param] = [round(spec["low"] + i * step, 4) for i in range(n_points)]
        elif ptype == "categorical":
            param_values[param] = spec["values"]
    combos = list(itertools.product(*param_values.values()))
    combos = combos[:max_trials]
    return [dict(zip(param_values.keys(), combo)) for combo in combos]


def _generate_trial_configs(search_space: dict | None, strategy: str, n_trials: int) -> list[dict]:
    """Generate trial configs from a search space using the given strategy."""
    if not search_space:
        return [{} for _ in range(n_trials)]
    if strategy == "grid":
        return _grid_configs(search_space, n_trials)
    return _random_configs(search_space, n_trials)


STEP_NAMES = ["load_data", "preprocess", "train", "evaluate", "save"]


def _generate_metrics(search_space: dict | None, metric_name: str | None) -> dict:
    """Generate plausible run metrics based on search space or defaults."""
    base = round(random.uniform(0.82, 0.97), 4)
    return {
        metric_name or "accuracy": base,
        "f1": round(base - random.uniform(0.01, 0.05), 4),
        "precision": round(base - random.uniform(0.01, 0.04), 4),
        "recall": round(base - random.uniform(0.01, 0.06), 4),
    }


def _simulate_run(run: Run, search_space: dict | None, metric_name: str | None) -> None:
    """Simulate execution of a trial run: advance status, set timestamps, generate metrics."""
    is_failed = random.random() < 0.15
    started = datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 30), seconds=random.randint(0, 59))
    duration = random.uniform(60, 600)

    run.started_at = started
    run.completed_at = started + timedelta(seconds=duration)
    run.duration_seconds = duration

    if is_failed:
        run.status = RunStatus.FAILED
        run.error_message = "Training failed: validation loss diverged"
    else:
        run.status = RunStatus.SUCCESS
        run.metrics = _generate_metrics(search_space, metric_name)


def _create_steps(run: Run) -> list[Step]:
    """Create pipeline steps for a simulated run."""
    is_failed = run.status == RunStatus.FAILED
    started = run.started_at or datetime.now(timezone.utc)
    steps = []

    failed_index = STEP_NAMES.index("train") if is_failed else len(STEP_NAMES)
    for i, step_name in enumerate(STEP_NAMES):
        if is_failed and step_name == "train":
            step_status = StepStatus.FAILED
        elif i > failed_index:
            step_status = StepStatus.SKIPPED
        else:
            step_status = StepStatus.SUCCESS
        step_started = started + timedelta(minutes=i * 2)
        step_duration = random.uniform(30, 180)
        is_done = step_status in (StepStatus.SUCCESS, StepStatus.FAILED)
        is_skipped = step_status == StepStatus.SKIPPED
        steps.append(Step(
            id=str(uuid.uuid4()),
            run_id=run.id,
            name=step_name,
            step_type=f"{step_name.title()}Step",
            status=step_status,
            started_at=step_started if not is_skipped else None,
            completed_at=step_started + timedelta(seconds=step_duration) if step_status == StepStatus.SUCCESS else None,
            duration_seconds=step_duration if step_status == StepStatus.SUCCESS else None,
            order_index=i,
            logs=f"[INFO] {step_name}: Processing data...\n[INFO] {step_name}: Done!" if step_status == StepStatus.SUCCESS else (f"[ERROR] {step_name}: Failed" if step_status == StepStatus.FAILED else f"[WARN] {step_name}: Skipped"),
            metrics={"step_metric": round(random.uniform(0.8, 1.0), 3)} if step_status == StepStatus.SUCCESS else None,
        ))

    return steps


def _serialize_run(run: Run, pipeline_name: str | None = None) -> RunResponse:
    """Serialize a Run with optional pipeline name."""
    return RunResponse(
        id=run.id,
        pipeline_id=run.pipeline_id,
        experiment_id=run.experiment_id,
        status=run.status.value if hasattr(run.status, "value") else run.status,
        run_number=run.run_number,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        config=run.config,
        metrics=run.metrics,
        error_message=run.error_message,
        created_by=run.created_by,
        created_at=run.created_at,
        pipeline_name=pipeline_name,
    )


@router.post("/{experiment_id}/trials", response_model=TrialLaunchResponse)
async def launch_trials(
    experiment_id: str,
    body: TrialLaunchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Launch trial runs for an experiment using its search-space config."""
    # Fetch experiment
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id).options(selectinload(Experiment.runs))
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Validate pipeline exists
    pipeline_result = await db.execute(select(Pipeline).where(Pipeline.id == body.pipeline_id))
    pipeline = pipeline_result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Extract search space from experiment config
    config = experiment.config or {}
    search_space = config.get("search_space", config)

    # Generate trial configs
    trial_configs = _generate_trial_configs(search_space, body.strategy, body.n_trials)

    # Get next run number for this experiment
    max_run_result = await db.execute(
        select(func.max(Run.run_number)).where(Run.experiment_id == experiment_id)
    )
    max_run_number = max_run_result.scalar() or 0

    # Create runs
    created_runs = []
    for i, trial_config in enumerate(trial_configs):
        run_config = dict(config)
        run_config.update(trial_config)

        run = Run(
            pipeline_id=body.pipeline_id,
            experiment_id=experiment_id,
            status=RunStatus.PENDING,
            run_number=max_run_number + i + 1,
            config=run_config,
        )
        db.add(run)
        created_runs.append(run)

    await db.commit()
    for run in created_runs:
        await db.refresh(run)

    # Simulate run lifecycle if requested
    if body.simulate:
        metric_name = config.get("metric_name") or experiment.metric_name
        for run in created_runs:
            _simulate_run(run, search_space, metric_name)
            steps = _create_steps(run)
            db.add_all(steps)
        await db.commit()
        for run in created_runs:
            await db.refresh(run)

        # Update experiment best_run_id and best_metric
        best_run = None
        best_value = None
        metric_key = metric_name or "accuracy"
        for run in created_runs:
            if run.status == RunStatus.SUCCESS and run.metrics:
                val = run.metrics.get(metric_key)
                if val is not None and (best_value is None or val > best_value):
                    best_value = val
                    best_run = run
        if best_run:
            experiment.best_run_id = best_run.id
            experiment.best_metric = best_value
            await db.commit()
            await db.refresh(experiment)

    # Execute runs via the pipeline executor if not simulating
    if not body.simulate:
        from app.executor.runner import execute_run
        pipeline_config = pipeline.config or {}
        for run in created_runs:
            if pipeline_config and "steps" in pipeline_config:
                # Pass the pipeline config as-is and trial params as initial_inputs
                # This allows steps to access hyperparameters via their inputs
                run_config = run.config or {}
                skip_keys = {"search_space", "direction", "metric_name", "metric"}
                trial_params = {k: v for k, v in run_config.items() if k not in skip_keys}
                background_tasks.add_task(execute_run, run.id, pipeline_config, trial_params)

    return TrialLaunchResponse(
        experiment_id=experiment_id,
        runs=[_serialize_run(r, pipeline.name) for r in created_runs],
        strategy=body.strategy,
        n_trials=len(created_runs),
    )
