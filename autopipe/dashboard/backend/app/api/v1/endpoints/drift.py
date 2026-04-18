"""Drift Detection endpoints."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DriftReport, DriftAlert, AlertSeverity
from app.db.session import get_db
from app.schemas import (
    DriftReportResponse, DriftReportList,
    DriftAlertResponse, DriftAlertList,
    DriftDetectRequest, DriftDetectResponse, FeatureDrift,
)

router = APIRouter()


def _normalize_feature_drifts(
    feature_drifts: Optional[Dict[str, Any]],
    default_threshold: float = 0.05,
) -> Dict[str, Dict[str, Any]]:
    """Normalize drift details into a stable, frontend-friendly shape."""
    normalized: Dict[str, Dict[str, Any]] = {}

    for feature_name, raw_value in (feature_drifts or {}).items():
        if isinstance(raw_value, dict):
            threshold = float(raw_value.get("threshold", default_threshold))
            p_value = raw_value.get("p_value")
            drift_score = raw_value.get("drift_score")
            if drift_score is None and p_value is not None:
                drift_score = max(0.0, min(1.0, 1.0 - float(p_value)))
            drift_score = float(drift_score or 0.0)

            is_drifted = raw_value.get("is_drifted")
            if is_drifted is None:
                if p_value is not None:
                    is_drifted = float(p_value) < threshold
                else:
                    is_drifted = drift_score > threshold

            normalized[feature_name] = {
                "drift_score": drift_score,
                "p_value": float(p_value) if p_value is not None else None,
                "threshold": threshold,
                "is_drifted": bool(is_drifted),
                "test_type": raw_value.get("test_type", "psi"),
            }
            continue

        drift_score = float(raw_value)
        normalized[feature_name] = {
            "drift_score": drift_score,
            "p_value": None,
            "threshold": default_threshold,
            "is_drifted": drift_score > default_threshold,
            "test_type": "psi",
        }

    return normalized


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


@router.post("/detect", response_model=DriftDetectResponse)
async def trigger_drift_detection(
    detect_request: DriftDetectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a drift detection job."""
    
    # In real implementation, this would launch a background job
    # For now, simulate a detection result
    
    metric_name = detect_request.test_types[0] if detect_request.test_types else "psi"
    feature_drifts_map = {
        "avg_session_duration": {
            "drift_score": 0.28,
            "p_value": 0.01,
            "threshold": detect_request.threshold,
            "is_drifted": 0.28 > detect_request.threshold,
            "test_type": metric_name,
        },
        "transaction_count": {
            "drift_score": 0.18,
            "p_value": 0.03,
            "threshold": detect_request.threshold,
            "is_drifted": 0.18 > detect_request.threshold,
            "test_type": metric_name,
        },
        "page_views": {
            "drift_score": 0.04,
            "p_value": 0.62,
            "threshold": detect_request.threshold,
            "is_drifted": 0.04 > detect_request.threshold,
            "test_type": metric_name,
        },
    }

    drifted_features = [
        feature_name
        for feature_name, details in feature_drifts_map.items()
        if details["is_drifted"]
    ]
    drift_detected = bool(drifted_features)
    overall_drift_score = max(
        (details["drift_score"] for details in feature_drifts_map.values()),
        default=0.0,
    )
    
    # Create drift report
    report = DriftReport(
        model_id=detect_request.model_id,
        run_id=None,
        drift_score=overall_drift_score,
        drift_detected=drift_detected,
        feature_drifts=feature_drifts_map,
        reference_data_summary={"rows": 10000, "columns": 20},
        current_data_summary={"rows": 5000, "columns": 20},
        alert_generated=drift_detected,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    
    # Generate alerts for drifted features
    if drift_detected:
        for feature in drifted_features:
            alert = DriftAlert(
                drift_report_id=report.id,
                feature_name=feature,
                severity=AlertSeverity.ERROR if feature_drifts_map[feature]["drift_score"] >= 0.25 else AlertSeverity.WARNING,
                drift_type="feature",
                drift_metric=metric_name,
                drift_score=feature_drifts_map[feature]["drift_score"],
                threshold=detect_request.threshold,
            )
            db.add(alert)
        await db.commit()
    
    # Build feature drift details
    feature_drifts = []
    for feature_name, stats in _normalize_feature_drifts(
        report.feature_drifts,
        default_threshold=detect_request.threshold,
    ).items():
        p_value = stats.get("p_value", 0.5)
        is_drifted = bool(stats.get("is_drifted"))
        if is_drifted:
            feature_drifts.append(FeatureDrift(
                feature_name=feature_name,
                drift_score=float(stats.get("drift_score", 0.0)),
                p_value=p_value,
                threshold=float(stats.get("threshold", detect_request.threshold)),
                is_drifted=is_drifted,
                test_type=stats.get("test_type", "ks"),
            ))
    
    return DriftDetectResponse(
        drift_detected=drift_detected,
        overall_drift_score=report.drift_score,
        features_analyzed=len(report.feature_drifts or {}),
        drifted_features=drifted_features,
        feature_drifts=feature_drifts,
        report_path=f"/api/v1/drift/{report.id}",
    )


@router.post("", response_model=DriftDetectResponse)
async def create_drift_report(
    detect_request: DriftDetectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a drift report / trigger drift detection.
    
    This endpoint is an alias for POST /drift/detect to match frontend expectations.
    """
    # Delegate to the detect endpoint
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


@router.post("/alerts/{alert_id}/acknowledge")
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
