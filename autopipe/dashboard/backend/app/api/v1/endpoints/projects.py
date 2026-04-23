"""Project management endpoints."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, Run
from app.db.session import get_db
from app.schemas import ProjectCreate, ProjectList, ProjectResponse, ProjectUpdate

router = APIRouter()


def _project_response(
    project: Project,
    run_count: int = 0,
    last_run_at: Optional[datetime] = None,
) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        tags=project.tags,
        starred=project.starred,
        created_at=project.created_at,
        updated_at=project.updated_at,
        created_by=project.created_by,
        run_count=run_count,
        last_run_at=last_run_at,
    )


@router.get("", response_model=ProjectList)
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List projects with filtering and pagination."""
    query = select(Project)

    if search:
        query = query.filter(
            (Project.name.ilike(f"%{search}%")) |
            (Project.description.ilike(f"%{search}%"))
        )

    if status:
        query = query.filter(Project.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    query = query.offset(skip).limit(limit).order_by(Project.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    project_ids = [p.id for p in items]
    run_stats = {}
    if project_ids:
        stats_result = await db.execute(
            select(Run.project_id, func.count(Run.id).label("run_count"), func.max(Run.completed_at).label("last_run_at"))
            .where(Run.project_id.in_(project_ids))
            .group_by(Run.project_id)
        )
        for row in stats_result.all():
            run_stats[row.project_id] = {
                "run_count": row.run_count,
                "last_run_at": row.last_run_at,
            }

    return ProjectList(
        total=total,
        page=(skip // limit) + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit,
        items=[
            _project_response(
                p,
                run_count=run_stats.get(p.id, {}).get("run_count", 0),
                last_run_at=run_stats.get(p.id, {}).get("last_run_at"),
            )
            for p in items
        ],
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    project = Project(
        name=data.name,
        description=data.description,
        status=data.status or "active",
        tags=data.tags,
        starred=data.starred or False,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _project_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stats_result = await db.execute(
        select(func.count(Run.id).label("run_count"), func.max(Run.completed_at).label("last_run_at"))
        .where(Run.project_id == project_id)
    )
    row = stats_result.one_or_none()
    run_count = row.run_count if row else 0
    last_run_at = row.last_run_at if row else None
    return _project_response(project, run_count=run_count, last_run_at=last_run_at)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()
    return None
