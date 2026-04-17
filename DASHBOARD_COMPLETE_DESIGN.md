# AutoPipe Dashboard - Complete Production Design Document

## Executive Summary

This document outlines the comprehensive design for AutoPipe's production-grade ML dashboard, covering architecture, API design, frontend components, data models, and deployment strategy.

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │   Web Browser   │  │  Mobile Browser │  │   CLI Tools     │               │
│  │   (React SPA)   │  │  (Responsive)   │  │   (curl/API)    │               │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘               │
│           │                    │                    │                       │
│           └────────────────────┴────────────────────┘                       │
│                               │                                              │
│                        WebSocket / HTTP                                      │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                           API GATEWAY                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FastAPI Application                              │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐  │   │
│  │  │  REST Router  │  │  WebSocket    │  │   GraphQL (Future)    │  │   │
│  │  │    /api/v1/   │  │   /ws/v1/     │  │      /graphql         │  │   │
│  │  └───────────────┘  └───────────────┘  └───────────────────────┘  │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Middleware Stack: Auth → Rate Limit → Logging → CORS       │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                         SERVICE LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │ PipelineService │  │  ModelService   │  │  DriftService   │               │
│  │                 │  │                 │  │                 │               │
│  │ • Execute runs  │  │ • CRUD models   │  │ • Detect drift  │               │
│  │ • Monitor logs  │  │ • Version mgmt  │  │ • PSI/KS tests  │               │
│  │ • Track metrics │  │ • Compare models│  │ • Alert config  │               │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘               │
│           │                    │                    │                       │
│  ┌────────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐             │
│  │ExperimentService│  │  AlertService   │  │DashboardService │             │
│  │                 │  │                 │  │                 │             │
│  │ • Optuna integ  │  │ • WebSocket push│  │ • Aggregations  │             │
│  │ • HP tracking   │  │ • Email/Slack │  │ • Time series   │             │
│  │ • Run compare   │  │ • Alert rules   │  │ • KPI metrics   │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                          DATA LAYER                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │    PostgreSQL   │  │     Redis       │  │   Elasticsearch │             │
│  │  (Primary DB)   │  │ (Cache+PubSub)  │  │ (Logs+Search)   │             │
│  │                 │  │                 │  │                 │             │
│  │ • Pipelines     │  │ • Session cache │  │ • Full-text     │             │
│  │ • Runs          │  │ • Rate limiting │  │   search index  │             │
│  │ • Models        │  │ • Real-time     │  │ • Log analytics │             │
│  │ • Users         │  │   pub/sub       │  │ • Aggregations  │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                    │                       │
│           └────────────────────┴────────────────────┘                       │
│                               │                                              │
│  ┌────────────────────────────▼────────────────────────────┐              │
│  │              Object Storage (S3/MinIO)                     │              │
│  │  • Model artifacts (.pkl, .onnx, .pt, .h5)               │              │
│  │  • Pipeline definitions (YAML/JSON)                       │              │
│  │  • Generated plots and reports                            │              │
│  │  • Dataset snapshots for reproducibility                  │              │
│  └────────────────────────────────────────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Data Models & Database Schema

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ENTITY RELATIONSHIPS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐         │
│  │    User      │1       * │   Pipeline   │1       * │    Run       │         │
│  │──────────────│◄────────│──────────────│◄────────│──────────────│         │
│  │ id (PK)      │         │ id (PK)      │         │ id (PK)      │         │
│  │ username     │         │ name         │         │ pipeline_id  │(FK)      │
│  │ email        │         │ description  │         │ status       │         │
│  │ role         │         │ config       │         │ started_at   │         │
│  │ created_at   │         │ created_by   │(FK)     │ completed_at │         │
│  └──────────────┘         │ tags[]       │         │ metrics      │         │
│                           └──────────────┘         └──────┬───────┘         │
│                                                           │                 │
│                           ┌───────────────────────────────┘                 │
│                           │ 1                                                 │
│                           │                                                 │
│                           │ *                                               │
│                    ┌──────▼────────┐         ┌──────────────┐               │
│                    │   RunStep     │         │   Artifact   │               │
│                    │───────────────│         │──────────────│               │
│                    │ id (PK)       │         │ id (PK)      │               │
│                    │ run_id (FK)   │         │ run_id (FK)  │               │
│                    │ step_name     │         │ name         │               │
│                    │ step_type     │         │ type         │               │
│                    │ status        │         │ path         │               │
│                    │ duration_ms   │         │ metadata     │               │
│                    └───────────────┘         └──────────────┘               │
│                                                                             │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐         │
│  │    Model     │1       * │ModelVersion │1       * │ModelArtifact │         │
│  │──────────────│◄────────│──────────────│◄────────│──────────────│         │
│  │ id (PK)      │         │ id (PK)      │         │ id (PK)      │         │
│  │ name         │         │ model_id(FK)│         │ version_id(FK)         │
│  │ description  │         │ version     │         │ type         │         │
│  │ framework    │         │ status       │         │ path         │         │
│  │ tags[]       │         │ metrics      │         │ size_bytes   │         │
│  └──────────────┘         │ params       │         └──────────────┘         │
│                           │ stage         │                                 │
│                           └──────────────┘                                 │
│                                    │                                        │
│                                    │ *                                      │
│                                    │                                        │
│                                    ▼ 1                                      │
│                           ┌──────────────┐                                  │
│                           │ ModelCompare │                                  │
│                           │──────────────│                                  │
│                           │ id (PK)      │                                  │
│                           │ v1_id (FK)   │                                  │
│                           │ v2_id (FK)   │                                  │
│                           │ report       │                                  │
│                           │ winner       │                                  │
│                           └──────────────┘                                  │
│                                                                             │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐         │
│  │  Experiment  │1       * │  Trial       │1       * │ TrialMetric  │       │
│  │──────────────│◄────────│──────────────│◄────────│──────────────│       │
│  │ id (PK)      │         │ id (PK)      │         │ id (PK)      │       │
│  │ name         │         │ exp_id (FK)  │         │ trial_id(FK) │       │
│  │ search_space │         │ params       │         │ name         │       │
│  │ best_trial   │         │ value        │         │ value        │       │
│  │ status       │         │ status       │         └──────────────│       │
│  └──────────────┘         └──────────────┘                               │       │
│                                                                             │
│  ┌──────────────┐         ┌──────────────┐                                │
│  │ DriftReport  │1       * │DriftFeature  │                               │
│  │──────────────│◄────────│──────────────│                               │
│  │ id (PK)      │         │ id (PK)      │                               │
│  │ model_id(FK) │         │ report_id(FK)│                               │
│  │ timestamp    │         │ feature_name │                               │
│  │ drift_ratio  │         │ drift_detected│                              │
│  │ status       │         │ psi_value    │                               │
│  └──────────────┘         └──────────────┘                               │
│                                                                             │
│  ┌──────────────┐         ┌──────────────┐                                │
│  │   Alert      │         │ AlertRule    │                                │
│  │──────────────│         │──────────────│                                │
│  │ id (PK)      │         │ id (PK)      │                                │
│  │ type         │         │ name         │                                │
│  │ severity     │         │ condition    │                                │
│  │ message      │         │ action       │                                │
│  │ acknowledged │         │ enabled      │                                │
│  └──────────────┘         └──────────────┘                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### SQLAlchemy Models (Full Implementation)

