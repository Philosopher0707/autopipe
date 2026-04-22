"""Dashboard overview endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ActivityLog,
    DashboardMetric,
    DriftAlert,
    DriftReport,
    Experiment,
    Model,
    ModelStage,
    Pipeline,
    Run,
    RunStatus,
)
from app.db.session import get_db
from app.schemas import (
    ActivityFeed, ActivityItem, DashboardStats, DriftStats, ExperimentStats,
    HealthStatus, ModelStats, PipelineStats, SidebarCounts, SystemHealth,
    ResourceUsageResponse, ResourceUsagePoint,
)

router = APIRouter()


def count_drifted_features(feature_drifts: dict | None) -> int:
    """Count how many features have drifted in a DriftReport.feature_drifts dict."""
    if not feature_drifts:
        return 0
    count = 0
    for stats in feature_drifts.values():
        if isinstance(stats, dict):
            if stats.get("is_drifted"):
                count += 1
            elif "p_value" in stats:
                threshold = float(stats.get("threshold", 0.05))
                if float(stats.get("p_value", 1.0)) < threshold:
                    count += 1
            elif "drift_score" in stats:
                threshold = float(stats.get("threshold", 0.1))
                if float(stats.get("drift_score", 0.0)) > threshold:
                    count += 1
        elif isinstance(stats, (int, float)):
            if float(stats) > 0.1:
                count += 1
    return count


@router.get("/overview", response_model=DashboardStats)
async def get_dashboard_overview(db: AsyncSession = Depends(get_db)):
    """Get dashboard overview statistics using optimized batch queries."""
    
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    
    pipeline_count = await db.scalar(select(func.count(Pipeline.id)))
    
    active_run_statuses = [RunStatus.RUNNING, RunStatus.PENDING]
    active_pipeline_sub = (
        select(Run.pipeline_id)
        .where(Run.status.in_(active_run_statuses))
        .distinct()
    )
    active_pipelines = await db.scalar(
        select(func.count()).select_from(Pipeline)
        .where(Pipeline.id.in_(active_pipeline_sub))
    )

    run_24h_query = select(
        func.count(Run.id)
        .filter(Run.status == RunStatus.SUCCESS, Run.completed_at >= yesterday)
        .label("completed"),
        func.count(Run.id)
        .filter(Run.status == RunStatus.FAILED, Run.completed_at >= yesterday)
        .label("failed"),
        func.avg(Run.duration_seconds)
        .filter(Run.completed_at >= yesterday, Run.duration_seconds.is_not(None))
        .label("avg_duration"),
    )

    run_24h = await db.execute(run_24h_query)
    row = run_24h.first()

    completed_24h = row.completed or 0 if row else 0
    failed_24h = row.failed or 0 if row else 0
    avg_duration = row.avg_duration if row else None

    total_24h = completed_24h + failed_24h
    success_rate = (completed_24h / total_24h * 100) if total_24h > 0 else 100.0
    
    model_counts = await db.execute(
        select(
            func.count(Model.id).label("total"),
            func.count(Model.id)
            .filter(Model.current_stage == ModelStage.PRODUCTION)
            .label("prod"),
            func.count(Model.id)
            .filter(Model.current_stage == ModelStage.STAGING)
            .label("staging"),
        )
    )
    model_row = model_counts.first()
    total_models = model_row.total or 0 if model_row else 0
    models_in_prod = model_row.prod or 0 if model_row else 0
    models_in_staging = model_row.staging or 0 if model_row else 0
    
    experiment_counts = await db.execute(
        select(
            func.count(func.distinct(Experiment.id)).label("total"),
            func.count(func.distinct(Experiment.id))
            .filter(Run.status.in_([RunStatus.RUNNING, RunStatus.PENDING]))
            .label("active"),
            func.count(func.distinct(Experiment.id))
            .filter(Experiment.updated_at >= yesterday)
            .label("recent"),
            func.count(Run.id).label("total_runs"),
        )
        .select_from(Experiment)
        .outerjoin(Run, Run.experiment_id == Experiment.id)
    )
    exp_row = experiment_counts.first()
    total_experiments = exp_row.total or 0 if exp_row else 0
    active_experiments = exp_row.active or 0 if exp_row else 0
    experiments_24h = exp_row.recent or 0 if exp_row else 0
    total_experiment_runs = exp_row.total_runs or 0 if exp_row else 0
    
    drift_counts = await db.execute(
        select(
            func.max(DriftAlert.created_at).label("last_check"),
            func.count(DriftAlert.id)
            .filter(DriftAlert.acknowledged.is_(False))
            .label("unack"),
            func.count(DriftAlert.id)
            .filter(DriftAlert.created_at >= yesterday)
            .label("today"),
        )
    )
    drift_row = drift_counts.first()
    latest_drift_check = drift_row.last_check if drift_row else None
    unacknowledged_alerts = drift_row.unack or 0 if drift_row else 0
    alerts_today = drift_row.today or 0 if drift_row else 0

    latest_report_result = await db.execute(
        select(DriftReport.drift_score, DriftReport.feature_drifts)
        .order_by(DriftReport.created_at.desc()).limit(1)
    )
    latest_report = latest_report_result.first()
    latest_drift_score = latest_report.drift_score if latest_report else 0.0
    latest_features_drifted = count_drifted_features(latest_report.feature_drifts if latest_report else None)
    
    stats = DashboardStats(
        pipelines=PipelineStats(
            total=pipeline_count or 0,
            running=active_pipelines or 0,
            completed_today=completed_24h or 0,
            failed_today=failed_24h or 0,
            avg_duration=f"{int((avg_duration or 0) / 60)}m {int((avg_duration or 0) % 60)}s",
            success_rate=round(success_rate, 1),
        ),
        models=ModelStats(
            total=total_models or 0,
            in_production=models_in_prod or 0,
            in_staging=models_in_staging or 0,
            recent_versions=0,
        ),
        drift=DriftStats(
            alerts_today=alerts_today or 0,
            features_drifted=latest_features_drifted,
            drift_ratio=latest_drift_score,
            last_check=latest_drift_check.isoformat() if latest_drift_check else None,
        ),
        experiments=ExperimentStats(
            total=total_experiments or 0,
            active=active_experiments or 0,
            completed_today=experiments_24h or 0,
            total_trials=total_experiment_runs or 0,
        ),
    )
    
    return stats


@router.get("/counts", response_model=SidebarCounts)
async def get_sidebar_counts(db: AsyncSession = Depends(get_db)):
    """Get sidebar badge counts with clean direct queries — no complex joins."""

    # Pipelines: total and those with active (non-terminal) runs
    pipelines_total = await db.scalar(select(func.count(Pipeline.id)))

    active_run_statuses = [RunStatus.RUNNING, RunStatus.PENDING]
    active_pipeline_sub = (
        select(Run.pipeline_id)
        .where(Run.status.in_(active_run_statuses))
        .distinct()
    )
    pipelines_active = await db.scalar(
        select(func.count()).select_from(Pipeline)
        .where(Pipeline.id.in_(active_pipeline_sub))
    )

    # Experiments: total and those with active runs
    experiments_total = await db.scalar(select(func.count(Experiment.id)))

    active_exp_sub = (
        select(Run.experiment_id)
        .where(Run.status.in_(active_run_statuses))
        .distinct()
    )
    experiments_active = await db.scalar(
        select(func.count()).select_from(Experiment)
        .where(Experiment.id.in_(active_exp_sub))
    )

    # Models
    models_total = await db.scalar(select(func.count(Model.id)))
    models_in_production = await db.scalar(
        select(func.count(Model.id))
        .where(Model.current_stage == ModelStage.PRODUCTION)
    )

    # Drift alerts: unacknowledged count
    drift_alerts_unacknowledged = await db.scalar(
        select(func.count(DriftAlert.id))
        .where(DriftAlert.acknowledged == False)
    )

    # Drift reports: features currently drifted from latest report
    latest_report_result = await db.execute(
        select(DriftReport.feature_drifts)
        .order_by(DriftReport.created_at.desc()).limit(1)
    )
    latest_report = latest_report_result.first()
    drift_features_drifted = count_drifted_features(latest_report.feature_drifts if latest_report else None)

    return SidebarCounts(
        pipelines_total=pipelines_total or 0,
        pipelines_active=pipelines_active or 0,
        experiments_total=experiments_total or 0,
        experiments_active=experiments_active or 0,
        models_total=models_total or 0,
        models_in_production=models_in_production or 0,
        drift_alerts_unacknowledged=drift_alerts_unacknowledged or 0,
        drift_features_drifted=drift_features_drifted,
    )


@router.get("/activity", response_model=ActivityFeed)
async def get_recent_activity(
    limit: int = Query(20, ge=1, le=100),
    activity_type: Optional[str] = Query(None, alias="type", description="Filter by activity type: run_completed, model_promoted, drift_alert, etc."),
    db: AsyncSession = Depends(get_db),
):
    """Get recent activity feed."""
    
    query = select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    
    if activity_type:
        query = query.where(ActivityLog.action.contains(activity_type))
    
    result = await db.execute(query)
    activities = result.scalars().all()
    
    activity_items = [
        ActivityItem(
            action=activity.action,
            timestamp=activity.created_at,
            title=activity.details.get("title", "Activity occurred") if activity.details else "Activity",
            description=activity.details.get("description", "") if activity.details else "",
            resource_type=activity.resource_type,
            resource_id=activity.resource_id,
            user=activity.user_id,
        )
        for activity in activities
    ]

    return ActivityFeed(items=activity_items[:limit])


@router.get("/health", response_model=SystemHealth)
async def get_system_health(db: AsyncSession = Depends(get_db)):
    """Get system health status with real connectivity checks."""

    now = datetime.now(timezone.utc)
    services: list[HealthStatus] = []

    # Database connectivity check
    try:
        await db.execute(select(1))
        services.append(HealthStatus(service="database", status="healthy", message="Connected", last_check=now))
    except Exception as e:
        services.append(HealthStatus(service="database", status="down", message=str(e)[:200], last_check=now))

    # Autopipe core check (import availability)
    try:
        from autopipe.core.pipeline import Pipeline  # noqa: F401
        services.append(HealthStatus(service="autopipe_core", status="healthy", message="Available", last_check=now))
    except ImportError:
        services.append(HealthStatus(service="autopipe_core", status="degraded", message="Not installed", last_check=now))

    overall_status = "healthy"
    if any(s.status == "down" for s in services):
        overall_status = "degraded"
    elif any(s.status == "degraded" for s in services):
        overall_status = "degraded"

    return SystemHealth(status=overall_status, services=services)


@router.get("/metrics/timeseries")
async def get_metrics_timeseries(
    metric_name: str,
    start: datetime = Query(None),
    end: datetime = Query(None),
    interval: str = Query("1h", description="Aggregation interval: 1m, 5m, 1h, 1d"),
    db: AsyncSession = Depends(get_db),
):
    """Get time-series metrics for dashboard charts."""
    end = end or datetime.now(timezone.utc)
    start = start or (end - timedelta(days=7))
    
    # Query time-series metrics from database
    result = await db.execute(
        select(DashboardMetric)
        .where(DashboardMetric.metric_name.contains(metric_name))
        .where(DashboardMetric.recorded_at >= start)
        .where(DashboardMetric.recorded_at <= end)
        .order_by(DashboardMetric.recorded_at)
    )
    metrics = result.scalars().all()
    
    points = [
        {
            "timestamp": m.recorded_at.isoformat(),
            "value": m.metric_value,
            "tags": m.tags,
        }
        for m in metrics
    ]

    return {
        "metric_name": metric_name,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "interval": interval,
        "points": points,
    }


@router.get("/alerts")
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, error, critical"),
    acknowledged: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get active alerts."""
    
    query = select(DriftAlert).where(DriftAlert.acknowledged == acknowledged).order_by(DriftAlert.created_at.desc()).limit(limit)
    
    if severity:
        query = query.where(DriftAlert.severity == severity)
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    alert_list = [
        {
            "id": alert.id,
            "feature_name": alert.feature_name,
            "type": alert.drift_type,
            "severity": alert.severity,
            "drift_score": alert.drift_score,
            "acknowledged": alert.acknowledged,
            "created_at": alert.created_at.isoformat(),
            "message": f"{alert.drift_type.capitalize()} drift in '{alert.feature_name}': {alert.drift_metric} = {alert.drift_score:.3f}",
        }
        for alert in alerts
    ]

    return {"alerts": alert_list, "total": len(alert_list)}


