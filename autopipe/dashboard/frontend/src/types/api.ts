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
