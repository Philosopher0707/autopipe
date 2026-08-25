"""Drift Detection endpoints."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.auth import require_role
from app.db.models import DriftAlert, DriftReport
from app.db.session import get_db
from app.schemas import (
    DriftAlertList,
    DriftAlertResponse,
    DriftDetectRequest,
    DriftReportList,
    DriftReportResponse,
)
from app.utils.drift_utils import normalize_feature_drifts as _normalize_feature_drifts
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def _serialize_drift_report(report: DriftReport) -> Dict[str, Any]:
    """Serialize a drift report with normalized feature drift details."""
    normalized_feature_drifts = _normalize_feature_drifts(report.feature_drifts)
    features_drifted = sum(
        1 for details in normalized_feature_drifts.values() if details.get("is_drifted")
    )

    return {
        "id": report.id,
        "model_id": report.model_id,
        "run_id": report.run_id,
        "drift_score": report.drift_score,
        "drift_detected": report.drift_detected,
        "feature_drifts": normalized_feature_drifts,
        "reference_data_summary": report.reference_data_summary,
        "current_data_summary": report.current_data_summary,
        "created_at": report.created_at,
        "alert_generated": report.alert_generated,
        "features_drifted": features_drifted,
    }


@router.get("", response_model=DriftReportList)
async def list_drift_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    model_id: Optional[str] = Query(None, description="Filter by model"),
    drift_detected: Optional[bool] = Query(None, description="Filter by drift detection status"),
    db: AsyncSession = Depends(get_db),
):
    """List all drift detection reports."""

    count_query = select(func.count(DriftReport.id))
    query = select(DriftReport)

    if model_id:
        count_query = count_query.where(DriftReport.model_id == model_id)
        query = query.where(DriftReport.model_id == model_id)

    if drift_detected is not None:
        count_query = count_query.where(DriftReport.drift_detected == drift_detected)
        query = query.where(DriftReport.drift_detected == drift_detected)

    total = await db.scalar(count_query)

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(desc(DriftReport.created_at))

    result = await db.execute(query)
    reports = result.scalars().all()

    items = [_serialize_drift_report(report) for report in reports]

    return DriftReportList(
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=(total or 0) // page_size + (1 if (total or 0) % page_size else 0),
        items=items,
    )


@router.post("/detect")
async def trigger_drift_detection(
    detect_request: DriftDetectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger real drift detection.

    NOT IMPLEMENTED YET: this endpoint previously returned hardcoded scores
    for synthetic features and persisted them as real reports. Real detection
    against reference/current datasets lands with the monitoring rewrite
    (ROADMAP P2). This handler intentionally does not write anything.
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Drift detection is not implemented yet. This endpoint no longer "
            "returns simulated data. Use GET /drift/reports for existing reports."
        ),
    )


@router.post("", response_model=None)
async def create_drift_report(
    detect_request: DriftDetectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a drift report / trigger drift detection.

    Alias for POST /drift/detect — equally not implemented (see above).
    """
    return await trigger_drift_detection(detect_request, db)


@router.get("/reports/{report_id}", response_model=DriftReportResponse)
async def get_drift_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get drift report details."""
    result = await db.execute(select(DriftReport).where(DriftReport.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Drift report not found")

    return _serialize_drift_report(report)


@router.get("/latest")
async def get_latest_drift(
    model_id: Optional[str] = Query(None, description="Filter by model"),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest drift status."""
    query = select(DriftReport).order_by(desc(DriftReport.created_at))

    if model_id:
        query = query.where(DriftReport.model_id == model_id)

    query = query.limit(1)
    result = await db.execute(query)
    report = result.scalar_one_or_none()

    if not report:
        return {
            "id": None,
            "model_id": model_id,
            "drift_score": 0.0,
            "drift_detected": False,
            "feature_drifts": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "features_drifted": 0,
        }

    return _serialize_drift_report(report)


# ==================== Alerts ====================


@router.get("/alerts", response_model=DriftAlertList)
async def list_alerts(
    acknowledged: Optional[bool] = Query(None),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    feature_name: Optional[str] = Query(None, description="Filter by feature name"),
    feature: Optional[str] = Query(None, alias="feature", description="Legacy feature alias"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List drift alerts."""

    resolved_feature_name = feature_name or feature
    count_query = select(func.count(DriftAlert.id))
    query = select(DriftAlert)

    if acknowledged is not None:
        count_query = count_query.where(DriftAlert.acknowledged == acknowledged)
        query = query.where(DriftAlert.acknowledged == acknowledged)

    if severity:
        count_query = count_query.where(DriftAlert.severity == severity)
        query = query.where(DriftAlert.severity == severity)

    if resolved_feature_name:
        count_query = count_query.where(DriftAlert.feature_name.ilike(f"%{resolved_feature_name}%"))
        query = query.where(DriftAlert.feature_name.ilike(f"%{resolved_feature_name}%"))

    total = await db.scalar(count_query)

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(desc(DriftAlert.created_at))

    result = await db.execute(query)
    alerts = result.scalars().all()

    return DriftAlertList(
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=(total or 0) // page_size + (1 if (total or 0) % page_size else 0),
        items=[DriftAlertResponse.model_validate(a) for a in alerts],
    )


@router.post("/alerts/{alert_id}/acknowledge", dependencies=[Depends(require_role("admin"))])
async def acknowledge_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge a drift alert."""
    result = await db.execute(select(DriftAlert).where(DriftAlert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    # alert.acknowledged_by = current_user.id  # Would need auth

    await db.commit()
    await db.refresh(alert)

    return {"message": "Alert acknowledged", "alert_id": alert_id}


@router.get("/features/{feature_name}")
async def get_feature_drift_history(
    feature_name: str,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get drift history for a specific feature."""
    from datetime import timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(DriftAlert)
        .where(DriftAlert.feature_name == feature_name)
        .where(DriftAlert.created_at >= cutoff)
        .order_by(DriftAlert.created_at)
    )
    alerts = result.scalars().all()

    history = [
        {
            "timestamp": a.created_at.isoformat(),
            "drift_score": a.drift_score,
            "threshold": a.threshold,
            "severity": a.severity,
            "acknowledged": a.acknowledged,
        }
        for a in alerts
    ]

    return {
        "feature_name": feature_name,
        "days_analyzed": days,
        "history": history,
        "total_alerts": len(history),
    }


@router.get("/{drift_id}", response_model=DriftReportResponse)
async def get_drift_report_by_id(
    drift_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get drift report by ID.

    Must be last route to avoid conflicts with /latest, /alerts, /features, etc.
    """
    result = await db.execute(select(DriftReport).where(DriftReport.id == drift_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Drift report not found")

    return _serialize_drift_report(report)
