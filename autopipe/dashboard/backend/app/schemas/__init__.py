"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


# ==================== Shared ====================

class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    total: int
    page: int
    page_size: int
    pages: int


# ==================== Pipeline Schemas ====================

class PipelineBase(BaseModel):
    """Base pipeline schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class PipelineCreate(PipelineBase):
    """Pipeline creation schema."""
    pass


class PipelineUpdate(BaseModel):
    """Pipeline update schema."""
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class PipelineInDB(PipelineBase):
    """Pipeline database schema."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool = True
    config_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    run_count: int = 0


class PipelineResponse(PipelineInDB):
    """Pipeline API response."""
    pass


class PipelineList(PaginatedResponse):
    """Pipeline list response."""
    items: List[PipelineResponse]


# ==================== Run Schemas ====================

class RunBase(BaseModel):
    """Base run schema."""
    pipeline_id: str
    experiment_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class RunCreate(RunBase):
    """Run creation schema."""
    pass


class RunUpdate(BaseModel):
    """Run update schema."""
    status: Optional[str] = Field(None, pattern="^(pending|running|success|failed|cancelled)$")
    metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class RunInDB(RunBase):
    """Run database schema."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    run_number: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    logs_path: Optional[str] = None
    error_message: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    pipeline_name: Optional[str] = None  # Populated from relationship


class RunResponse(RunInDB):
    """Run API response."""
    pass


class RunList(PaginatedResponse):
    """Run list response."""
    items: List[RunResponse]


class RunFilters(BaseModel):
    """Run filter parameters."""
    status: Optional[str] = None
    pipeline_id: Optional[str] = None
    experiment_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    created_by: Optional[str] = None


# ==================== Step Schemas ====================

class StepBase(BaseModel):
    """Base step schema."""
    run_id: str
    name: str = Field(..., min_length=1, max_length=255)
    step_type: str = Field(..., max_length=100)
    config: Optional[Dict[str, Any]] = None
    order_index: int = 0


class StepCreate(StepBase):
    """Step creation schema."""
    pass


class StepUpdate(BaseModel):
    """Step update schema."""
    status: Optional[str] = Field(None, pattern="^(pending|running|success|failed|skipped)$")
    metrics: Optional[Dict[str, Any]] = None
    logs: Optional[str] = None
    error_message: Optional[str] = None


class StepInDB(StepBase):
    """Step database schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    input_shape: Optional[Dict[str, Any]] = None
    output_shape: Optional[Dict[str, Any]] = None
    logs: Optional[str] = None


class StepResponse(StepInDB):
    """Step API response."""
    pass


class StepList(BaseModel):
    """Step list response."""
    items: List[StepResponse]


# ==================== Experiment Schemas ====================

class ExperimentBase(BaseModel):
    """Base experiment schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ExperimentCreate(ExperimentBase):
    """Experiment creation schema."""
    pass


class ExperimentUpdate(BaseModel):
    """Experiment update schema."""
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ExperimentInDB(ExperimentBase):
    """Experiment database schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    best_run_id: Optional[str] = None
    best_metric: Optional[float] = None
    metric_name: Optional[str] = None
    run_count: int = 0
    status: str = "pending"


class ExperimentResponse(ExperimentInDB):
    """Experiment API response."""
    pass


class ExperimentList(PaginatedResponse):
    """Experiment list response."""
    items: List[ExperimentResponse]


# ==================== Model Registry Schemas ====================

class ModelBase(BaseModel):
    """Base model registry schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    framework: str = Field(..., max_length=50)  # sklearn, pytorch, tensorflow, etc.
    task_type: Optional[str] = Field(None, max_length=50)  # classification, regression, etc.
    signature: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ModelCreate(ModelBase):
    """Model creation schema."""
    pass


class ModelUpdate(BaseModel):
    """Model update schema."""
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class ModelInDB(ModelBase):
    """Model database schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    current_stage: str
    created_at: datetime
    updated_at: datetime
    version_count: int = 0


class ModelResponse(ModelInDB):
    """Model API response."""
    pass


class ModelList(PaginatedResponse):
    """Model list response."""
    items: List[ModelResponse]


# ==================== Model Version Schemas ====================

class ModelVersionCreate(BaseModel):
    """Model version creation schema."""
    description: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None
    artifact_path: str
    run_id: Optional[str] = None
    tags: Optional[List[str]] = None


class ModelVersionUpdate(BaseModel):
    """Model version update schema."""
    stage: Optional[str] = Field(None, pattern="^(pending|staging|production|archived)$")
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class ModelVersionInDB(BaseModel):
    """Model version database schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    model_id: str
    version: int
    stage: str
    description: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None
    artifact_path: str
    run_id: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: datetime
    transitioned_at: Optional[datetime] = None
    model_name: Optional[str] = None  # Populated from relationship


class ModelVersionResponse(ModelVersionInDB):
    """Model version API response."""
    pass


class ModelVersionList(BaseModel):
    """Model version list response."""
    items: List[ModelVersionResponse]
    total: int


class ModelComparisonRequest(BaseModel):
    """Model comparison request."""
    model_id: str
    version_a: int
    version_b: int


class ModelComparisonResponse(BaseModel):
    """Model comparison response."""
    model_name: str
    version_a: int
    version_b: int
    metric_differences: Dict[str, float]
    is_better: bool
    report: str  # Markdown formatted comparison


class ModelPromoteRequest(BaseModel):
    """Model promotion request."""
    stage: str = Field(..., pattern="^(pending|staging|production|archived)$")
    description: Optional[str] = None


# ==================== Drift Detection Schemas ====================

class DriftReportBase(BaseModel):
    """Base drift report schema."""
    model_id: Optional[str] = None
    run_id: Optional[str] = None
    drift_score: float = Field(..., ge=0.0, le=1.0)
    drift_detected: bool = False
    feature_drifts: Optional[Dict[str, Any]] = None
    reference_data_summary: Optional[Dict[str, Any]] = None
    current_data_summary: Optional[Dict[str, Any]] = None


class DriftReportCreate(DriftReportBase):
    """Drift report creation schema."""
    pass


class DriftReportInDB(DriftReportBase):
    """Drift report database schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime
    alert_generated: bool