```python
# backend/app/db/models.py

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, 
    ForeignKey, Enum as SQLEnum, JSON, Index, Table
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

# Association table for pipeline tags
pipeline_tags = Table(
    'pipeline_tags',
    Base.metadata,
    Column('pipeline_id', ForeignKey('pipelines.id'), primary_key=True),
    Column('tag_id', ForeignKey('tags.id'), primary_key=True)
)


class UserRole(str, Enum):
    ADMIN = "admin"
    DATA_SCIENTIST = "data_scientist"
    VIEWER = "viewer"

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ModelStage(str, Enum):
    PENDING = "pending"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

# ============================================================================
# USER & ACCESS CONTROL
# ============================================================================

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(SQLEnum(UserRole), default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Relationships
    pipelines = relationship("Pipeline", back_populates="created_by_user")
    api_keys = relationship("APIKey", back_populates="user")


class APIKey(Base):
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(100))
    scopes = Column(JSON, default=list)  # ["read", "write", "admin"]
    last_used = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="api_keys")


# ============================================================================
# PIPELINE & EXECUTION
# ============================================================================

class Tag(Base):
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(7), default="#3B82F6")  # Hex color


class Pipeline(Base):
    __tablename__ = 'pipelines'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    config = Column(JSON)  # Pipeline DAG definition
    created_by = Column(Integer, ForeignKey('users.id'))
    is_active = Column(Boolean, default=True)
    schedule = Column(String(100))  # Cron expression for scheduled runs
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    runs = relationship("Run", back_populates="pipeline", cascade="all, delete-orphan")
    created_by_user = relationship("User", back_populates="pipelines")
    tags = relationship("Tag", secondary=pipeline_tags)
    
    # Indexes
    __table_args__ = (
        Index('ix_pipelines_name_active', 'name', 'is_active'),
    )


class Run(Base):
    __tablename__ = 'runs'
    
    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, ForeignKey('pipelines.id'), nullable=False)
    status = Column(SQLEnum(RunStatus), default=RunStatus.PENDING, index=True)
    run_number = Column(Integer)  # Auto-increment per pipeline
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)  # Calculated field
    
    # Execution context
    config_snapshot = Column(JSON)  # Pipeline config at run time
    environment = Column(JSON)  # Python version, packages, etc.
    triggered_by = Column(String(50))  # user:123, schedule, webhook
    
    # Results
    metrics = Column(JSON)  # Aggregated metrics: {"accuracy": 0.95, "f1": 0.92}
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    pipeline = relationship("Pipeline", back_populates="runs")
    steps = relationship("RunStep", back_populates="run", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="run")
    logs = relationship("LogEntry", back_populates="run")
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_runs_pipeline_status', 'pipeline_id', 'status'),
        Index('ix_runs_started_at', 'started_at'),
    )


class RunStep(Base):
    """Individual step within a pipeline run"""
    __tablename__ = 'run_steps'
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey('runs.id'), nullable=False)
    
    step_name = Column(String(100), nullable=False)
    step_type = Column(String(50))  # "TrainStep", "DataLoadingStep", etc.
    step_index = Column(Integer)  # Order in pipeline
    
    status = Column(SQLEnum(RunStatus), default=RunStatus.PENDING)
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    
    # Execution
    inputs = Column(JSON)  # Input artifacts/data references
    outputs = Column(JSON)  # Output artifacts/data references
    metrics = Column(JSON)  # Step-specific metrics
    parameters = Column(JSON)  # Step configuration
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    run = relationship("Run", back_populates="steps")
    artifacts = relationship("Artifact", back_populates="step")


class Artifact(Base):
    """Artifacts produced by pipeline runs"""
    __tablename__ = 'artifacts'
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey('runs.id'), nullable=False)
    step_id = Column(Integer, ForeignKey('run_steps.id'), nullable=True)
    
    name = Column(String(200), nullable=False)
    type = Column(String(50))  # "model", "dataset", "plot", "report", "metric"
    mime_type = Column(String(100))  # "application/json", "image/png"
    
    # Storage
    storage_backend = Column(String(20), default="s3")  # s3, gcs, local
    storage_path = Column(String(500))  # Full path/URI
    size_bytes = Column(Integer)
    checksum = Column(String(64))  # SHA-256
    
    # Metadata
    metadata = Column(JSON)  # Additional artifact metadata
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    run = relationship("Run", back_populates="artifacts")
    step = relationship("RunStep", back_populates="artifacts")


class LogEntry(Base):
    """Structured logs from pipeline execution"""
    __tablename__ = 'logs'
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey('runs.id'), nullable=False)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    level = Column(String(10))  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text)
    source = Column(String(100))  # "step:TrainStep", "system", etc.
    
    # Structured data
    step_id = Column(Integer, ForeignKey('run_steps.id'))
    extra = Column(JSON)  # Additional structured fields
    
    run = relationship("Run", back_populates="logs")
    
    __table_args__ = (
        Index('ix_logs_run_timestamp', 'run_id', 'timestamp'),
    )


# ============================================================================
# MODEL REGISTRY
# ============================================================================

class Model(Base):
    """Registered model (umbrella for all versions)"""
    __tablename__ = 'models'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text)
    
    # Model characteristics
    framework = Column(String(50))  # "sklearn", "pytorch", "tensorflow", "xgboost"
    task_type = Column(String(50))  # "classification", "regression", "clustering"
    
    # Current state
    latest_version = Column(Integer, default=0)
    production_version = Column(Integer)
    
    # Metadata
    tags = Column(JSON, default=list)
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")


class ModelVersion(Base):
    """Specific version of a registered model"""
    __tablename__ = 'model_versions'
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey('models.id'), nullable=False)
    version = Column(Integer, nullable=False)
    
    # Stage lifecycle
    stage = Column(SQLEnum(ModelStage), default=ModelStage.PENDING)
    
    # Source
    run_id = Column(Integer, ForeignKey('runs.id'))  # Source run
    artifact_id = Column(Integer, ForeignKey('artifacts.id'))  # Model artifact
    
    # Model characteristics
    signature = Column(JSON)  # Input/output signature
    parameters = Column(JSON)  # Model hyperparameters
    
    # Performance metrics (denormalized for quick access)
    metrics = Column(JSON)  # {"accuracy": 0.95, "f1": 0.92}
    
    # Metadata
    description = Column(Text)
    tags = Column(JSON, default=list)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    model = relationship("Model", back_populates="versions")
    artifacts = relationship("ModelArtifact", back_populates="version")
    comparisons_as_v1 = relationship("ModelComparison", foreign_keys="ModelComparison.v1_id")
    comparisons_as_v2 = relationship("ModelComparison", foreign_keys="ModelComparison.v2_id")
    
    __table_args__ = (
        Index('ix_model_versions_model_version', 'model_id', 'version', unique=True),
        Index('ix_model_versions_stage', 'stage'),
    )


class ModelArtifact(Base):
    """Artifacts associated with a model version"""
    __tablename__ = 'model_artifacts'
    
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey('model_versions.id'), nullable=False)
    
    artifact_type = Column(String(50))  # "model", "onnx", "tflite", "schema"
    storage_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer)
    checksum = Column(String(64))
    
    version = relationship("ModelVersion", back_populates="artifacts")


class ModelComparison(Base):
    """A/B comparison between two model versions"""
    __tablename__ = 'model_comparisons'
    
    id = Column(Integer, primary_key=True, index=True)
    
    v1_id = Column(Integer, ForeignKey('model_versions.id'), nullable=False)
    v2_id = Column(Integer, ForeignKey('model_versions.id'), nullable=False)
    
    # Comparison results
    metric_differences = Column(JSON)  # {"accuracy": 0.03, "f1": 0.02}
    is_improvement = Column(Boolean)
    winner_id = Column(Integer, ForeignKey('model_versions.id'))
    
    # Report
    report_markdown = Column(Text)  # Full comparison report
    report_html = Column(Text)
    
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================================
# EXPERIMENT TRACKING
# ============================================================================

class Experiment(Base):
    """Hyperparameter optimization experiment"""
    __tablename__ = 'experiments'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    
    # Configuration
    search_space = Column(JSON)  # {"lr": {"type": "float", "low": 0.001, "high": 0.1}}
    direction = Column(String(10), default="minimize")  # minimize/maximize
    metric_name = Column(String(50))  # Primary optimization metric
    
    # State
    status = Column(String(20), default="running")  # running, completed, failed
    best_trial_id = Column(Integer, ForeignKey('trials.id'))
    n_trials = Column(Integer, default=100)
    n_completed = Column(Integer, default=0)
    
    # Metadata
    pipeline_id = Column(Integer, ForeignKey('pipelines.id'))
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    trials = relationship("Trial", back_populates="experiment", foreign_keys="Trial.experiment_id")
    best_trial = relationship("Trial", foreign_keys=[best_trial_id])


class Trial(Base):
    """Individual trial within an experiment"""
    __tablename__ = 'trials'
    
    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey('experiments.id'), nullable=False)
    trial_number = Column(Integer)
    
    # Parameters
    params = Column(JSON)  # {"lr": 0.01, "batch_size": 32}
    
    # Results
    value = Column(Float)  # Primary metric value
    status = Column(String(20), default="running")  # running, completed, failed, pruned
    
    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    
    # Relationships
    experiment = relationship("Experiment", back_populates="trials", foreign_keys=[experiment_id])
    metrics = relationship("TrialMetric", back_populates="trial", cascade="all, delete-orphan")


class TrialMetric(Base):
    """All metrics recorded for a trial"""
    __tablename__ = 'trial_metrics'
    
    id = Column(Integer, primary_key=True, index=True)
    trial_id = Column(Integer, ForeignKey('trials.id'), nullable=False)
    
    name = Column(String(50), nullable=False)
    value = Column(Float)
    step = Column(Integer, default=0)  # For training curves
    
    trial = relationship("Trial", back_populates="metrics")


# ============================================================================
# DRIFT DETECTION
# ============================================================================

class DriftReport(Base):
    """Data drift detection report"""
    __tablename__ = 'drift_reports'
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey('models.id'))
    model_version_id = Column(Integer, ForeignKey('model_versions.id'))
    
    # Source data
    reference_dataset = Column(String(200))  # Reference dataset ID/path
    current_dataset = Column(String(200))  # Current dataset ID/path
    
    # Overall results
    drift_detected = Column(Boolean, default=False)
    drift_ratio = Column(Float)  # % of features drifted
    features_drifted = Column(Integer)
    features_total = Column(Integer)
    
    # Statistics
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    detection_method = Column(String(50))  # "psi", "ks", "chi2", "wasserstein"
    threshold = Column(Float, default=0.05)  # p-value or PSI threshold
    
    # Report
    summary = Column(JSON)  # Quick summary stats
    report_path = Column(String(500))  # Full HTML report
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    features = relationship("DriftFeature", back_populates="report", cascade="all, delete-orphan")


class DriftFeature(Base):
    """Drift status for individual features"""
    __tablename__ = 'drift_features'
    
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey('drift_reports.id'), nullable=False)
    
    feature_name = Column(String(100), nullable=False)
    feature_type = Column(String(20))  # "numeric", "categorical"
    
    # Drift statistics
    drift_detected = Column(Boolean, default=False)
    psi_value = Column(Float)
    ks_statistic = Column(Float)
    ks_pvalue = Column(Float)
    wasserstein_distance = Column(Float)
    
    # Distribution stats
    reference_mean = Column(Float)
    reference_std = Column(Float)
    current_mean = Column(Float)
    current_std = Column(Float)
    
    # Charts
    distribution_plot_path = Column(String(500))
    
    report = relationship("DriftReport", back_populates="features")


# ============================================================================
# ALERTING
# ============================================================================

class AlertRule(Base):
    """Alert configuration rules"""
    __tablename__ = 'alert_rules'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Conditions
    condition_type = Column(String(50))  # "drift", "metric_threshold", "pipeline_failure", "experiment_completed"
    condition_config = Column(JSON)  # {"metric": "accuracy", "operator": "<", "threshold": 0.9}
    
    # Actions
    actions = Column(JSON)  # [{"type": "webhook", "url": "..."}, {"type": "email", "to": "..."}]
    
    # Status
    enabled = Column(Boolean, default=True)
    cooldown_minutes = Column(Integer, default=60)  # Min time between alerts
    
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    """Triggered alerts"""
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey('alert_rules.id'))
    
    severity = Column(SQLEnum(AlertSeverity), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text)
    
    # Context
    source_type = Column(String(50))  # "drift", "pipeline", "model", "system"
    source_id = Column(String(50))  # ID of triggering entity
    context = Column(JSON)  # Additional context
    
    # Status
    status = Column(String(20), default="open")  # open, acknowledged, resolved
    acknowledged_by = Column(Integer, ForeignKey('users.id'))
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes for alert queries
    __table_args__ = (
        Index('ix_alerts_status_created', 'status', 'created_at'),
        Index('ix_alerts_severity', 'severity'),
    )


# ============================================================================
# DASHBOARD & METRICS
# ============================================================================

class DashboardMetric(Base):
    """Time-series metrics for dashboard charts"""
    __tablename__ = 'dashboard_metrics'
    
    id = Column(Integer, primary_key=True, index=True)
    
    metric_name = Column(String(100), nullable=False, index=True)
    metric_type = Column(String(50))  # "counter", "gauge", "histogram"
    
    # Dimensions
    pipeline_id = Column(Integer, ForeignKey('pipelines.id'))
    model_id = Column(Integer, ForeignKey('models.id'))
    tags = Column(JSON)  # Additional dimensions
    
    # Value
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('ix_metrics_name_time', 'metric_name', 'timestamp'),
        Index('ix_metrics_pipeline_time', 'pipeline_id', 'timestamp'),
    )


class ActivityLog(Base):
    """User-facing activity feed"""
    __tablename__ = 'activity_logs'
    
    id = Column(Integer, primary_key=True, index=True)
    
    activity_type = Column(String(50), nullable=False, index=True)  # "run_completed", "model_promoted", etc.
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Actor
    user_id = Column(Integer, ForeignKey('users.id'))
    
    # Related entities
    entity_type = Column(String(50))  # "pipeline", "run", "model"
    entity_id = Column(String(50))
    
    # Metadata
    metadata = Column(JSON)
    is_read = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('ix_activity_user_time', 'user_id', 'created_at'),
    )
```

