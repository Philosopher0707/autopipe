// Dashboard Types
export interface DashboardStats {
  pipelines: {
    total: number
    running: number
    completed_today: number
    failed_today: number
    avg_duration: string
    success_rate: number
  }
  models: {
    total: number
    in_production: number
    in_staging: number
    recent_versions: number
  }
  drift: {
    alerts_today: number
    features_drifted: number
    drift_ratio: number
    last_check: string | null
  }
  experiments: {
    total: number
    active: number
    completed_today: number
    total_trials: number
  }
}

export interface ActivityLog {
  id?: string
  action: string
  timestamp?: string
  created_at?: string
  title?: string
  description?: string
  resource_type?: string
  resource_id?: string
  user?: string
}

// Pipeline Types
export type RunStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'

export interface Pipeline {
  id: string
  name: string
  description?: string
  config?: Record<string, unknown>
  tags?: string[]
  is_active: boolean
  created_at: string
  updated_at: string
  created_by?: string
  run_count?: number
  project_id?: string
}

export interface PipelineRun {
  id: string
  pipeline_id: string
  experiment_id?: string
  status: RunStatus
  run_number: number
  started_at?: string
  completed_at?: string
  duration_seconds?: number
  metrics?: Record<string, number>
  config?: Record<string, unknown>
  error_message?: string
  created_at: string
  pipeline_name?: string
}

export interface Step {
  id: string
  run_id: string
  name: string
  step_type: string
  status: RunStatus | 'skipped'
  started_at?: string
  completed_at?: string
  duration_seconds?: number
  order_index: number
}

// Model Registry Types
export type ModelStage = 'pending' | 'staging' | 'production' | 'archived'

export interface Model {
  id: string
  name: string
  description?: string
  framework: string
  task_type?: string
  current_stage: ModelStage
  tags?: string[]
  created_at: string
  updated_at: string
  version_count?: number
  versions?: ModelVersion[]  // Eager-loaded versions from model detail endpoint
}

export interface ModelVersion {
  id: string
  model_id: string
  version: number
  stage: ModelStage
  description?: string
  metrics?: Record<string, number>
  params?: Record<string, unknown>
  artifact_path: string
  run_id?: string
  tags?: string[]
  created_at: string
  transitioned_at?: string | null
  model_name?: string
}

// Experiment Types
export interface Experiment {
  id: string
  name: string
  description?: string
  config?: Record<string, unknown>
  status: 'pending' | 'running' | 'completed' | 'failed'
  tags?: string[]
  created_at: string
  updated_at: string
  best_run_id?: string
  best_metric?: number
  metric_name?: string
  run_count?: number
}

// Drift Detection Types
export interface DriftFeature {
  drift_score: number
  p_value?: number | null
  threshold: number
  is_drifted: boolean
  test_type: string
}

export interface DriftReport {
  id: string
  model_id?: string
  run_id?: string | null
  drift_score: number
  drift_detected: boolean
  feature_drifts?: Record<string, DriftFeature>
  reference_data_summary?: Record<string, unknown>
  current_data_summary?: Record<string, unknown>
  created_at: string
  features_drifted?: number
  alert_generated?: boolean
}

export interface DriftAlert {
  id: string
  feature_name: string
  severity: 'info' | 'warning' | 'error' | 'critical'
  drift_score: number
  threshold: number
  drift_type: string
  drift_metric: string
  acknowledged: boolean
  created_at: string
}

// Auth Types
export interface User {
  id: string
  username: string
  email: string
  full_name?: string
  role: 'admin' | 'data_scientist' | 'viewer'
  is_active: boolean
  last_login?: string
}

// API Response Types
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size?: number
  per_page?: number
  pages?: number
}

export interface ApiError {
  detail: string
  status_code: number
}

// Explainability Types
export interface ShapValuePoint {
  feature: string
  value: number
  impact: number
  base_value: number
}

export interface LimeExplanationPoint {
  feature: string
  weight: number
}

export interface PermutationImportancePoint {
  feature: string
  importance: number
  std: number
}

export interface ExplainabilityResponse {
  run_id: string
  shap_values: ShapValuePoint[]
  lime_explanation: LimeExplanationPoint[]
  permutation_importance: PermutationImportancePoint[]
}

