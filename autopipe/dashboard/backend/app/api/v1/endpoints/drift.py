"""Drift Detection endpoints."""

from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DriftReport, DriftAlert, AlertSeverity
from app.db.session import get_db
from app.schemas import (
    DriftReportCreate, DriftReportResponse, DriftReportList,
    DriftAlertResponse, DriftAlertList,
    DriftDetectRequest, DriftDetectResponse, FeatureDrift,
)

router = APIRouter()


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
    
    return DriftReportList(
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=(total or 0) // page_size + (1 if (total or 0) % page_size else 0),
        items=[DriftReportResponse.model_validate(r) for r in reports],
    )


@router.post("/detect", response_model=DriftDetectResponse)
async def trigger_drift_detection(
    detect_request: DriftDetectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a drift detection job."""
    
    # In real implementation, this would launch a background job
    # For now, simulate a detection result
    
    # Mock drift detection results
    drifted_features = ["avg_session_duration", "transaction_count"] if detect_request.threshold > 0.05 else []
    drift_detected = len(drifted_features) > 0
    
    # Create drift report
    report = DriftReport(
        model_id=detect_request.model_id,
        run_id=None,
        drift_score=0.28,
        drift_detected=drift_detected,
        feature_drifts={
            f"feature_{i}": {
                "p_value": 0.01 if i % 3 == 0 else 0.5,
                "test_type": detect_request.test_types[0],
            }
            for i in range(10)
        },
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
                severity=AlertSeverity.WARNING,
                drift_type="feature",
                drift_metric="psi",
                drift_score=0.28,
                threshold=detect_request.threshold,
            )
            db.add(alert)
        await db.commit()
    
    # Build feature drift details
    feature_drifts = []
    for feature_name, stats in (report.feature_drifts or {}).items():
        p_value = stats.get("p_value", 0.5)
        is_drifted = p_value < detect_request.threshold
        if is_drifted:
            feature_drifts.append(FeatureDrift(
                feature_name=feature_name,
                drift_score=1.0 - p_value,
                p_value=p_value,
                threshold=detect_request.threshold,
                is_drifted=is_drifted,
                test_type=stats.get("test_type", "ks"),
            ))
    
    return DriftDetectResponse(
        drift_detected=drift_detected,
        overall_drift_score=report.drift_score,
        features_analyzed=len(report.feature_drifts or {}),
        drifted_features=drifted_features,
        feature_drifts=feature_drifts,
        report_path=f"/api/v1/drift/reports/{report.id}",
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
    
    return report


@router.get("/{drift_id}", response_model=DriftReportResponse)
async def get_drift_report_by_id(
    drift_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get drift report by ID (alias for /reports/{id}).
    
    This endpoint matches the frontend expectation at /api/v1/drift/{id}
    """
    result = await db.execute(select(DriftReport).where(DriftReport.id == drift_id))
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Drift report not found")
    
    return report


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
            "drift_detected": False,
            "last_check": datetime.utcnow().isoformat(),
            "features_drifted": 0,
            "drift_score": 0.0,
        }
    
    # Count alerts for this report
    alerts_count = await db.scalar(
        select(func.count(DriftAlert.id)).where(DriftAlert.drift_report_id == report.id)
    )
    
    return {
        "drift_detected": report.drift_detected,
        "last_check": report.created_at.isoformat(),
        "features_drifted": alerts_count or 0,
        "drift_score": report.drift_score,
        "report_id": report.id,
    }


# ==================== Alerts ====================

@router.get("/alerts", response_model=DriftAlertList)
async def list_alerts(
    acknowledged: bool = Query(False),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    featured: Optional[str] = Query(None, description="Filter by feature name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List drift alerts."""
    
    count_query = select(func.count(DriftAlert.id)).where(DriftAlert.acknowledged == acknowledged)
    query = select(DriftAlert).where(DriftAlert.acknowledged == acknowledged)
    
    if severity:
        count_query = count_query.where(DriftAlert.severity == severity)
        query = query.where(DriftAlert.severity == severity)
    
    if featured:
        count_query = count_query.where(DriftAlert.feature_name.ilike(f"%{featured}%"))
        query = query.where(DriftAlert.feature_name.ilike(f"%{featured}%"))
    
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
    alert.acknowledged_at = datetime.utcnow()
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
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
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