---

## 🚀 API Design (REST + WebSocket)

### OpenAPI Specification Overview

```yaml
openapi: 3.0.0
info:
  title: AutoPipe Dashboard API
  version: 1.0.0
  description: Production-grade API for AutoPipe ML Dashboard

servers:
  - url: http://localhost:8000/api/v1

# ============================================================================
# AUTHENTICATION
# ============================================================================

paths:
  /auth/login:
    post:
      summary: Login with username/password
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                username: { type: string }
                password: { type: string }
      responses:
        200:
          description: Login successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  access_token: { type: string }
                  refresh_token: { type: string }
                  expires_in: { type: integer }

  /auth/refresh:
    post:
      summary: Refresh access token
      security: [BearerAuth: []]
      responses:
        200:
          description: New access token

# ============================================================================
# DASHBOARD
# ============================================================================

  /dashboard/overview:
    get:
      summary: Get dashboard overview statistics
      security: [BearerAuth: []]
      responses:
        200:
          description: Dashboard statistics
          content:
            application/json:
              schema:
                type: object
                properties:
                  pipelines:
                    total: { type: integer }
                    running: { type: integer }
                    completed_today: { type: integer }
                  models:
                    total: { type: integer }
                    in_production: { type: integer }
                    in_staging: { type: integer }
                  drift:
                    features_drifted: { type: integer }
                    drift_ratio: { type: number }
                    last_check: { type: string, format: date-time }
                  experiments:
                    active: { type: integer }
                    completed_today: { type: integer }
                    total_trials: { type: integer }

  /dashboard/activity:
    get:
      summary: Get recent activity feed
      parameters:
        - name: limit
          in: query
          schema: { type: integer, default: 20 }
        - name: offset
          in: query
          schema: { type: integer, default: 0 }
      security: [BearerAuth: []]
      responses:
        200:
          description: Activity feed

  /dashboard/health:
    get:
      summary: Get system health status
      responses:
        200:
          description: Health check response

# ============================================================================
# PIPELINES
# ============================================================================

  /pipelines:
    get:
      summary: List pipelines
      parameters:
        - name: status
          in: query
          schema: { type: string, enum: [active, inactive, all] }
        - name: tag
          in: query
          schema: { type: string }
        - name: search
          in: query
          schema: { type: string }
        - name: sort_by
          in: query
          schema: { type: string, enum: [created_at, updated_at, name] }
        - name: sort_order
          in: query
          schema: { type: string, enum: [asc, desc] }
        - name: limit
          in: query
          schema: { type: integer, default: 20 }
        - name: offset
          in: query
          schema: { type: integer, default: 0 }
      security: [BearerAuth: []]
      responses:
        200:
          description: List of pipelines

    post:
      summary: Create new pipeline
      security: [BearerAuth: []]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [name]
              properties:
                name: { type: string, maxLength: 100 }
                description: { type: string }
                config: { type: object }
                tags: { type: array, items: { type: string } }
      responses:
        201:
          description: Pipeline created

  /pipelines/{pipeline_id}:
    get:
      summary: Get pipeline details
      parameters:
        - name: pipeline_id
          in: path
          required: true
          schema: { type: integer }
      security: [BearerAuth: []]
      responses:
        200:
          description: Pipeline details

    put:
      summary: Update pipeline
      security: [BearerAuth: []]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                name: { type: string }
                description: { type: string }
                config: { type: object }
                is_active: { type: boolean }
      responses:
        200:
          description: Pipeline updated

    delete:
      summary: Delete pipeline
      security: [BearerAuth: []]
      responses:
        204:
          description: Pipeline deleted

  /pipelines/{pipeline_id}/runs:
    get:
      summary: List pipeline runs
      parameters:
        - name: pipeline_id
          in: path
          required: true
          schema: { type: integer }
        - name: status
          in: query
          schema: { type: string, enum: [pending, running, success, failed] }
        - name: limit
          in: query
          schema: { type: integer, default: 20 }
      security: [BearerAuth: []]
      responses:
        200:
          description: List of runs

    post:
      summary: Trigger new run
      security: [BearerAuth: []]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                config_override: { type: object }
                parameters: { type: object }
      responses:
        201:
          description: Run triggered

# ============================================================================
# RUNS
# ============================================================================

  /runs:
    get:
      summary: List all runs (with filtering)
      parameters:
        - name: pipeline_id
          in: query
          schema: { type: integer }
        - name: status
          in: query
          schema: { type: string }
        - name: started_after
          in: query
          schema: { type: string, format: date-time }
        - name: started_before
          in: query
          schema: { type: string, format: date-time }
      security: [BearerAuth: []]
      responses:
        200:
          description: List of runs

  /runs/{run_id}:
    get:
      summary: Get run details
      parameters:
        - name: run_id
          in: path
          required: true
          schema: { type: integer }
      security: [BearerAuth: []]
      responses:
        200:
          description: Run details with steps

    delete:
      summary: Cancel running run
      security: [BearerAuth: []]
      responses:
        200:
          description: Run cancelled

  /runs/{run_id}/logs:
    get:
      summary: Get run logs
      parameters:
        - name: run_id
          in: path
          required: true
          schema: { type: integer }
        - name: level
          in: query
          schema: { type: string, enum: [DEBUG, INFO, WARNING, ERROR] }
        - name: step
          in: query
          schema: { type: string }
        - name: tail
          in: query
          description: Number of recent lines to return
          schema: { type: integer, default: 100 }
      security: [BearerAuth: []]
      responses:
        200:
          description: Log entries

  /runs/{run_id}/artifacts:
    get:
      summary: List run artifacts
      security: [BearerAuth: []]
      responses:
        200:
          description: List of artifacts

  /runs/{run_id}/artifacts/{artifact_id}/download:
    get:
      summary: Download artifact
      security: [BearerAuth: []]
      responses:
        200:
          description: Artifact binary data

  /runs/{run_id}/metrics:
    get:
      summary: Get run metrics time-series
      security: [BearerAuth: []]
      responses:
        200:
          description: Metrics data

  /runs/{run_id}/compare/{other_run_id}:
    get:
      summary: Compare two runs
      security: [BearerAuth: []]
      responses:
        200:
          description: Comparison results

# ============================================================================
# MODEL REGISTRY
# ============================================================================

  /models:
    get:
      summary: List registered models
      parameters:
        - name: framework
          in: query
          schema: { type: string, enum: [sklearn, pytorch, tensorflow, xgboost] }
        - name: task_type
          in: query
          schema: { type: string, enum: [classification, regression, clustering] }
        - name: tag
          in: query
          schema: { type: string }
      security: [BearerAuth: []]
      responses:
        200:
          description: List of models

    post:
      summary: Register new model
      security: [BearerAuth: []]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [name]
              properties:
                name: { type: string }
                description: { type: string }
                framework: { type: string }
                task_type: { type: string }
                tags: { type: array, items: { type: string } }
      responses:
        201:
          description: Model created

  /models/{model_id}:
    get:
      summary: Get model details
      security: [BearerAuth: []]
      responses:
        200:
          description: Model with version summary

    put:
      summary: Update model
      security: [BearerAuth: []]
      responses:
        200:
          description: Model updated

    delete:
      summary: Delete model
      security: [BearerAuth: []]
      responses:
        204:
          description: Model deleted

  /models/{model_id}/versions:
    get:
      summary: List model versions
      security: [BearerAuth: []]
      responses:
        200:
          description: List of versions

    post:
      summary: Create new version
      security: [BearerAuth: []]
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                run_id: { type: integer }
                artifact_id: { type: integer }
                description: { type: string }
                metrics: { type: object }
                stage: { type: string, enum: [pending, staging, production] }
      responses:
        201:
          description: Version created

  /models/{model_id}/versions/{version}:
    get:
      summary: Get version details
      security: [BearerAuth: []]
      responses:
        200:
          description: Version with artifacts

  /models/{model_id}/versions/{version}/stage:
    put:
      summary: Update model stage
      security: [BearerAuth: []]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [stage]
              properties:
                stage: { type: string, enum: [pending, staging, production, archived] }
                comment: { type: string }
      responses:
        200:
          description: Stage updated

  /models/compare:
    post:
      summary: Compare two model versions
      security: [BearerAuth: []]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [v1_id, v2_id]
              properties:
                v1_id: { type: integer }
                v2_id: { type: integer }
                test_dataset: { type: string }
      responses:
        200:
          description: Comparison report

# ============================================================================
# EXPERIMENTS
# ============================================================================

  /experiments:
    get:
      summary: List experiments
      security: [BearerAuth: []]
      responses:
        200:
          description: List of experiments

    post:
      summary: Create experiment
      security: [BearerAuth: []]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [name, search_space]
              properties:
                name: { type: string }
                description: { type: string }
                search_space: { type: object }
                direction: { type: string, enum: [minimize, maximize] }
                metric_name: { type: string }
                n_trials: { type: integer, default: 100 }
      responses:
        201:
          description: Experiment created

  /experiments/{experiment_id}:
    get:
      summary: Get experiment details
      security: [BearerAuth: []]
      responses:
        200:
          description: Experiment with trials

    delete:
      summary: Stop/delete experiment
      security: [BearerAuth: []]
      responses:
        204:
          description: Experiment stopped

  /experiments/{experiment_id}/trials:
    get:
      summary: List trials
      security: [BearerAuth: []]
      responses:
        200:
          description: List of trials

  /experiments/{experiment_id}/trials/{trial_id}:
    get:
      summary: Get trial details
      security: [BearerAuth: []]
      responses:
        200:
          description: Trial with metrics

  /experiments/{experiment_id}/visualize:
    get:
      summary: Get visualization data
      security: [BearerAuth: []]
      responses:
        200:
          description: Parallel coordinates, importance, etc.

# ============================================================================
# DRIFT DETECTION
# ============================================================================

  /drift:
    get:
      summary: List drift reports
      parameters:
        - name: model_id
          in: query
          schema: { type: integer }
        - name: drift_detected
          in: query
          schema: { type: boolean }
      security: [BearerAuth: []]
      responses:
        200:
          description: List of drift reports

    post:
      summary: Trigger drift detection
      security: [BearerAuth: []]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [model_version_id, current_dataset]
              properties:
                model_version_id: { type: integer }
                reference_dataset: { type: string }
                current_dataset: { type: string }
                method: { type: string, enum: [psi, ks, chi2, wasserstein, all] }
                threshold: { type: number }
      responses:
        202:
          description: Drift detection started

  /drift/{report_id}:
    get:
      summary: Get drift report
      security: [BearerAuth: []]
      responses:
        200:
          description: Full drift report

  /drift/latest:
    get:
      summary: Get latest drift status
      parameters:
        - name: model_id
          in: query
          schema: { type: integer }
      security: [BearerAuth: []]
      responses:
        200:
          description: Latest drift status

  /drift/metrics:
    get:
      summary: Get drift metrics time-series
      security: [BearerAuth: []]
      responses:
        200:
          description: Drift metrics over time

# ============================================================================
# ALERTS
# ============================================================================

  /alerts:
    get:
      summary: List alerts
      parameters:
        - name: status
          in: query
          schema: { type: string, enum: [open, acknowledged, resolved, all] }
        - name: severity
          in: query
          schema: { type: string, enum: [info, warning, critical] }
        - name: limit
          in: query
          schema: { type: integer, default: 50 }
      security: [BearerAuth: []]
      responses:
        200:
          description: List of alerts

  /alerts/{alert_id}/acknowledge:
    post:
      summary: Acknowledge alert
      security: [BearerAuth: []]
      responses:
        200:
          description: Alert acknowledged

  /alerts/{alert_id}/resolve:
    post:
      summary: Resolve alert
      security: [BearerAuth: []]
      responses:
        200:
          description: Alert resolved

  /alert-rules:
    get:
      summary: List alert rules
      security: [BearerAuth: []]
      responses:
        200:
          description: List of rules

    post:
      summary: Create alert rule
      security: [BearerAuth: []]
      responses:
        201:
          description: Rule created

# ============================================================================
# WEBSOCKET
# ============================================================================

websockets:
  /ws/v1/runs/{run_id}:
    description: |
      Subscribe to real-time run updates.
      
      Events sent:
      - run.started: { run_id, timestamp }
      - run.step.started: { run_id, step_name, step_index }
      - run.step.completed: { run_id, step_name, metrics }
      - run.log: { run_id, level, message, timestamp }
      - run.metric: { run_id, name, value, step }
      - run.completed: { run_id, status, metrics }
      - run.failed: { run_id, error }

  /ws/v1/dashboard:
    description: |
      Subscribe to dashboard broadcasts.
      
      Events sent:
      - dashboard.metrics: { metrics: [...], timestamp }
      - dashboard.activity: { activity: [...] }
      - dashboard.alert: { alert: {...} }
      - system.health: { status, services: {...} }

  /ws/v1/experiments/{experiment_id}:
    description: |
      Subscribe to experiment updates.
      
      Events sent:
      - experiment.trial.started: { trial_id, params }
      - experiment.trial.completed: { trial_id, value }
      - experiment.progress: { completed, total, best_value }
      - experiment.completed: { experiment_id, best_trial }

securitySchemes:
  BearerAuth:
    type: http
    scheme: bearer
    bearerFormat: JWT
```

