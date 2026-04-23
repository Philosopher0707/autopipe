"""Pydantic schemas for API request/response validation."""

from datetime import datetime, timezone
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


class SidebarCounts(BaseModel):
    """Sidebar badge counts — clean direct counts, no complex joins."""
    pipelines_total: int = 0
    pipelines_active: int = 0  # pipelines with any non-terminal run (running/pending)
    experiments_total: int = 0  # total experiments (shown when active is 0)
    experiments_active: int = 0  # experiments with running/pending runs
    models_total: int = 0
    models_in_production: int = 0
    drift_alerts_unacknowledged: int = 0
    drift_features_drifted: int = 0


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
    config: Optional[Dict[str, Any]] = None
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


# ==================== Training Config Schemas ====================

class TrainingConfigResponse(BaseModel):
    """Response for GET /runs/{id}/config."""
    run_id: str
    architecture: Optional[str] = None
    optimizer: Optional[str] = None
    learning_rate: Optional[float] = None
    weight_decay: Optional[float] = None
    batch_size: Optional[int] = None
    epochs: Optional[int] = None
    early_stopping: Optional[Dict[str, Any]] = None
    lr_scheduler: Optional[Dict[str, Any]] = None
    amp: Optional[bool] = None
    gradient_clip: Optional[float] = None


class CheckpointBase(BaseModel):
    """Base checkpoint schema."""
    epoch: int
    val_loss: float
    val_accuracy: float
    file_path: str
    is_best: bool = False