// AutoML / Optuna Types
export interface TrialPoint {
  number: number
  state: string
  value?: number
  values?: number[]
  params: Record<string, unknown>
  duration_seconds?: number
  started_at?: string
  completed_at?: string
}

export interface AutomlTrialsResponse {
  experiment_id: string
  trials: TrialPoint[]
}

export interface ParamImportancePoint {
  param: string
  importance: number
}

export interface ParetoFrontPoint {
  trial_number: number
  objective_1: number
  objective_2: number
  params: Record<string, unknown>
}

export interface PruningHistoryPoint {
  trial_number: number
  step: number
  intermediate_value: number
  pruned: boolean
}

export interface AutomlVisualizationsResponse {
  experiment_id: string
  param_importance: ParamImportancePoint[]
  pareto_front: ParetoFrontPoint[]
  pruning_history: PruningHistoryPoint[]
  parallel_coords_data: Record<string, unknown>[]
}

// Feature Engineering Types
export interface TransformStep {
  name: string
  type: string
  params: Record<string, unknown>
  enabled: boolean
}

export interface FeatureStats {
  name: string
  dtype: string
  nulls: number
  mean?: number
  std?: number
  min?: number
  max?: number
  unique?: number
}

export interface FeatureTransformsResponse {
  run_id: string
  pipeline: TransformStep[]
  before: FeatureStats[]
  after: FeatureStats[]
}

// AutoML Trial Detail / History Types
export interface TrialDetailResponse {
  trial: TrialPoint
}

export interface TrialHistoryPoint {
  step: number
  value: number
  timestamp: string
}

export interface TrialHistoryResponse {
  trial_id: string
  history: TrialHistoryPoint[]
}

// Feature Engineering Extract / Preview Types
export interface FeatureExtractRequest {
  pipeline_id: string
  data: Record<string, unknown>[]
  transforms?: TransformStep[]
}

export interface FeatureExtractResponse {
  pipeline_id: string
  before_count: number
  after_count: number
  before: FeatureStats[]
  after: FeatureStats[]
  sample_values: Record<string, unknown[]>
}

export interface FeaturePreviewResponse {
  pipeline_id: string
  pipeline: TransformStep[]
  before: FeatureStats[]
  after: FeatureStats[]
}

// Training Config Types
export interface TrainingConfigResponse {
  run_id: string
  architecture?: string
  optimizer?: string
  learning_rate?: number
  weight_decay?: number
  batch_size?: number
  epochs?: number
  early_stopping?: Record<string, unknown>
  lr_scheduler?: Record<string, unknown>
  amp?: boolean
  gradient_clip?: number
}

// Checkpoint Types
export interface Checkpoint {
  id: string
  epoch: number
  val_loss: number
  val_accuracy: number
  file_path: string
  is_best: boolean
  restored: boolean
  promoted: boolean
  created_at: string
}

export interface CheckpointsResponse {
  run_id: string
  checkpoints: Checkpoint[]
}

// Experiment Artifact Types
export interface ExperimentArtifact {
  id: string
  artifact_type: 'image' | 'figure' | 'csv' | 'json' | 'other'
  title: string
  file_path: string
  file_size: number
  created_at: string
}

export interface ExperimentArtifactsResponse {
  experiment_id: string
  artifacts: ExperimentArtifact[]
}

// Pipeline Validation Types
export interface PipelineValidateRequest {
  name?: string
  steps?: Record<string, unknown>[]
  config?: Record<string, unknown>
}

export interface ValidationError {
  step_index?: number
  field: string
  message: string
}

export interface PipelineValidateResponse {
  valid: boolean
  errors: ValidationError[]
}

// Project Types
export interface Project {
  id: string
  name: string
  description?: string
  status: 'active' | 'archived'
  tags?: string[]
  starred: boolean
  created_at: string
  updated_at: string
  created_by?: string
  run_count?: number
  last_run_at?: string | null
}

// System Resource Types
export interface ResourceUsagePoint {
  timestamp: string
  cpu_percent: number
  memory_percent: number
  gpu_percent?: number
}

export interface ResourceUsageResponse {
  points: ResourceUsagePoint[]
}