---

## 🎨 Frontend Architecture

### Technology Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND TECH STACK                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Framework: React 18 + TypeScript                       │   │
│  │  Build Tool: Vite                                       │   │
│  │  Package Manager: pnpm (preferred) or npm              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│  ┌───────────────────────┼─────────────────────────────────┐   │
│  │                       │                                  │   │
│  │  State Management     │  Server State                   │   │
│  │  ┌───────────────┐   │  ┌───────────────┐             │   │
│  │  │ Zustand       │   │  │ React Query   │             │   │
│  │  │ - UI state    │   │  │ - API calls   │             │   │
│  │  │ - Auth state  │   │  │ - Caching     │             │   │
│  │  │ - Theme       │   │  │ - Real-time   │             │   │
│  │  └───────────────┘   │  └───────────────┘             │   │
│  │                       │                                  │   │
│  │  Routing: React Router v6                              │   │
│  │  - Code splitting                                      │   │
│  │  - Protected routes                                    │   │
│  │  - Route-based data loading                            │   │
│  │                       │                                  │   │
│  │  Styling: Tailwind CSS 3.4                             │   │
│  │  - Custom design system                                  │   │
│  │  - Dark mode support                                     │   │
│  │  - Responsive utilities                                  │   │
│  └───────────────────────┼─────────────────────────────────┘   │
│                          │                                      │
│  ┌───────────────────────▼─────────────────────────────────┐   │
│  │  Data Visualization                                     │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────┐  │   │
│  │  │ Chart.js      │  │ D3.js         │  │ AG Grid   │  │   │
│  │  │ - Line charts │  │ - Custom viz  │  │ - Tables  │  │   │
│  │  │ - Bar charts  │  │ - DAG viz     │  │ - Sorting │  │   │
│  │  │ - Pie charts  │  │ - Heatmaps    │  │ - Filters │  │   │
│  │  └───────────────┘  └───────────────┘  └───────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│  ┌───────────────────────▼─────────────────────────────────┐   │
│  │  Real-time Communication                                │   │
│  │  ┌───────────────┐                                      │   │
│  │  │ Socket.io     │  - Bidirectional events              │   │
│  │  │ - Client      │  - Auto-reconnection                 │   │
│  │  │ - Room-based  │  - Fallback polling                  │   │
│  │  └───────────────┘                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│  ┌───────────────────────▼─────────────────────────────────┐   │
│  │  UI Components                                          │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────┐  │   │
│  │  │ Shadcn/ui     │  │ Radix UI      │  │ Lucide    │  │   │
│  │  │ - Base comps  │  │ - Primitives  │  │ - Icons   │  │   │
│  │  │ - Themes      │  │ - A11y        │  │           │  │   │
│  │  └───────────────┘  └───────────────┘  └───────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── .env                          # Environment variables
├── .env.example
│
├── src/
│   ├── main.tsx                  # App entry point
│   ├── App.tsx                   # Root component
│   ├── routes.tsx                # Route definitions
│   │
│   ├── api/                      # API layer
│   │   ├── client.ts             # Axios/fetch instance
│   │   ├── endpoints/
│   │   │   ├── pipelines.ts
│   │   │   ├── runs.ts
│   │   │   ├── models.ts
│   │   │   ├── experiments.ts
│   │   │   ├── drift.ts
│   │   │   └── alerts.ts
│   │   ├── hooks/                # React Query hooks
│   │   │   ├── usePipelines.ts
│   │   │   ├── useRuns.ts
│   │   │   ├── useModels.ts
│   │   │   └── ...
│   │   └── websocket.ts          # Socket.io client
│   │
│   ├── components/               # Shared components
│   │   ├── ui/                   # Shadcn/ui primitives
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── table.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── tooltip.tsx
│   │   │   └── ...
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── PageLayout.tsx
│   │   │   └── Breadcrumbs.tsx
│   │   ├── charts/
│   │   │   ├── LineChart.tsx
│   │   │   ├── BarChart.tsx
│   │   │   ├── PieChart.tsx
│   │   │   ├── HeatmapChart.tsx
│   │   │   └── DashboardCharts.tsx
│   │   ├── tables/
│   │   │   ├── DataTable.tsx     # Reusable AG Grid wrapper
│   │   │   ├── PipelineTable.tsx
│   │   │   ├── RunsTable.tsx
│   │   │   └── ModelsTable.tsx
│   │   ├── visualizations/
│   │   │   ├── PipelineDAG.tsx   # D3.js pipeline graph
│   │   │   ├── ConfusionMatrix.tsx
│   │   │   ├── SHAPPlot.tsx      # Explainability plots
│   │   │   ├── FeatureImportance.tsx
│   │   │   └── DriftChart.tsx
│   │   ├── feedback/
│   │   │   ├── LoadingSpinner.tsx
│   │   │   ├── ErrorBoundary.tsx
│   │   │   ├── Toast.tsx
│   │   │   ├── AlertBanner.tsx
│   │   │   └── EmptyState.tsx
│   │   └── forms/
│   │       ├── PipelineForm.tsx
│   │       ├── AlertRuleForm.tsx
│   │       └── ModelPromoteForm.tsx
│   │
│   ├── pages/                    # Page components
│   │   ├── auth/
│   │   │   ├── Login.tsx
│   │   │   └── Callback.tsx
│   │   ├── dashboard/
│   │   │   └── Dashboard.tsx
│   │   ├── pipelines/
│   │   │   ├── PipelineList.tsx
│   │   │   ├── PipelineDetail.tsx
│   │   │   └── PipelineEditor.tsx
│   │   ├── runs/
│   │   │   ├── RunList.tsx
│   │   │   ├── RunDetail.tsx
│   │   │   └── RunLogs.tsx
│   │   ├── models/
│   │   │   ├── ModelList.tsx
│   │   │   ├── ModelDetail.tsx
│   │   │   ├── ModelVersion.tsx
│   │   │   └── ModelCompare.tsx
│   │   ├── experiments/
│   │   │   ├── ExperimentList.tsx
│   │   │   ├── ExperimentDetail.tsx
│   │   │   └── ExperimentVisualize.tsx
│   │   ├── drift/
│   │   │   ├── DriftList.tsx
│   │   │   └── DriftReport.tsx
│   │   ├── explainability/
│   │   │   ├── Explainability.tsx
│   │   │   └── FeatureImportance.tsx
│   │   └── settings/
│   │       ├── Settings.tsx
│   │       ├── AlertRules.tsx
│   │       └── TeamManagement.tsx
│   │
│   ├── hooks/                    # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useTheme.ts
│   │   ├── useWebSocket.ts
│   │   ├── useRealtimeRuns.ts
│   │   └── usePagination.ts
│   │
│   ├── stores/                   # Zustand stores
│   │   ├── authStore.ts
│   │   ├── uiStore.ts
│   │   └── dashboardStore.ts
│   │
│   ├── types/                    # TypeScript types
│   │   ├── api.ts
│   │   ├── models.ts
│   │   ├── pipeline.ts
│   │   ├── run.ts
│   │   ├── experiment.ts
│   │   ├── drift.ts
│   │   └── index.ts
│   │
│   ├── utils/                    # Utilities
│   │   ├── formatters.ts         # Date, number formatting
│   │   ├── validators.ts
│   │   ├── constants.ts
│   │   └── helpers.ts
│   │
│   ├── styles/
│   │   ├── globals.css
│   │   └── tailwind.css
│   │
│   └── test/
│       ├── setup.ts
│       └── mocks/
│
├── public/
│   └── ...                       # Static assets
│
└── cypress/                      # E2E tests
    └── ...