class DriftReportResponse(DriftReportInDB):
    """Drift report API response."""
    features_drifted: Optional[int] = None


class DriftReportList(PaginatedResponse):
    """Drift report list response."""
    items: List[DriftReportResponse]


class FeatureDrift(BaseModel):
    """Feature drift details."""
    feature_name: str
    drift_score: float
    p_value: Optional[float] = None
    threshold: float
    is_drifted: bool
    test_type: str  # ks, psi, chi2, etc.


class DriftDetectRequest(BaseModel):
    """Drift detection request."""
    model_id: Optional[str] = None
    reference_data_path: Optional[str] = None
    current_data_path: Optional[str] = None
    threshold: float = Field(0.05, ge=0.0, le=1.0)
    test_types: List[str] = ["ks", "psi"]


class DriftDetectResponse(BaseModel):
    """Drift detection response."""
    drift_detected: bool
    overall_drift_score: float
    features_analyzed: int
    drifted_features: List[str]
    feature_drifts: List[FeatureDrift]
    report_path: Optional[str] = None


class DriftAlertResponse(BaseModel):
    """Drift alert response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    feature_name: str
    severity: str
    drift_score: float
    threshold: float
    drift_type: str
    drift_metric: str
    acknowledged: bool
    created_at: datetime


class DriftAlertList(PaginatedResponse):
    """Drift alert list response."""
    items: List[DriftAlertResponse]


# ==================== Dashboard Overview Schemas ====================

class PipelineStats(BaseModel):
    """Pipeline-related dashboard statistics."""
    total: int = 0
    running: int = 0
    completed_today: int = 0
    failed_today: int = 0
    avg_duration: str = "0m 0s"
    success_rate: float = 0.0


class ModelStats(BaseModel):
    """Model-related dashboard statistics."""
    total: int = 0
    in_production: int = 0
    in_staging: int = 0
    recent_versions: int = 0


class DriftStats(BaseModel):
    """Drift-related dashboard statistics."""
    alerts_today: int = 0
    features_drifted: int = 0
    drift_ratio: float = 0.0
    last_check: Optional[str] = None


class ExperimentStats(BaseModel):
    """Experiment-related dashboard statistics."""
    total: int = 0
    active: int = 0
    completed_today: int = 0
    total_trials: int = 0


class DashboardStats(BaseModel):
    """Dashboard statistics overview."""
    pipelines: PipelineStats = Field(default_factory=PipelineStats)
    models: ModelStats = Field(default_factory=ModelStats)
    drift: DriftStats = Field(default_factory=DriftStats)
    experiments: ExperimentStats = Field(default_factory=ExperimentStats)


class ActivityItem(BaseModel):
    """Dashboard activity item."""
    action: str  # run_started, run_completed, model_promoted, drift_alert, etc.
    timestamp: datetime
    title: str
    description: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    user: Optional[str] = None


class ActivityFeed(BaseModel):
    """Dashboard activity feed."""
    items: List[ActivityItem]


class HealthStatus(BaseModel):
    """System health status."""
    service: str
    status: str  # healthy, degraded, down
    message: Optional[str] = None
    last_check: datetime


class SystemHealth(BaseModel):
    """Overall system health."""
    status: str
    services: List[HealthStatus]


# ==================== WebSocket Schemas ====================

class WebSocketMessage(BaseModel):
    """WebSocket message envelope."""
    type: str  # event type: run.status, run.log, run.metric, etc.
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RunLogMessage(BaseModel):
    """Run log WebSocket message."""
    run_id: str
    step_id: Optional[str] = None
    level: str  # DEBUG, INFO, WARN, ERROR
    message: str
    timestamp: datetime


class RunMetricMessage(BaseModel):
    """Run metric WebSocket message."""
    run_id: str
    step_id: Optional[str] = None
    metric_name: str
    value: float
    step_number: Optional[int] = None
    timestamp: datetime


class RunStatusMessage(BaseModel):
    """Run status change WebSocket message."""
    run_id: str
    pipeline_id: str
    pipeline_name: str
    old_status: Optional[str] = None
    new_status: str
    timestamp: datetime


# ==================== Artifact Schemas ====================

class ArtifactBase(BaseModel):
    """Base artifact schema."""
    name: str = Field(..., min_length=1, max_length=255)
    artifact_type: str = Field(..., max_length=50)  # model, plot, metric, data
    file_path: str
    metadata: Optional[Dict[str, Any]] = None


class ArtifactCreate(ArtifactBase):
    """Artifact creation schema."""
    run_id: Optional[str] = None
    step_id: Optional[str] = None


class ArtifactInDB(ArtifactBase):
    """Artifact database schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime


class ArtifactResponse(ArtifactInDB):
    """Artifact API response."""
    download_url: Optional[str] = None


class ArtifactList(PaginatedResponse):
    """Artifact list response."""
    items: List[ArtifactResponse]