class CheckpointResponse(CheckpointBase):
    """Checkpoint API response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    restored: bool = False
    promoted: bool = False
    created_at: Optional[datetime] = None


class CheckpointsResponse(BaseModel):
    """Response for GET /runs/{id}/checkpoints."""
    run_id: str
    checkpoints: List[CheckpointResponse]


class CheckpointPromoteRequest(BaseModel):
    """Request to mark a checkpoint as restored or promoted."""
    restored: Optional[bool] = None
    promoted: Optional[bool] = None


class RunFilters(BaseModel):
    """Run filter parameters."""
    status: Optional[str] = None
    pipeline_id: Optional[str] = None
    experiment_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    created_by: Optional[str] = None


# ==================== Run Comparison Schemas ====================

class RunCompareRequest(BaseModel):
    """Request to compare multiple runs."""
    run_ids: List[str] = Field(..., min_length=2, max_length=10, description="List of run IDs to compare")


class ParameterComparison(BaseModel):
    """Parameter comparison between runs."""
    value: Optional[Any] = None


class ParameterComparisonRow(BaseModel):
    """Row in parameter comparison table."""
    name: str
    values: Dict[str, Optional[Any]]  # run_id -> value
    is_different: bool


class MetricComparison(BaseModel):
    """Metric comparison between runs."""
    value: Optional[float] = None
    delta_from_baseline: Optional[float] = None  # percentage difference


class MetricComparisonRow(BaseModel):
    """Row in metric comparison table."""
    name: str
    values: Dict[str, MetricComparison]
    best_run_id: Optional[str] = None
    higher_is_better: bool = True


class RunSummaryForComparison(BaseModel):
    """Summary of a run for comparison view."""
    id: str
    run_number: int
    status: str
    pipeline_name: Optional[str] = None
    pipeline_id: str
    experiment_id: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    config: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None


class RunDiffSummary(BaseModel):
    """Summary of differences between runs."""
    total_params: int
    different_params: int
    total_metrics: int
    best_metric_per_key: Dict[str, str]  # metric_name -> run_id


class RunCompareResponse(BaseModel):
    """Response for run comparison."""
    runs: List[RunSummaryForComparison]
    parameters: List[ParameterComparisonRow]
    metrics: List[MetricComparisonRow]
    diff_summary: RunDiffSummary


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


class TrialLaunchRequest(BaseModel):
    """Request to launch trial runs for an experiment."""
    pipeline_id: str
    strategy: str = Field(default="random", pattern="^(random|grid)$")
    n_trials: int = Field(default=5, ge=1, le=100)
    simulate: bool = Field(default=True, description="Auto-advance runs through lifecycle with metrics")


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


class TrialLaunchResponse(BaseModel):
    """Response for launching trial runs."""
    experiment_id: str
    runs: List[RunResponse]
    strategy: str
    n_trials: int


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
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

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


class ModelResponse(ModelInDB):
    """Model API response."""
    versions: List[ModelVersionResponse] = Field(default_factory=list)


class ModelList(PaginatedResponse):
    """Model list response."""
    items: List[ModelResponse]


class ModelComparisonRequest(BaseModel):
    """Model comparison request."""
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    version_a: int
    version_b: int


class ModelComparisonResponse(BaseModel):
    """Model comparison response."""
    model_config = ConfigDict(protected_namespaces=())

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
    model_config = ConfigDict(protected_namespaces=())

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
    model_config = ConfigDict(protected_namespaces=())

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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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


# ==================== Chart Data Schemas ====================

class ChartMetricPoint(BaseModel):
    """Single data point for a metric-over-time chart."""
    run_number: int
    value: float
    completed_at: Optional[str] = None


class RunMetricsOverTimeResponse(BaseModel):
    """Response for GET /charts/run-metrics-over-time."""
    metric: str
    points: List[ChartMetricPoint]


class StepDurationPoint(BaseModel):
    """Single step duration entry."""
    name: str
    duration_seconds: Optional[float] = None
    status: str
    order_index: int


class StepDurationsResponse(BaseModel):
    """Response for GET /charts/step-durations."""
    run_id: str
    steps: List[StepDurationPoint]


class ExperimentMetricTraceResponse(BaseModel):
    """Response for GET /charts/experiment-metric-trace."""
    experiment_id: str
    metrics: List[str]
    points: List[Dict[str, Any]]


class ModelVersionMetricsResponse(BaseModel):
    """Response for GET /charts/model-version-metrics."""
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    model_name: str
    metrics: List[str]
    points: List[Dict[str, Any]]


class DriftFeatureScorePoint(BaseModel):
    """Single feature drift score entry."""
    name: str
    drift_score: float
    threshold: float
    is_drifted: bool
    test_type: str


class DriftFeatureScoresResponse(BaseModel):
    """Response for GET /charts/drift-feature-scores."""
    report_id: str
    drift_detected: bool
    features: List[DriftFeatureScorePoint]


class DriftTrendPoint(BaseModel):
    """Single point in drift trend."""
    created_at: str
    drift_score: float
    drift_detected: bool
    features_drifted: int


class DriftTrendResponse(BaseModel):
    """Response for GET /charts/drift-trend."""
    model_config = ConfigDict(protected_namespaces=())

    model_id: Optional[str] = None
    points: List[DriftTrendPoint]


# ==================== Metric Log Schemas ====================

class MetricLogPoint(BaseModel):
    """Single metric log entry."""
    step_index: Optional[int] = None
    value: float
    recorded_at: str


class MetricSeriesResponse(BaseModel):
    """Response for GET /charts/metric-series."""
    metric_name: str
    run_id: str
    run_number: int
    points: List[MetricLogPoint]


class AvailableMetricsResponse(BaseModel):
    """Response for GET /charts/available-metrics."""
    metrics: List[str]


class MetricLogCreate(BaseModel):
    """Request to log a single metric value."""
    run_id: str
    step_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    experiment_id: Optional[str] = None
    metric_name: str = Field(..., min_length=1, max_length=255)
    step_index: Optional[int] = None
    value: float


# ==================== Chart Artifact Schemas ====================

class ChartArtifactCreate(BaseModel):
    """Chart artifact creation schema."""
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    experiment_id: Optional[str] = None
    chart_type: str = Field(..., pattern="^(line|bar|scatter|area|pie|heatmap)$")
    title: str = Field(..., min_length=1, max_length=255)
    data: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None


class ChartArtifactResponse(BaseModel):
    """Chart artifact API response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    experiment_id: Optional[str] = None
    chart_type: str
    title: str
    data: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None
    created_at: datetime


class ChartArtifactList(PaginatedResponse):
    """Chart artifact list response."""
    items: List[ChartArtifactResponse]


# ==================== Training Metrics Schemas ====================

class TrainingEpochPoint(BaseModel):
    """Single epoch of training/validation metrics."""
    epoch: int
    loss: Optional[float] = None
    val_loss: Optional[float] = None
    accuracy: Optional[float] = None
    val_accuracy: Optional[float] = None


class TrainingMetricsTraceResponse(BaseModel):
    """Response for GET /charts/training-metrics-trace."""
    run_id: str
    run_number: int
    points: List[TrainingEpochPoint]


# ==================== Explainability Schemas ====================

class ShapValuePoint(BaseModel):
    """Single SHAP value for a feature."""
    feature: str
    value: float
    impact: float
    base_value: float


class LimeExplanationPoint(BaseModel):
    """Single LIME explanation weight for a feature."""
    feature: str
    weight: float