```

### Key Component Designs

#### 1. PipelineDAG Component (D3.js Pipeline Visualization)

```typescript
// src/components/visualizations/PipelineDAG.tsx
import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { Pipeline, RunStep } from '@/types';

interface PipelineDAGProps {
  pipeline: Pipeline;
  runSteps?: RunStep[];  // Optional: for showing current run progress
  onNodeClick?: (step: RunStep) => void;
  height?: number;
}

export const PipelineDAG: React.FC<PipelineDAGProps> = ({
  pipeline,
  runSteps,
  onNodeClick,
  height = 400
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  
  useEffect(() => {
    if (!svgRef.current) return;
    
    // D3.js DAG rendering logic
    // 1. Parse pipeline config to extract steps and dependencies
    // 2. Create D3 force simulation or hierarchical layout
    // 3. Render nodes (circles) with status colors
    // 4. Render edges (arrows) connecting dependencies
    // 5. Add interactivity (hover, click)
    
    const svg = d3.select(svgRef.current);
    // ... rendering logic
    
  }, [pipeline, runSteps]);
  
  return (
    <div className="pipeline-dag" style={{ height }}>
      <svg ref={svgRef} width="100%" height="100%" />
    </div>
  );
};
```

#### 2. Real-time Log Viewer

```typescript
// src/components/tables/LogViewer.tsx
import React, { useEffect, useRef } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useVirtualizer } from '@tanstack/react-virtual';

interface LogEntry {
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  message: string;
  source: string;
}

interface LogViewerProps {
  runId: number;
  initialLogs?: LogEntry[];
}

const LEVEL_COLORS = {
  DEBUG: 'text-gray-500',
  INFO: 'text-blue-600',
  WARNING: 'text-amber-600',
  ERROR: 'text-red-600'
};

