"""Chart data endpoints — return JSON shapes for Recharts rendering."""

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.drift import _normalize_feature_drifts
from app.db.models import ChartArtifact, DriftReport, Experiment, Model, ModelVersion, Run, RunStatus, Step
from app.db.session import get_db
from app.schemas import (
    ChartArtifactCreate,
    ChartArtifactList,
    ChartArtifactResponse,
    ChartMetricPoint,
    DriftFeatureScorePoint,
    DriftFeatureScoresResponse,
    DriftTrendPoint,
    DriftTrendResponse,
    ExperimentMetricTraceResponse,
    ModelVersionMetricsResponse,
    RunMetricsOverTimeResponse,
    StepDurationPoint,
    StepDurationsResponse,
)

router = APIRouter()


def _is_numeric(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _top_numeric_keys(items: List[Dict[str, Any]], n: int = 3) -> List[str]:
    """Find the most frequent numeric keys across a list of metric dicts."""
    counter: Counter = Counter()
    for item in items:
        for k, v in (item or {}).items():
            if _is_numeric(v):
                counter[k] += 1
    return [k for k, _ in counter.most_common(n)]


# ---------------------------------------------------------------------------
# GET /charts/run-metrics-over-time
# ---------------------------------------------------------------------------

@router.get("/run-metrics-over-time", response_model=RunMetricsOverTimeResponse)
async def get_run_metrics_over_time(
    metric: str = Query(..., description="Metric key inside Run.metrics"),
    pipeline_id: Optional[str] = Query(None),
    experiment_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Run).where(Run.status == RunStatus.SUCCESS)
    if pipeline_id:
        query = query.where(Run.pipeline_id == pipeline_id)
    if experiment_id:
        query = query.where(Run.experiment_id == experiment_id)
    query = query.order_by(Run.completed_at.desc()).limit(limit)

    result = await db.execute(query)
    runs = result.scalars().all()

    points: List[ChartMetricPoint] = []
    for run in reversed(runs):
        metrics = run.metrics or {}
        if metric in metrics and _is_numeric(metrics[metric]):
            points.append(
                ChartMetricPoint(
                    run_number=run.run_number or 0,
                    value=float(metrics[metric]),
                    completed_at=run.completed_at.isoformat() if run.completed_at else None,
                )
            )

    return RunMetricsOverTimeResponse(metric=metric, points=points)


# ---------------------------------------------------------------------------
# GET /charts/step-durations
# ---------------------------------------------------------------------------

@router.get("/step-durations", response_model=StepDurationsResponse)
async def get_step_durations(
    run_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    query = select(Step).where(Step.run_id == run_id).order_by(Step.order_index)
    result = await db.execute(query)
    steps = result.scalars().all()

    return StepDurationsResponse(
        run_id=run_id,
        steps=[
            StepDurationPoint(
                name=s.name,
                duration_seconds=s.duration_seconds,
                status=s.status.value if hasattr(s.status, "value") else str(s.status),
                order_index=s.order_index,
            )
            for s in steps
        ],
    )


# ---------------------------------------------------------------------------
# GET /charts/experiment-metric-trace
# ---------------------------------------------------------------------------

@router.get("/experiment-metric-trace", response_model=ExperimentMetricTraceResponse)
async def get_experiment_metric_trace(
    experiment_id: str = Query(...),
    metrics: Optional[str] = Query(None, description="Comma-separated metric keys (auto-detect if omitted)"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Run)
        .where(Run.experiment_id == experiment_id, Run.status == RunStatus.SUCCESS)
        .order_by(Run.run_number)
    )
    runs = result.scalars().all()

    if not runs:
        return ExperimentMetricTraceResponse(experiment_id=experiment_id, metrics=[], points=[])

    metric_keys = [m.strip() for m in metrics.split(",")] if metrics else None
    if not metric_keys:
        metric_keys = _top_numeric_keys([r.metrics for r in runs])

    points: List[Dict[str, Any]] = []
    for run in runs:
        row: Dict[str, Any] = {"run_number": run.run_number or 0}
        rm = run.metrics or {}
        for key in metric_keys:
            if key in rm and _is_numeric(rm[key]):
                row[key] = float(rm[key])
        if len(row) > 1:
            points.append(row)

    return ExperimentMetricTraceResponse(experiment_id=experiment_id, metrics=metric_keys, points=points)


# ---------------------------------------------------------------------------
# GET /charts/model-version-metrics
# ---------------------------------------------------------------------------

@router.get("/model-version-metrics", response_model=ModelVersionMetricsResponse)
async def get_model_version_metrics(
    model_id: str = Query(...),
    metrics: Optional[str] = Query(None, description="Comma-separated metric keys (auto-detect if omitted)"),
    db: AsyncSession = Depends(get_db),
):
    model_result = await db.execute(select(Model).where(Model.id == model_id))
    model = model_result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    version_result = await db.execute(
        select(ModelVersion).where(ModelVersion.model_id == model_id).order_by(ModelVersion.version)
    )
    versions = version_result.scalars().all()

    if not versions:
        return ModelVersionMetricsResponse(model_id=model_id, model_name=model.name, metrics=[], points=[])

    metric_keys = [m.strip() for m in metrics.split(",")] if metrics else None
    if not metric_keys:
        metric_keys = _top_numeric_keys([v.metrics for v in versions])

    points: List[Dict[str, Any]] = []
    for v in versions:
        row: Dict[str, Any] = {"version": v.version, "stage": v.stage.value if hasattr(v.stage, "value") else str(v.stage)}
        vm = v.metrics or {}
        for key in metric_keys:
            if key in vm and _is_numeric(vm[key]):
                row[key] = float(vm[key])
        if any(k in row for k in metric_keys):
            points.append(row)

    return ModelVersionMetricsResponse(model_id=model_id, model_name=model.name, metrics=metric_keys, points=points)


# ---------------------------------------------------------------------------
# GET /charts/drift-feature-scores
# ---------------------------------------------------------------------------

@router.get("/drift-feature-scores", response_model=DriftFeatureScoresResponse)
async def get_drift_feature_scores(
    report_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DriftReport).where(DriftReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drift report not found")

    normalized = _normalize_feature_drifts(report.feature_drifts)

    features = [
        DriftFeatureScorePoint(
            name=name,
            drift_score=details["drift_score"],
            threshold=details["threshold"],
            is_drifted=details["is_drifted"],
            test_type=details.get("test_type", "psi"),
        )
        for name, details in normalized.items()
    ]

    return DriftFeatureScoresResponse(
        report_id=report_id,
        drift_detected=report.drift_detected,
        features=features,
    )


# ---------------------------------------------------------------------------
# GET /charts/drift-trend
# ---------------------------------------------------------------------------

@router.get("/drift-trend", response_model=DriftTrendResponse)
async def get_drift_trend(
    model_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = select(DriftReport).where(DriftReport.created_at >= cutoff)
    if model_id:
        query = query.where(DriftReport.model_id == model_id)
    query = query.order_by(DriftReport.created_at)

    result = await db.execute(query)
    reports = result.scalars().all()

    points: List[DriftTrendPoint] = []
    for r in reports:
        normalized = _normalize_feature_drifts(r.feature_drifts)
        features_drifted = sum(1 for d in normalized.values() if d.get("is_drifted"))
        points.append(
            DriftTrendPoint(
                created_at=r.created_at.isoformat(),
                drift_score=r.drift_score,
                drift_detected=r.drift_detected,
                features_drifted=features_drifted,
            )
        )

    return DriftTrendResponse(model_id=model_id, points=points)


# ---------------------------------------------------------------------------
# POST /charts/artifacts
# ---------------------------------------------------------------------------

@router.post("/artifacts", response_model=ChartArtifactResponse, status_code=status.HTTP_201_CREATED)
async def create_chart_artifact(
    body: ChartArtifactCreate,
    db: AsyncSession = Depends(get_db),
):
    artifact = ChartArtifact(**body.model_dump())
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    return artifact


# ---------------------------------------------------------------------------
# GET /charts/artifacts
# ---------------------------------------------------------------------------

@router.get("/artifacts", response_model=ChartArtifactList)
async def list_chart_artifacts(
    run_id: Optional[str] = Query(None),
    step_id: Optional[str] = Query(None),
    experiment_id: Optional[str] = Query(None),
    chart_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChartArtifact)
    if run_id:
        query = query.where(ChartArtifact.run_id == run_id)
    if step_id:
        query = query.where(ChartArtifact.step_id == step_id)
    if experiment_id:
        query = query.where(ChartArtifact.experiment_id == experiment_id)
    if chart_type:
        query = query.where(ChartArtifact.chart_type == chart_type)

    count_query = select(func.count(ChartArtifact.id))
    # Apply same filters to count query
    if run_id:
        count_query = count_query.where(ChartArtifact.run_id == run_id)
    if step_id:
        count_query = count_query.where(ChartArtifact.step_id == step_id)
    if experiment_id:
        count_query = count_query.where(ChartArtifact.experiment_id == experiment_id)
    if chart_type:
        count_query = count_query.where(ChartArtifact.chart_type == chart_type)

    total = await db.scalar(count_query)
    offset = (page - 1) * page_size
    query = query.order_by(ChartArtifact.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    artifacts = result.scalars().all()

    return ChartArtifactList(
        items=artifacts,
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=max(1, (total or 0 + page_size - 1) // page_size) if total else 0,
    )


# ---------------------------------------------------------------------------
# GET /charts/artifacts/{artifact_id}
# ---------------------------------------------------------------------------

@router.get("/artifacts/{artifact_id}", response_model=ChartArtifactResponse)
async def get_chart_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ChartArtifact).where(ChartArtifact.id == artifact_id))
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chart artifact not found")
    return artifact