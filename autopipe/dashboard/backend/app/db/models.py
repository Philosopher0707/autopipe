"""Database models for the Dashboard."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship, declarative_base

Base = declarative_base()


class RunStatus(str, enum.Enum):
    """Pipeline run status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    """Step execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ModelStage(str, enum.Enum):
    """Model version stage enumeration."""
    PENDING = "pending"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class AlertSeverity(str, enum.Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class UserRole(str, enum.Enum):
    """User role enumeration."""
    ADMIN = "admin"
    DATA_SCIENTIST = "data_scientist"
    VIEWER = "viewer"


class Pipeline(Base):
    """ML Pipeline definition."""
    __tablename__ = "pipelines"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    config_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    runs: Mapped[List["Run"]] = relationship("Run", back_populates="pipeline", lazy="select")


class Run(Base):
    """Pipeline execution run."""
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id: Mapped[str] = mapped_column(String, ForeignKey("pipelines.id"), nullable=False)
    experiment_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("experiments.id"), nullable=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    config: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    metrics: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    logs_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    run_number: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    pipeline: Mapped["Pipeline"] = relationship("Pipeline", back_populates="runs")
    experiment: Mapped[Optional["Experiment"]] = relationship("Experiment", back_populates="runs")
    steps: Mapped[List["Step"]] = relationship("Step", back_populates="run", lazy="select")
    artifacts: Mapped[List["Artifact"]] = relationship("Artifact", back_populates="run", lazy="select")


class Step(Base):
    """Pipeline step execution."""
    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String, ForeignKey("runs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[StepStatus] = mapped_column(Enum(StepStatus), default=StepStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    config: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    metrics: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    input_shape: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    output_shape: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="steps")


class Experiment(Base):
    """ML Experiment definition."""
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    best_run_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    best_metric: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metric_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    runs: Mapped[List["Run"]] = relationship("Run", back_populates="experiment", lazy="select")


class Model(Base):
    """Registered ML Model."""
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    framework: Mapped[str] = mapped_column(String(50), nullable=False)  # sklearn, pytorch, tensorflow, etc.
    task_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # classification, regression, etc.
    signature: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    current_stage: Mapped[ModelStage] = mapped_column(Enum(ModelStage), default=ModelStage.PENDING)
    latest_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    versions: Mapped[List["ModelVersion"]] = relationship("ModelVersion", back_populates="model", lazy="select")


class ModelVersion(Base):
    """Model version snapshot."""
    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id: Mapped[str] = mapped_column(String, ForeignKey("models.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[ModelStage] = mapped_column(Enum(ModelStage), default=ModelStage.PENDING)
    metrics: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    params: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    artifact_path: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    run_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    transitioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Relationships
    model: Mapped["Model"] = relationship("Model", back_populates="versions")

    __table_args__ = (
        # Ensure version numbers are unique per model
        {"sqlite_autoincrement": True},
    )


class DriftReport(Base):
    """Data drift detection report."""
    __tablename__ = "drift_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("models.id"), nullable=True)
    run_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("runs.id"), nullable=True)
    drift_score: Mapped[float] = mapped_column(Float, default=0.0)
    drift_detected: Mapped[bool] = mapped_column(default=False)
    feature_drifts: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    reference_data_summary: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    current_data_summary: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    alert_generated: Mapped[bool] = mapped_column(default=False)


class DriftAlert(Base):
    """Drift alert record."""
    __tablename__ = "drift_alerts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    drift_report_id: Mapped[str] = mapped_column(String, ForeignKey("drift_reports.id"), nullable=False)
    feature_name: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity), default=AlertSeverity.WARNING)
    drift_type: Mapped[str] = mapped_column(String(50), nullable=False)  # feature, prediction, target
    drift_metric: Mapped[str] = mapped_column(String(50), nullable=False)  # ks, psi, chi2, etc.
    drift_score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(default=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Artifact(Base):
    """Run artifact (file, model, etc.)."""
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("runs.id"), nullable=True)
    step_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("steps.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)  # model, plot, metric, data
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    meta_data: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    run: Mapped[Optional["Run"]] = relationship("Run", back_populates="artifacts")
    step: Mapped[Optional["Step"]] = relationship("Step")


class User(Base):
    """Dashboard user."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER)
    api_key: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    preferences: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)


class DashboardMetric(Base):
    """Time-series metrics for dashboard widgets."""
    __tablename__ = "dashboard_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_type: Mapped[str] = mapped_column(String(50), default="gauge")  # gauge, counter, histogram
    tags: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    run_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("runs.id"), nullable=True)


class ActivityLog(Base):
    """User and system activity log."""
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # create_run, promote_model, etc.
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # run, model, pipeline
    resource_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    details: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