export const LogViewer: React.FC<LogViewerProps> = ({ 
  runId, 
  initialLogs = [] 
}) => {
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  
  // WebSocket for real-time logs
  const { subscribe } = useWebSocket();
  
  useEffect(() => {
    const unsubscribe = subscribe(`run:${runId}:log`, (entry: LogEntry) => {
      setLogs(prev => [...prev, entry]);
      if (autoScroll && scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    });
    
    return unsubscribe;
  }, [runId, subscribe, autoScroll]);
  
  // Virtual list for performance with large logs
  const rowVirtualizer = useVirtualizer({
    count: logs.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 24,
    overscan: 20
  });
  
  return (
    <div className="log-viewer flex flex-col h-full">
      <div className="flex items-center justify-between p-2 border-b">
        <span className="text-sm text-gray-600">
          {logs.length.toLocaleString()} lines
        </span>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          Auto-scroll
        </label>
      </div>
      
      <div 
        ref={scrollRef}
        className="flex-1 overflow-auto font-mono text-sm bg-gray-900"
      >
        <div style={{ height: `${rowVirtualizer.getTotalSize()}px` }}>
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const log = logs[virtualRow.index];
            return (
              <div
                key={virtualRow.key}
                style={{ height: `${virtualRow.size}px`, transform: `translateY(${virtualRow.start}px)` }}
                className="flex items-start gap-3 px-3 py-1 hover:bg-gray-800"
              >
                <span className="text-gray-500 text-xs whitespace-nowrap">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <span className={`font-semibold ${LEVEL_COLORS[log.level]}`}>
                  {log.level.padEnd(7)}
                </span>
                <span className="text-gray-300">
                  {log.message}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
```

#### 3. Model Comparison Chart

```typescript
// src/components/charts/ModelComparisonChart.tsx
import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';
import { ModelComparison } from '@/types';

interface ComparisonChartProps {
  comparison: ModelComparison;
  metrics: string[];
}

export const ModelComparisonChart: React.FC<ComparisonChartProps> = ({
  comparison,
  metrics
}) => {
  const data = metrics.map(metric => ({
    metric,
    v1: comparison.v1_metrics[metric],
    v2: comparison.v2_metrics[metric],
    diff: comparison.differences[metric]
  }));
  
  return (
    <div className="bg-white rounded-lg border p-6">
      <h3 className="text-lg font-semibold mb-4">
        Model Comparison: {comparison.v1_version} vs {comparison.v2_version}
      </h3>
      
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="metric" />
          <YAxis domain={[0, 1]} />
          <Tooltip />
          <Legend />
          <ReferenceLine y={0.5} stroke="#666" />
          <Bar 
            dataKey="v1" 
            name={`v${comparison.v1_version}`} 
            fill="#3B82F6" 
          />
          <Bar 
            dataKey="v2" 
            name={`v${comparison.v2_version}`} 
            fill="#10B981" 
          />
        </BarChart>
      </ResponsiveContainer>
      
      <div className="mt-4 grid grid-cols-2 gap-4">
        <div className="text-center">
          <p className="text-sm text-gray-500">Winner</p>
          <p className="text-lg font-semibold text-blue-600">
            {comparison.winner === comparison.v1_id ? 'v1' : 'v2'}
          </p>
        </div>
        <div className="text-center">
          <p className="text-sm text-gray-500">Improvement</p>
          <p className={`text-lg font-semibold ${
            comparison.is_improvement ? 'text-green-600' : 'text-red-600'
          }`}>
            {comparison.improvement_percentage}%
          </p>
        </div>
      </div>
    </div>
  );
};
```

---

## 🔌 Backend Services Implementation

### Service Layer Architecture

```python
# backend/app/services/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')

class BaseService(ABC, Generic[T]):
    """Base service class with common CRUD operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    @abstractmethod
    async def get(self, id: int) -> Optional[T]:
        pass
    
    @abstractmethod
    async def list(self, skip: int = 0, limit: int = 100, **filters) -> List[T]:
        pass
    
    @abstractmethod
    async def create(self, data: dict) -> T:
        pass
    
    @abstractmethod
    async def update(self, id: int, data: dict) -> Optional[T]:
        pass
    
    @abstractmethod
    async def delete(self, id: int) -> bool:
        pass
```

### Pipeline Service

```python
# backend/app/services/pipeline_service.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Pipeline, Run, RunStatus, RunStep
from app.services.base import BaseService
from app.core.events import event_emitter
from app.core.runner import PipelineRunner


class PipelineService(BaseService[Pipeline]):
    """Service for managing pipelines and their execution"""
    
    async def get(self, pipeline_id: int) -> Optional[Pipeline]:
        """Get pipeline by ID with related data"""
        result = await self.db.execute(
            select(Pipeline)
            .options(selectinload(Pipeline.runs))
            .where(Pipeline.id == pipeline_id)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> tuple[List[Pipeline], int]:
        """List pipelines with filtering and pagination"""
        
        query = select(Pipeline)
        count_query = select(func.count(Pipeline.id))
        
        # Apply filters
        if status:
            is_active = status == 'active'
            query = query.where(Pipeline.is_active == is_active)
            count_query = count_query.where(Pipeline.is_active == is_active)
        
        if search:
            search_filter = Pipeline.name.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Sorting
        sort_column = getattr(Pipeline, sort_by, Pipeline.created_at)
        if sort_order == "desc":
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
        # Execute
        result = await self.db.execute(query)
        total_result = await self.db.execute(count_query)
        
        pipelines = result.scalars().all()
        total = total_result.scalar()
        
        return list(pipelines), total
    
    async def create(self, data: Dict[str, Any], user_id: int) -> Pipeline:
        """Create new pipeline"""
        pipeline = Pipeline(
            name=data['name'],
            description=data.get('description'),
            config=data.get('config', {}),
            created_by=user_id,
            tags=data.get('tags', [])
        )
        
        self.db.add(pipeline)
        await self.db.commit()
        await self.db.refresh(pipeline)
        
        await event_emitter.emit("pipeline.created", {
            "pipeline_id": pipeline.id,
            "name": pipeline.name,
            "user_id": user_id
        })
        
        return pipeline
    
    async def trigger_run(
        self,
        pipeline_id: int,
        config_override: Optional[Dict] = None,
        parameters: Optional[Dict] = None,
        triggered_by: str = "manual"
    ) -> Run:
        """Trigger a new pipeline run"""
        
        pipeline = await self.get(pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline {pipeline_id} not found")
        
        # Get next run number
        result = await self.db.execute(
            select(func.max(Run.run_number))
            .where(Run.pipeline_id == pipeline_id)
        )
        next_run_number = (result.scalar() or 0) + 1
        
        # Create run record
        run = Run(
            pipeline_id=pipeline_id,
            status=RunStatus.PENDING,
            run_number=next_run_number,
            config_snapshot=config_override or pipeline.config,
            triggered_by=triggered_by,
            parameters=parameters or {}
        )
        
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        
        # Start execution in background
        # (In production, this would be a Celery task or Kubernetes Job)
        PipelineRunner.queue_run(run.id, config_override, parameters)
        
        await event_emitter.emit("run.triggered", {
            "run_id": run.id,
            "pipeline_id": pipeline_id,
            "run_number": next_run_number
        })
        
        return run


class RunService:
    """Service for managing pipeline runs"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_run_details(self, run_id: int) -> Optional[Run]:
        """Get run with all related data"""
        result = await self.db.execute(
            select(Run)
            .options(
                selectinload(Run.steps),
                selectinload(Run.artifacts),
                selectinload(Run.pipeline)
            )
            .where(Run.id == run_id)
        )
        return result.scalar_one_or_none()
    
    async def get_run_logs(
        self,
        run_id: int,
        level: Optional[str] = None,
        step: Optional[str] = None,
        tail: int = 100
    ) -> List[Dict]:
        """Get run logs with filtering"""
        from app.db.models import LogEntry
        
        query = select(LogEntry).where(LogEntry.run_id == run_id)
        
        if level:
            query = query.where(LogEntry.level == level.upper())
        if step:
            query = query.where(LogEntry.source == step)
        
        query = query.order_by(LogEntry.timestamp.desc()).limit(tail)
        
        result = await self.db.execute(query)
        logs = result.scalars().all()
        
        return [
            {
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "message": log.message,
                "source": log.source,
                "extra": log.extra
            }
            for log in reversed(logs)  # Return in chronological order
        ]
    
    async def cancel_run(self, run_id: int) -> bool:
        """Cancel a running pipeline"""
        run = await self.get_run_details(run_id)
        if not run or run.status != RunStatus.RUNNING:
            return False
        
        # Signal cancellation to runner
        await PipelineRunner.cancel_run(run_id)
        
        run.status = RunStatus.CANCELLED
        run.completed_at = datetime.utcnow()
        await self.db.commit()
        
        await event_emitter.emit("run.cancelled", {"run_id": run_id})
        return True
```

### Model Registry Service

```python
# backend/app/services/model_service.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Model, ModelVersion, ModelStage, ModelComparison, ModelArtifact
from app.core.storage import StorageBackend
from app.core.events import event_emitter


class ModelService:
    """Service for model registry operations"""
    
    def __init__(self, db: AsyncSession, storage: StorageBackend):
        self.db = db
        self.storage = storage
    
    async def get_model(self, model_id: int) -> Optional[Model]:
        """Get model with version summary"""
        result = await self.db.execute(
            select(Model)
            .options(selectinload(Model.versions))
            .where(Model.id == model_id)
        )
        return result.scalar_one_or_none()
    
    async def create_version(
        self,
        model_id: int,
        run_id: int,
        artifact_id: int,
        description: Optional[str] = None,
        metrics: Optional[Dict] = None,
        tags: Optional[List[str]] = None
    ) -> ModelVersion:
        """Create new model version"""
        
        model = await self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        # Get next version number
        next_version = model.latest_version + 1
        
        version = ModelVersion(
            model_id=model_id,
            version=next_version,
            run_id=run_id,
            artifact_id=artifact_id,
            description=description,
            metrics=metrics or {},
            tags=tags or [],
            stage=ModelStage.PENDING
        )
        
        self.db.add(version)
        
        # Update model
        model.latest_version = next_version
        
        await self.db.commit()
        await self.db.refresh(version)
        
        await event_emitter.emit("model.version_created", {
            "model_id": model_id,
            "version": next_version,
            "metrics": metrics
        })
        
        return version
    
    async def promote_version(
        self,
        model_id: int,
        version: int,
        target_stage: ModelStage,
        comment: Optional[str] = None
    ) -> ModelVersion:
        """Promote model version to new stage"""
        
        result = await self.db.execute(
            select(ModelVersion)
            .where(
                ModelVersion.model_id == model_id,
                ModelVersion.version == version
            )
        )
        model_version = result.scalar_one_or_none()
        
        if not model_version:
            raise ValueError(f"Version {version} not found for model {model_id}")
        
        # Handle production promotion
        if target_stage == ModelStage.PRODUCTION:
            # Archive current production version
            await self._archive_current_production(model_id)
            
            # Update model's production version
            model = await self.get_model(model_id)
            model.production_version = version
        
        model_version.stage = target_stage
        
        await self.db.commit()
        await self.db.refresh(model_version)
        
        await event_emitter.emit("model.promoted", {
            "model_id": model_id,
            "version": version,
            "stage": target_stage.value,
            "comment": comment
        })
        
        return model_version
    
    async def _archive_current_production(self, model_id: int):
        """Archive the current production version"""
        model = await self.get_model(model_id)
        if model and model.production_version:
            result = await self.db.execute(
                select(ModelVersion)
                .where(
                    ModelVersion.model_id == model_id,
                    ModelVersion.version == model.production_version
                )
            )
            old_version = result.scalar_one_or_none()
            if old_version:
                old_version.stage = ModelStage.ARCHIVED
    
    async def compare_versions(
        self,
        v1_id: int,
        v2_id: int,
        test_dataset: Optional[str] = None
    ) -> ModelComparison:
        """Compare two model versions"""
        
        # Fetch both versions
        result = await self.db.execute(
            select(ModelVersion)
            .where(ModelVersion.id.in_([v1_id, v2_id]))
        )
        versions = result.scalars().all()
        
        if len(versions) != 2:
            raise ValueError("Both versions must exist")
        
        v1, v2 = versions
        
        # Calculate metric differences
        metric_diffs = {}
        all_metrics = set(v1.metrics.keys()) | set(v2.metrics.keys())
        
        for metric in all_metrics:
            v1_val = v1.metrics.get(metric, 0)
            v2_val = v2.metrics.get(metric, 0)
            metric_diffs[metric] = round(v2_val - v1_val, 6)
        
        # Determine winner
        # (In production, this would use a configurable strategy)
        primary_metric = 'accuracy'  # Could be configurable
        is_improvement = metric_diffs.get(primary_metric, 0) > 0
        winner_id = v2_id if is_improvement else v1_id
        
        # Generate report
        report = self._generate_comparison_report(v1, v2, metric_diffs)
        
        comparison = ModelComparison(
            v1_id=v1_id,
            v2_id=v2_id,
            metric_differences=metric_diffs,
            is_improvement=is_improvement,
            winner_id=winner_id,
            report_markdown=report['markdown'],
            report_html=report['html']
        )
        
        self.db.add(comparison)
        await self.db.commit()
        await self.db.refresh(comparison)
        
        return comparison
    
    def _generate_comparison_report(
        self,
        v1: ModelVersion,
        v2: ModelVersion,
        differences: Dict[str, float]
    ) -> Dict[str, str]:
        """Generate comparison report in multiple formats"""
        
        markdown = f"""# Model Comparison Report

## Versions Compared
- **Baseline (v{v1.version})**: ID {v1.id}
- **Candidate (v{v2.version})**: ID {v2.id}

## Metrics Comparison

| Metric | v{v1.version} | v{v2.version} | Difference | Status |
|--------|---------------|---------------|------------|--------|
"""
        
        for metric, diff in differences.items():
            v1_val = v1.metrics.get(metric, 'N/A')
            v2_val = v2.metrics.get(metric, 'N/A')
            status = "✅ Better" if diff > 0 else "❌ Worse" if diff < 0 else "➖ Equal"
            markdown += f"| {metric} | {v1_val} | {v2_val} | {diff:+.4f} | {status} |\n"
        
        markdown += f"\n## Summary\n\n"
        markdown += f"**Winner**: Version {v2.version if differences.get('accuracy', 0) > 0 else v1.version}\n"
        markdown += f"**Overall Improvement**: {'Yes' if any(d > 0 for d in differences.values()) else 'No'}\n"
        
        html = f"""
        <html>
        <body>
            <h1>Model Comparison Report</h1>
            <h2>Versions Compared</h2>
            <p>Baseline (v{v1.version}): ID {v1.id}</p>
            <p>Candidate (v{v2.version}): ID {v2.id}</p>
            {self._render_comparison_table(v1, v2, differences)}
        </body>
        </html>
        """
        
        return {"markdown": markdown, "html": html}
```

### WebSocket Handler

```python
# backend/app/api/v1/endpoints/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Set
import json
import asyncio

from app.core.auth import get_current_user_ws
from app.core.redis import redis_client

router = APIRouter()

# Connection managers for different rooms
class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, room: str):
        await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = set()
        self.active_connections[room].add(websocket)
    
    def disconnect(self, websocket: WebSocket, room: str):
        if room in self.active_connections:
            self.active_connections[room].discard(websocket)
    
    async def broadcast(self, room: str, message: dict):
        """Broadcast message to all connections in room"""
        if room not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[room]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            self.active_connections[room].discard(conn)


manager = ConnectionManager()


@router.websocket("/ws/v1/runs/{run_id}")
async def run_websocket(
    websocket: WebSocket,
    run_id: int,
    token: str  # Passed as query param for WebSocket auth
):
    """WebSocket for run updates"""
    room = f"run:{run_id}"
    await manager.connect(websocket, room)
    
    try:
        # Subscribe to Redis pub/sub for this run
        pubsub = redis_client.pubsub()
        pubsub.subscribe(f"run:{run_id}")
        
        # Forward messages from Redis to WebSocket
        while True:
            message = pubsub.get_message(timeout=1.0)
            if message and message['type'] == 'message':
                data = json.loads(message['data'])
                await websocket.send_json(data)
            
            # Keep connection alive
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
            except asyncio.TimeoutError:
                pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, room)
        pubsub.unsubscribe(f"run:{run_id}")


@router.websocket("/ws/v1/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket for dashboard broadcasts"""
    await manager.connect(websocket, "dashboard")
    
    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe("dashboard")
        
        while True:
            message = pubsub.get_message(timeout=1.0)
            if message and message['type'] == 'message':
                data = json.loads(message['data'])
                await websocket.send_json(data)
            
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
            except asyncio.TimeoutError:
                pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, "dashboard")
        pubsub.unsubscribe("dashboard")


# Event publisher that writes to Redis
async def publish_event(channel: str, event_type: str, data: dict):
    """Publish event to Redis for WebSocket distribution"""
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    redis_client.publish(channel, json.dumps(message))
```

---

## 📊 Dashboard Pages Design

### 1. Dashboard Overview Page

```typescript
// frontend/src/pages/dashboard/Dashboard.tsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { DashboardStats } from '@/components/charts/DashboardStats';
import { ActivityFeed } from '@/components/feedback/ActivityFeed';
import { useRealtimeDashboard } from '@/hooks/useWebSocket';
import { dashboardApi } from '@/api/endpoints/dashboard';

const Dashboard: React.FC = () => {
  // Fetch initial stats
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: () => dashboardApi.getOverview(),
    refetchInterval: 30000  // Refetch every 30s
  });
  
  // Subscribe to real-time updates
  useRealtimeDashboard();
  
  if (isLoading) return <DashboardSkeleton />;
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Real-time ML pipeline monitoring and insights
          </p>
        </div>
        <div className="flex gap-2">
          <QuickActions />
        </div>
      </div>
      
      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Pipelines"
          value={stats?.pipelines.total}
          change={{ value: 12, trend: 'up' }}
          icon="pipeline"
          status={{ running: stats?.pipelines.running }}
        />
        <StatCard
          title="Models in Production"
          value={stats?.models.in_production}
          change={{ value: 3, trend: 'up' }}
          icon="model"
          subtext={`${stats?.models.in_staging} in staging`}
        />
        <StatCard
          title="Drift Alerts"
          value={stats?.drift.features_drifted}
          alert={stats?.drift.drift_ratio > 0.1}
          icon="alert"
        />
        <StatCard
          title="Active Experiments"
          value={stats?.experiments.active}
          icon="experiment"
          subtext={`${stats?.experiments.total_trials} trials today`}
        />
      </div>
      
      {/* Charts & Activity */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Pipeline Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <DashboardCharts />
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <ActivityFeed />
          </CardContent>
        </Card>
      </div>
      
      {/* Active Pipelines Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Active Pipelines</CardTitle>
          <Button variant="outline" size="sm">View All</Button>
        </CardHeader>
        <CardContent>
          <ActivePipelinesTable />
        </CardContent>
      </Card>
    </div>
  );
};
```

### 2. Pipeline Detail Page

```typescript
// frontend/src/pages/pipelines/PipelineDetail.tsx
import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PipelineDAG } from '@/components/visualizations/PipelineDAG';
import { RunsTable } from '@/components/tables/RunsTable';
import { RunLogs } from '@/pages/runs/RunLogs';
import { Button } from '@/components/ui/button';
import { pipelineApi } from '@/api/endpoints/pipelines';

const PipelineDetail: React.FC = () => {
  const { pipelineId } = useParams<{ pipelineId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  
  const { data: pipeline, isLoading } = useQuery({
    queryKey: ['pipeline', pipelineId],
    queryFn: () => pipelineApi.getById(Number(pipelineId))
  });
  
  const handleTriggerRun = async () => {
    const run = await pipelineApi.triggerRun(Number(pipelineId));
    navigate(`/runs/${run.id}`);
  };
  
  if (isLoading) return <PipelineDetailSkeleton />;
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">{pipeline?.name}</h1>
          <p className="text-muted-foreground mt-1">{pipeline?.description}</p>
          <div className="flex gap-2 mt-2">
            {pipeline?.tags.map(tag => (
              <Badge key={tag} variant="secondary">{tag}</Badge>
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(`/pipelines/${pipelineId}/edit`)}>
            <Pencil className="w-4 h-4 mr-2" />
            Edit
          </Button>
          <Button onClick={handleTriggerRun}>
            <Play className="w-4 h-4 mr-2" />
            Run Pipeline
          </Button>
        </div>
      </div>
      
      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="visualization">Visualization</TabsTrigger>
          <TabsTrigger value="runs">Runs ({pipeline?.runs.length})</TabsTrigger>
          <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>
        
        <TabsContent value="overview" className="space-y-4">
          <PipelineOverview pipeline={pipeline} />
        </TabsContent>
        
        <TabsContent value="visualization">
          <Card>
            <CardContent className="pt-6">
              <PipelineDAG 
                pipeline={pipeline} 
                height={500}
              />
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="runs">
          <RunsTable pipelineId={Number(pipelineId)} />
        </TabsContent>
        
        <TabsContent value="artifacts">
          <ArtifactBrowser pipelineId={Number(pipelineId)} />
        </TabsContent>
      </Tabs>
    </div>
  );
};
```

---

## 🐳 Deployment Configuration

### Docker Compose (Production)

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_WS_URL=ws://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://autopipe:${DB_PASSWORD}@postgres:5432/autopipe
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - LOG_LEVEL=INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./artifacts:/app/artifacts
    restart: unless-stopped

  # Database
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=autopipe
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=autopipe
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U autopipe"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Cache & Pub/Sub
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Vector database for logs (optional)
  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    restart: unless-stopped

  # Log aggregator
  kibana:
    image: kibana:8.11.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch
    restart: unless-stopped

  # Object storage (for model artifacts)
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=${MINIO_USER}
      - MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    restart: unless-stopped

  # Background task workers
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    command: celery -A app.tasks worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://autopipe:${DB_PASSWORD}@postgres:5432/autopipe
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  # Periodic tasks
  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    command: celery -A app.tasks beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://autopipe:${DB_PASSWORD}@postgres:5432/autopipe
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  # Reverse proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  elasticsearch_data:
  minio_data:
```

### Kubernetes Manifests

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: autopipe

---
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autopipe-backend
  namespace: autopipe
spec:
  replicas: 3
  selector:
    matchLabels:
      app: autopipe-backend
  template:
    metadata:
      labels:
        app: autopipe-backend
    spec:
      containers:
      - name: backend
        image: autopipe/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: autopipe-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: autopipe-config
              key: redis-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
# k8s/backend-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: autopipe-backend
  namespace: autopipe
spec:
  selector:
    app: autopipe-backend
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: autopipe-ingress
  namespace: autopipe
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - dashboard.autopipe.io
    secretName: autopipe-tls
  rules:
  - host: dashboard.autopipe.io
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: autopipe-backend
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: autopipe-frontend
            port:
              number: 3000
```

---

## 🧪 Testing Strategy

```
tests/
├── backend/
│   ├── unit/
│   │   ├── test_services/
│   │   ├── test_models/
│   │   └── test_utils/
│   ├── integration/
│   │   ├── test_api/
│   │   └── test_websocket/
│   ├── e2e/
│   │   └── test_full_pipeline.py
│   └── conftest.py
│
└── frontend/
    ├── unit/
    │   ├── components/
    │   ├── hooks/
    │   └── utils/
    ├── integration/
    │   └── api/
    └── e2e/
        ├── cypress/
        └── playwright/
```

---

## 📈 Monitoring & Observability

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'autopipe-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /api/v1/metrics
  
  - job_name: 'autopipe-worker'
    static_configs:
      - targets: ['celery-worker:8080']
```

Key metrics to track:
- API request latency (p50, p95, p99)
- Database query performance
- WebSocket connection count
- Pipeline execution time
- Model deployment frequency
- Drift detection frequency
- Error rates by endpoint

---

## 📝 Implementation Roadmap

### Phase 1: Core Dashboard (MVP) - Week 1-2
- [x] Basic HTML dashboard (already exists)
- [ ] FastAPI backend with database models
- [ ] React frontend setup with routing
- [ ] Authentication (JWT)
- [ ] Pipeline list and detail views
- [ ] Run execution and logs

### Phase 2: Model Registry - Week 3-4
- [ ] Model CRUD operations
- [ ] Version management
- [ ] Stage transitions
- [ ] Model comparison UI
- [ ] Artifact storage integration

### Phase 3: Real-time Features - Week 5-6
- [ ] WebSocket implementation
- [ ] Live run monitoring
- [ ] Activity feed
- [ ] Live log streaming
- [ ] Dashboard real-time updates

### Phase 4: Advanced Features - Week 7-8
- [ ] Experiment tracking with Optuna
- [ ] Drift detection dashboard
- [ ] Explainability visualizations
- [ ] Alert management
- [ ] Report generation

### Phase 5: Production Hardening - Week 9-10
- [ ] Docker production setup
- [ ] Kubernetes deployment
- [ ] Monitoring integration (Prometheus/Grafana)
- [ ] Performance optimization
- [ ] Security audit

---

## Summary

This design document provides a comprehensive blueprint for building a production-grade AutoPipe dashboard. The architecture includes:

1. **Scalable Backend** with FastAPI, SQLAlchemy, and Redis pub/sub
2. **Modern Frontend** with React, TypeScript, and Tailwind CSS
3. **Real-time Updates** via WebSocket for live monitoring
4. **Comprehensive Data Models** for the full ML lifecycle
5. **Production Deployment** with Docker Compose and Kubernetes
6. **Security** with JWT authentication and RBAC
7. **Observability** with structured logging and metrics

Next steps would be to implement the core backend API and database models first, then build out the React frontend to consume those endpoints.

---

## 🔴 Implementation Status (as of 2026-04-14)

> ⚠️ **OUTDATED STATUS**: This section was auto-updated to reflect the actual repository state. The `IMPLEMENTATION_STATUS.md` file inside `autopipe/dashboard/` is the canonical living status document — this section summarizes it for convenience.

### Overall Progress: ~45%

The dashboard is in **Phase 1–2** of the design. The project structure is fully scaffolded and core building blocks are in place. Significant gaps remain in service layer, auth, real-time, and production infra.

---

### ✅ Completed

#### Backend (FastAPI) — ~40% complete

**File inventory** (`autopipe/dashboard/backend/app/`):

| Path | Status | Notes |
|------|--------|-------|
| `main.py` | ✅ | FastAPI app entry point |
| `db/models.py` | ✅ | Full SQLAlchemy models (14 tables) |
| `db/session.py` | ✅ | Async session factory |
| `schemas/__init__.py` | ✅ | Complete Pydantic schemas (~530 lines) |
| `core/config.py` | ✅ | Settings via pydantic-settings |
| `core/events.py` | ✅ | Event emitter |
| `api/v1/router.py` | ✅ | API v1 router wiring |
| `api/v1/endpoints/pipelines.py` | ✅ | Pipeline CRUD endpoints |
| `api/v1/endpoints/runs.py` | ✅ | Run management endpoints |
| `api/v1/endpoints/models.py` | ✅ | Model registry endpoints |
| `api/v1/endpoints/experiments.py` | ✅ | Experiment tracking endpoints |
| `api/v1/endpoints/drift.py` | ✅ | Drift detection endpoints |
| `api/v1/endpoints/dashboard.py` | ✅ | Overview, activity, health, metrics |
| `api/v1/endpoints/websocket.py` | ✅ | WebSocket handlers |
| `requirements.txt` | ✅ | All dependencies pinned |
| `Dockerfile` | ✅ | Backend Docker image |
| `start.sh` | ✅ | Startup script |

**Database tables implemented** (all via SQLAlchemy async, using UUID primary keys):

```
✅ pipelines          ✅ runs              ✅ steps
✅ experiments        ✅ models            ✅ model_versions
✅ drift_reports      ✅ drift_alerts      ✅ artifacts
✅ users              ✅ dashboard_metrics ✅ activity_logs
```

**Missing / Not Started**:
- ❌ Service layer (`services/*.py`) — business logic embedded in endpoints
- ❌ Database migrations (Alembic) — no migration files
- ❌ Authentication — `core/auth.py` missing; JWT endpoints missing
- ❌ API key management endpoints
- ❌ Background task workers (Celery)
- ❌ Redis integration for pub/sub (imported but not connected)

#### Frontend (React) — ~30% complete

**File inventory** (`autopipe/dashboard/frontend/`):

| Path | Status | Notes |
|------|--------|-------|
| `package.json` | ✅ | All dependencies configured (Recharts, AG Grid, Socket.io, Radix UI, etc.) |
| `vite.config.ts` | ✅ | Build config |
| `tailwind.config.js` | ✅ | Tailwind + forms + typography plugins |
| `src/main.tsx` | ✅ | Entry point |
| `src/App.tsx` | ✅ | Root component |
| `src/routes.tsx` | ✅ | Route definitions |
| `src/api/client.ts` | ✅ | Axios instance |
| `src/api/endpoints/index.ts` | ✅ | Endpoint exports |
| `src/api/endpoints/drift.ts` | ✅ | Drift API client |
| `src/components/layout/Layout.tsx` | ✅ | App shell |
| `src/components/ui/index.ts` | ✅ | UI component exports |
| `src/pages/dashboard/Dashboard.tsx` | ⚠️ | Basic dashboard page (minimal content) |
| `src/stores/authStore.ts` | ⚠️ | Zustand auth store (skeleton) |
| `src/stores/uiStore.ts` | ⚠️ | Zustand UI store (skeleton) |
| `src/types/api.ts` | ⚠️ | Partial API types |
| `src/utils/helpers.ts` | ⚠️ | Minimal utilities |
| `src/styles/globals.css` | ✅ | Global styles |

**Missing / Not Started**:
- ❌ Auth/Login page
- ❌ Protected routes (route guards)
- ❌ Pipeline list & detail pages
- ❌ Run list, detail & log viewer pages
- ❌ Model registry pages
- ❌ Experiment tracking pages
- ❌ Drift report visualization pages
- ❌ Charts and visualizations (components designed but not built)
- ❌ WebSocket client integration (socket.io client installed)
- ❌ API endpoint files for pipelines, runs, experiments, models
- ❌ End-to-end tests

#### Infrastructure — ~15% complete

| Component | Status | Notes |
|-----------|--------|-------|
| `docker-compose.yml` | ✅ | At `autopipe/dashboard/docker-compose.yml` |
| Frontend `Dockerfile` | ❌ | Missing |
| Kubernetes manifests | ❌ | Not created |
| CI/CD (GitHub Actions) | ❌ | Not created |
| Alembic migrations | ❌ | Not created |

---

### 📊 Implementation Gap vs. Design Document

| Design Section | In Code? | % Done | Notes |
|---|---|---|---|
| System Architecture Diagram | ⚠️ | 10% | File structure loosely follows it |
| SQLAlchemy Models | ✅ | 90% | 14 tables implemented; design has 18 |
| REST API Endpoints (OpenAPI) | ✅ | 60% | Most endpoints exist, auth missing |
| WebSocket Handlers | ✅ | 30% | Handlers exist but Redis not wired |
| React Project Structure | ✅ | 40% | Partial; needs ~15 more page components |
| Service Layer (Python) | ❌ | 0% | Business logic in endpoints |
| Dashboard Pages | ⚠️ | 10% | Only basic Dashboard.tsx |
| Deployment Config | ⚠️ | 20% | Docker compose exists; K8s missing |
| Testing Strategy | ❌ | 0% | No test files for dashboard |
| Monitoring/Observability | ❌ | 0% | Not implemented |

---

### 🔧 Updated Roadmap (Priority Order)

#### Immediate (Fix Gaps — This Week)
1. **Fix auth** — create `app/core/auth.py` with JWT; add `/auth/login`, `/auth/refresh` endpoints
2. **Add Alembic migrations** — initialize `alembic init` and generate first migration
3. **Connect Redis** — wire `core/events.py` to Redis pub/sub for real-time
4. **Service layer** — extract business logic from endpoints into `services/*.py`

#### Short Term (2–3 Weeks)
5. **Frontend auth** — Login page, route guards, token refresh
6. **Frontend API wiring** — Connect React Query hooks to real endpoints
7. **Pipeline pages** — List, detail, editor components
8. **Run pages** — List, detail, live log viewer
9. **Model registry pages** — List, detail, version compare

#### Medium Term (Month 1–2)
10. **Experiment tracking UI** — List, detail, visualization
11. **Drift detection UI** — Reports, charts, alerts
12. **WebSocket frontend** — Socket.io client, real-time updates
13. **Charts & visualizations** — Recharts dashboards, DAG graph
14. **Frontend E2E tests** — Playwright or Cypress

#### Production Hardening (Month 2–3)
15. **Docker Compose full setup** — Frontend + Backend + PostgreSQL + Redis
16. **Kubernetes manifests** — Deployment, Service, Ingress, HPA
17. **CI/CD pipeline** — GitHub Actions for test + build + deploy
18. **Performance optimization** — Query pagination, AG Grid virtualization
19. **Security audit** — RBAC, rate limiting, input validation

---

### 📁 Key Files Reference

```
autopipe/dashboard/
├── DOCKER_COMPOSE_STATUS.md          # Docker setup docs
├── IMPLEMENTATION_STATUS.md          # Canonical living status (authoritative)
├── frontend/                         # React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── api/endpoints/            # Only drift.ts exists
│       ├── pages/dashboard/          # Only basic Dashboard.tsx
│       ├── stores/                   # Skeleton Zustand stores
│       └── components/               # Layout + UI shell only
└── backend/                          # FastAPI + SQLAlchemy async + Pydantic
    └── app/
        ├── db/models.py              # 14 tables fully defined
        ├── schemas/                  # Complete Pydantic schemas
        ├── api/v1/endpoints/         # All endpoint files exist
        ├── core/config.py            # Settings
        └── core/events.py            # Event emitter (needs Redis wiring)
```

---

*Last updated: 2026-04-14 — auto-generated from repository audit*
