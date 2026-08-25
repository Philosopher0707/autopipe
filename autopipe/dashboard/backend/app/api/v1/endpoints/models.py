"""Model Registry endpoints."""

from datetime import datetime, timezone
from typing import Optional

from app.db.models import Model, ModelStage, ModelVersion
from app.db.session import get_db
from app.schemas import (
    ModelCreate,
    ModelList,
    ModelPromoteRequest,
    ModelResponse,
    ModelUpdate,
    ModelVersionCreate,
    ModelVersionList,
    ModelVersionResponse,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter()


@router.get("", response_model=ModelList)
async def list_models(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name"),
    framework: Optional[str] = Query(None, description="Filter by framework"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    stage: Optional[str] = Query(
        None, description="Filter by stage: pending, staging, production, archived"
    ),
    db: AsyncSession = Depends(get_db),
):
    """List all registered models."""

    count_query = select(func.count(Model.id))
    query = select(Model).options(selectinload(Model.versions))

    if search:
        count_query = count_query.where(Model.name.ilike(f"%{search}%"))
        query = query.where(Model.name.ilike(f"%{search}%"))

    if framework:
        count_query = count_query.where(Model.framework == framework)
        query = query.where(Model.framework == framework)

    if task_type:
        count_query = count_query.where(Model.task_type == task_type)
        query = query.where(Model.task_type == task_type)

    if tag:
        count_query = count_query.where(Model.tags.contains([tag]))
        query = query.where(Model.tags.contains([tag]))

    if stage:
        count_query = count_query.where(Model.current_stage == stage)
        query = query.where(Model.current_stage == stage)

    total = await db.scalar(count_query)

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(desc(Model.updated_at))

    result = await db.execute(query)
    models = result.scalars().unique().all()

    # Build response
    items = []
    for m in models:
        model_dict = m.__dict__.copy()
        model_dict["version_count"] = len(m.versions) if m.versions else 0
        items.append(ModelResponse.model_validate(model_dict))

    return ModelList(
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=(total or 0) // page_size + (1 if (total or 0) % page_size else 0),
        items=items,
    )


@router.post("", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    model: ModelCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new model."""
    db_model = Model(
        name=model.name,
        description=model.description,
        framework=model.framework,
        task_type=model.task_type,
        signature=model.signature,
        tags=model.tags,
    )
    db.add(db_model)
    await db.commit()
    refreshed = await db.execute(
        select(Model).where(Model.id == db_model.id).options(selectinload(Model.versions))
    )
    db_model = refreshed.scalar_one()
    return ModelResponse(
        id=db_model.id,
        name=db_model.name,
        description=db_model.description,
        framework=db_model.framework,
        task_type=db_model.task_type,
        signature=db_model.signature,
        tags=db_model.tags or [],
        current_stage=db_model.current_stage,
        created_at=db_model.created_at,
        updated_at=db_model.updated_at,
        version_count=len(db_model.versions) if db_model.versions else 0,
        versions=[],
    )


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get model by ID with eager-loaded versions."""
    result = await db.execute(
        select(Model).where(Model.id == model_id).options(selectinload(Model.versions))
    )
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Sort versions by version number descending
    sorted_versions = sorted(model.versions, key=lambda v: v.version, reverse=True)

    # Build response with versions
    model_dict = {
        "id": model.id,
        "name": model.name,
        "description": model.description,
        "framework": model.framework,
        "task_type": model.task_type,
        "current_stage": model.current_stage,
        "signature": model.signature,
        "tags": model.tags,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
        "version_count": len(model.versions) if model.versions else 0,
        "versions": [
            ModelVersionResponse(
                id=v.id,
                model_id=v.model_id,
                version=v.version,
                stage=v.stage,
                description=v.description,
                metrics=v.metrics,
                params=v.params,
                artifact_path=v.artifact_path,
                run_id=v.run_id,
                tags=v.tags,
                created_at=v.created_at,
                transitioned_at=v.transitioned_at,
                model_name=model.name,
            )
            for v in sorted_versions
        ],
    }
    return ModelResponse.model_validate(model_dict)


@router.patch("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: str,
    update_data: ModelUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update model metadata."""
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if update_data.description is not None:
        model.description = update_data.description
    if update_data.tags is not None:
        model.tags = update_data.tags

    await db.commit()
    refreshed = await db.execute(
        select(Model).where(Model.id == model_id).options(selectinload(Model.versions))
    )
    model = refreshed.scalar_one()
    version_count = await db.scalar(
        select(func.count(ModelVersion.id)).where(ModelVersion.model_id == model_id)
    )
    return ModelResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        framework=model.framework,
        task_type=model.task_type,
        signature=model.signature,
        tags=model.tags or [],
        current_stage=model.current_stage,
        created_at=model.created_at,
        updated_at=model.updated_at,
        version_count=version_count or 0,
        versions=[],
    )


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete model and all versions."""
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    await db.delete(model)
    await db.commit()
    return None


# ==================== Model Versions ====================


@router.get("/{model_id}/versions", response_model=ModelVersionList)
async def list_model_versions(
    model_id: str,
    stage: Optional[str] = Query(None, description="Filter by stage"),
    db: AsyncSession = Depends(get_db),
):
    """List all versions of a model."""
    # Verify model exists
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    query = select(ModelVersion).where(ModelVersion.model_id == model_id)

    if stage:
        query = query.where(ModelVersion.stage == stage)

    query = query.order_by(desc(ModelVersion.version))
    result = await db.execute(query)
    versions = result.scalars().all()

    # Add model_name to each
    items = []
    for v in versions:
        ver_dict = v.__dict__.copy()
        ver_dict["model_name"] = model.name
        items.append(ModelVersionResponse.model_validate(ver_dict))

    return ModelVersionList(items=items, total=len(items))


@router.post(
    "/{model_id}/versions", response_model=ModelVersionResponse, status_code=status.HTTP_201_CREATED
)
async def create_model_version(
    model_id: str,
    version: ModelVersionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new model version."""
    # Verify model exists
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Get next version number
    result = await db.execute(
        select(func.max(ModelVersion.version)).where(ModelVersion.model_id == model_id)
    )
    next_version = (result.scalar() or 0) + 1

    db_version = ModelVersion(
        model_id=model_id,
        version=next_version,
        description=version.description,
        metrics=version.metrics,
        params=version.params,
        artifact_path=version.artifact_path,
        run_id=version.run_id,
        tags=version.tags,
        stage=ModelStage.PENDING,
    )
    db.add(db_version)
    await db.commit()
    await db.refresh(db_version)

    # Update model's latest version
    model.latest_version = next_version
    await db.commit()

    ver_dict = db_version.__dict__.copy()
    ver_dict["model_name"] = model.name
    return ModelVersionResponse.model_validate(ver_dict)


@router.get("/{model_id}/versions/{version_number}", response_model=ModelVersionResponse)
async def get_model_version(
    model_id: str,
    version_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Get specific model version."""
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.model_id == model_id)
        .where(ModelVersion.version == version_number)
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    # Get model name
    model_result = await db.execute(select(Model.name).where(Model.id == model_id))
    model_name = model_result.scalar()

    ver_dict = version.__dict__.copy()
    ver_dict["model_name"] = model_name
    return ModelVersionResponse.model_validate(ver_dict)


@router.post("/{model_id}/versions/{version_number}/promote", response_model=ModelVersionResponse)
async def promote_model_version(
    model_id: str,
    version_number: int,
    promote_data: ModelPromoteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Promote a model version to a different stage."""
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.model_id == model_id)
        .where(ModelVersion.version == version_number)
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    # Update stage
    stage_map = {
        "pending": ModelStage.PENDING,
        "staging": ModelStage.STAGING,
        "production": ModelStage.PRODUCTION,
        "archived": ModelStage.ARCHIVED,
    }

    if promote_data.stage not in stage_map:
        raise HTTPException(status_code=400, detail="Invalid stage")

    version.stage = stage_map[promote_data.stage]
    version.transitioned_at = datetime.now(timezone.utc)

    # Update model's current stage if promoted to production
    model_result = await db.execute(select(Model).where(Model.id == model_id))
    model = model_result.scalar_one_or_none()

    if model:
        model.current_stage = version.stage

    await db.commit()
    await db.refresh(version)

    ver_dict = version.__dict__.copy()
    ver_dict["model_name"] = model.name if model else None
    return ModelVersionResponse.model_validate(ver_dict)


@router.post("/{model_id}/compare")
async def compare_model_versions(
    model_id: str,
    version_a: int = Query(..., description="First version to compare"),
    version_b: int = Query(..., description="Second version to compare"),
    db: AsyncSession = Depends(get_db),
):
    """Compare two model versions."""
    # Get both versions
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.model_id == model_id)
        .where(ModelVersion.version.in_([version_a, version_b]))
    )
    versions = result.scalars().all()

    if len(versions) != 2:
        raise HTTPException(status_code=404, detail="One or both versions not found")

    v_a = next((v for v in versions if v.version == version_a), None)
    v_b = next((v for v in versions if v.version == version_b), None)

    # Get model
    model_result = await db.execute(select(Model).where(Model.id == model_id))
    model = model_result.scalar_one_or_none()

    # Calculate differences
    metrics_a = v_a.metrics or {}
    metrics_b = v_b.metrics or {}

    all_keys = set(metrics_a.keys()) | set(metrics_b.keys())
    differences = {}

    for key in all_keys:
        val_a = metrics_a.get(key, None)
        val_b = metrics_b.get(key, None)
        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            diff = val_b - val_a
            pct_diff = (diff / val_a * 100) if val_a != 0 else 0
            differences[key] = {
                f"v{version_a}": val_a,
                f"v{version_b}": val_b,
                "difference": diff,
                "percentage": round(pct_diff, 2),
            }

    primary_metric = "accuracy" if "accuracy" in differences else next(iter(differences), None)
    is_better = False
    if primary_metric is not None:
        is_better = differences[primary_metric]["difference"] > 0

    report_lines = [
        f"Compared model versions v{version_a} and v{version_b}.",
    ]
    for metric, metric_diff in differences.items():
        report_lines.append(
            f"{metric}: {metric_diff[f'v{version_a}']} -> {metric_diff[f'v{version_b}']} "
            f"({metric_diff['percentage']}%)"
        )

    return {
        "model_name": model.name if model else "",
        "version_a": version_a,
        "version_b": version_b,
        "metric_differences": {
            metric: metric_diff["difference"] for metric, metric_diff in differences.items()
        },
        "is_better": is_better,
        "report": "\n".join(report_lines),
    }


@router.get("/{model_id}/download/{version_number}")
async def download_model(
    model_id: str,
    version_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Get download URL for model artifact."""
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.model_id == model_id)
        .where(ModelVersion.version == version_number)
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    # In real implementation, this would generate a signed URL
    return {
        "model_id": model_id,
        "version": version_number,
        "artifact_path": version.artifact_path,
        # "download_url": generate_presigned_url(version.artifact_path),
    }