@router.get("/metrics")
async def get_dashboard_metrics(
    metric_name: Optional[str] = Query(None, description="Filter by metric name"),
    pipeline_id: Optional[str] = Query(None, description="Filter by pipeline ID"),
    start: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end: Optional[datetime] = Query(None, description="End time (ISO format)"),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard metrics (alias for timeseries endpoint).
    
    This endpoint matches the frontend expectation at /api/v1/dashboard/metrics
    """
    end = end or datetime.now(timezone.utc)
    start = start or (end - timedelta(days=7))
    
    # Build query
    query = select(DashboardMetric).where(
        DashboardMetric.recorded_at >= start
    ).where(
        DashboardMetric.recorded_at <= end
    ).order_by(DashboardMetric.recorded_at)
    
    if metric_name:
        query = query.where(DashboardMetric.metric_name.contains(metric_name))
    
    if pipeline_id:
        query = query.where(DashboardMetric.tags.contains({"pipeline_id": pipeline_id}))
    
    result = await db.execute(query)
    metrics = result.scalars().all()
    
    data_points = [
        {
            "timestamp": m.recorded_at.isoformat(),
            "value": m.metric_value,
        }
        for m in metrics
    ]

    return {"data": data_points}


@router.get("/resources", response_model=ResourceUsageResponse)
async def get_resource_usage(hours: int = 24, db: AsyncSession = Depends(get_db)):
    """Get system resource usage for the last N hours (default 24).

    Returns seeded data. Will use psutil for real metrics when available.
    """
    import random
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    points = []
    for i in range(min(hours * 4, 288)):  # 4 points/hour, max 288
        ts = now - timedelta(minutes=15 * i)
        points.append(ResourceUsagePoint(
            timestamp=ts,
            cpu_percent=round(random.uniform(10, 85), 1),
            memory_percent=round(random.uniform(40, 75), 1),
            gpu_percent=round(random.uniform(0, 95), 1) if i % 3 == 0 else None,
        ))
    points.reverse()
    return ResourceUsageResponse(points=points)