class PermutationImportancePoint(BaseModel):
    """Permutation importance for a feature."""
    feature: str
    importance: float
    std: float


class ExplainabilityRequest(BaseModel):
    """Request for POST /explainability/shap and /lime."""
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    data: List[Dict[str, Any]]


class ShapResponse(BaseModel):
    """Response for POST /explainability/shap."""
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    feature_importance: List[ShapValuePoint]


class LimeResponse(BaseModel):
    """Response for POST /explainability/lime."""
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    feature_importance: List[LimeExplanationPoint]


class ExplainabilityResponse(BaseModel):
    """Response for GET /charts/explainability."""
    run_id: str
    shap_values: List[ShapValuePoint]
    lime_explanation: List[LimeExplanationPoint]
    permutation_importance: List[PermutationImportancePoint]


# ==================== AutoML / Optuna Schemas ====================

class TrialPoint(BaseModel):
    """Single Optuna trial result."""
    number: int
    state: str
    value: Optional[float] = None
    values: Optional[List[float]] = None
    params: Dict[str, Any]
    duration_seconds: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AutomlTrialsResponse(BaseModel):
    """Response for GET /charts/automl-trials."""
    experiment_id: str
    trials: List[TrialPoint]


class TrialDetailResponse(BaseModel):
    """Response for GET /trials/{id}."""
    trial: TrialPoint


class TrialHistoryPoint(BaseModel):
    """Single point in a trial's optimization history."""
    step: int
    value: float
    timestamp: datetime


class TrialHistoryResponse(BaseModel):
    """Response for GET /trials/{id}/history."""
    trial_id: str
    history: List[TrialHistoryPoint]


class ParamImportancePoint(BaseModel):
    """Parameter importance for radar chart."""
    param: str
    importance: float


class ParetoFrontPoint(BaseModel):
    """Single point on Pareto front."""
    trial_number: int
    objective_1: float
    objective_2: float
    params: Dict[str, Any]


class PruningHistoryPoint(BaseModel):
    """Pruning event for a trial."""
    trial_number: int
    step: int
    intermediate_value: float
    pruned: bool


class AutomlVisualizationsResponse(BaseModel):
    """Response for GET /charts/automl-visualizations."""
    experiment_id: str
    param_importance: List[ParamImportancePoint]
    pareto_front: List[ParetoFrontPoint]
    pruning_history: List[PruningHistoryPoint]
    parallel_coords_data: List[Dict[str, Any]]


# ==================== Feature Engineering Schemas ====================

class TransformStep(BaseModel):
    """Single transform in a feature engineering pipeline."""
    name: str
    type: str
    params: Dict[str, Any]
    enabled: bool = True


class FeatureStats(BaseModel):
    """Statistics for a single feature."""
    name: str
    dtype: str
    nulls: int
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    unique: Optional[int] = None


class FeatureTransformsResponse(BaseModel):
    """Response for GET /charts/feature-transforms."""
    run_id: str
    pipeline: List[TransformStep]
    before: List[FeatureStats]
    after: List[FeatureStats]


class FeatureExtractRequest(BaseModel):
    """Request for POST /features/extract."""
    pipeline_id: str
    data: List[Dict[str, Any]]
    transforms: Optional[List[TransformStep]] = None


class FeatureExtractResponse(BaseModel):
    """Response for POST /features/extract."""
    pipeline_id: str
    before_count: int
    after_count: int
    before: List[FeatureStats]
    after: List[FeatureStats]
    sample_values: Dict[str, List[Any]]


class FeaturePreviewResponse(BaseModel):
    """Response for GET /features/preview/{pipeline_id}."""
    pipeline_id: str
    pipeline: List[TransformStep]
    before: List[FeatureStats]
    after: List[FeatureStats]


# ==================== Experiment Artifacts Schemas ====================

class ExperimentArtifact(BaseModel):
    """Single experiment artifact."""
    id: str
    artifact_type: str  # image, figure, csv, json, other
    title: str
    file_path: str
    file_size: int
    created_at: Optional[datetime] = None


class ExperimentArtifactsResponse(BaseModel):
    """Response for GET /experiments/{id}/artifacts."""
    experiment_id: str
    artifacts: List[ExperimentArtifact]


# ==================== System Resource Schemas ====================

class ResourceUsagePoint(BaseModel):
    """Single resource usage measurement."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    gpu_percent: Optional[float] = None


class ResourceUsageResponse(BaseModel):
    """Response for GET /dashboard/resources."""
    points: List[ResourceUsagePoint]
