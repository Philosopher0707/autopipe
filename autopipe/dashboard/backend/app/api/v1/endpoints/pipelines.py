"""Pipeline management endpoints."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db.models import ActivityLog, Pipeline, Run, RunStatus
from app.db.session import get_db
from app.schemas import PipelineCreate, PipelineList, PipelineResponse, PipelineUpdate, RunResponse
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class TriggerRunRequest(BaseModel):
    """Request body for triggering a pipeline run."""

    config_override: Optional[Dict[str, Any]] = None


router = APIRouter()


def _serialize_run(run: Run, pipeline_name: Optional[str] = None) -> RunResponse:
    """Serialize a pipeline run with the fields used by the frontend."""
    return RunResponse(
        id=run.id,
        pipeline_id=run.pipeline_id,
        experiment_id=run.experiment_id,
        project_id=run.project_id,
        status=run.status,
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


def _serialize_pipeline(pipeline: Pipeline, run_count: int = 0) -> PipelineResponse:
    """Serialize a pipeline with the fields used by the frontend."""
    return PipelineResponse(
        id=pipeline.id,
        name=pipeline.name,
        description=pipeline.description,
        config=pipeline.config,
        tags=pipeline.tags or [],
        project_id=pipeline.project_id,
        config_hash=pipeline.config_hash,
        created_at=pipeline.created_at,
        updated_at=pipeline.updated_at,
        created_by=pipeline.created_by,
        run_count=run_count,
        is_active=pipeline.is_active,
    )


@router.get("", response_model=PipelineList)
async def list_pipelines(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    status: Optional[str] = Query(None, description="Filter by status: active, inactive, all"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    sort_by: str = Query("created_at", description="Sort field: name, created_at, updated_at"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    db: AsyncSession = Depends(get_db),
):
    """List pipelines with filtering and pagination."""

    # Build base query
    query = select(Pipeline)

    # Apply filters
    if status and status != "all":
        query = query.filter(Pipeline.is_active == (status == "active"))

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Pipeline.name.ilike(search_filter)) | (Pipeline.description.ilike(search_filter))
        )

    if tag:
        # Check if tag is in the JSON tags array
        query = query.filter(Pipeline.tags.contains([tag]))

    # Count total with filters
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query)

    # Apply sorting
    sort_field = getattr(Pipeline, sort_by, Pipeline.created_at)
    if sort_order == "desc":
        sort_field = sort_field.desc()
    query = query.order_by(sort_field)

    # Apply pagination
    query = query.offset(skip).limit(limit)

    result = await db.execute(query.options(selectinload(Pipeline.runs)))
    pipelines = result.scalars().all()

    # Convert to response format
    items = []
    for pipeline in pipelines:
        items.append(
            _serialize_pipeline(pipeline, run_count=len(pipeline.runs) if pipeline.runs else 0)
        )

    return PipelineList(
        total=total_count or 0,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
        pages=(total_count or 0) // limit + (1 if (total_count or 0) % limit > 0 else 0),
        items=items,
    )


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline details."""
    result = await db.execute(
        select(Pipeline).where(Pipeline.id == pipeline_id).options(selectinload(Pipeline.runs))
    )
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found",
        )

    return _serialize_pipeline(pipeline, run_count=len(pipeline.runs) if pipeline.runs else 0)


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    pipeline: PipelineCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new pipeline."""
    db_pipeline = Pipeline(
        name=pipeline.name,
        description=pipeline.description,
        config=pipeline.config,
        tags=pipeline.tags,
        config_hash=pipeline.config_hash if hasattr(pipeline, "config_hash") else None,
        project_id=pipeline.project_id if hasattr(pipeline, "project_id") else None,
    )

    db.add(db_pipeline)
    await db.commit()
    await db.refresh(db_pipeline)

    # Log activity
    activity = ActivityLog(
        action="pipeline_created",
        resource_type="pipeline",
        resource_id=db_pipeline.id,
        details={
            "title": f"Pipeline '{pipeline.name}' created",
            "description": pipeline.description or "",
        },
    )
    db.add(activity)
    await db.commit()

    return _serialize_pipeline(db_pipeline, run_count=0)


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    pipeline_update: PipelineUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a pipeline."""
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found",
        )

    # Update fields
    if pipeline_update.description is not None:
        pipeline.description = pipeline_update.description
    if pipeline_update.config is not None:
        pipeline.config = pipeline_update.config
    if pipeline_update.tags is not None:
        pipeline.tags = pipeline_update.tags

    pipeline.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(pipeline)
    run_count = await db.scalar(select(func.count(Run.id)).where(Run.pipeline_id == pipeline_id))

    return _serialize_pipeline(pipeline, run_count=run_count or 0)


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a pipeline."""
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found",
        )

    await db.delete(pipeline)
    await db.commit()

    return None


@router.post("/{pipeline_id}/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def trigger_run(
    pipeline_id: str,
    background_tasks: BackgroundTasks,
    body: TriggerRunRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a new pipeline run."""
    if body is None:
        body = TriggerRunRequest()

    # Check pipeline exists
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found",
        )

    # Get next run number
    result = await db.execute(
        select(func.max(Run.run_number)).where(Run.pipeline_id == pipeline_id)
    )
    max_run = result.scalar() or 0

    run_config = body.config_override or pipeline.config

    # Create run
    run = Run(
        pipeline_id=pipeline_id,
        project_id=pipeline.project_id,
        status=RunStatus.PENDING,
        run_number=max_run + 1,
        config=run_config,
    )

    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Log activity
    activity = ActivityLog(
        action="run_triggered",
        resource_type="run",
        resource_id=run.id,
        details={
            "title": f"Run triggered for pipeline '{pipeline.name}'",
            "description": f"Run #{run.run_number}",
        },
    )
    db.add(activity)
    await db.commit()

    # Execute pipeline in background if config has steps
    if run_config and "steps" in run_config:
        from app.executor.runner import execute_run

        background_tasks.add_task(execute_run, run.id, run_config)

    return _serialize_run(run, pipeline.name)


@router.get("/{pipeline_id}/runs")
async def list_pipeline_runs(
    pipeline_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List runs for a pipeline."""

    # Check pipeline exists
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found",
        )

    # Build query
    query = select(Run).where(Run.pipeline_id == pipeline_id)

    if status:
        query = query.filter(Run.status == status)

    query = query.order_by(Run.created_at.desc())

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Get runs
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    items = []
    for run in runs:
        items.append(_serialize_run(run, pipeline.name))

    return {
        "items": items,
        "total": total or 0,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
        "pages": (total or 0) // limit + (1 if (total or 0) % limit > 0 else 0),
    }
