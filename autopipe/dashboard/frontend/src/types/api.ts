// Dashboard Types
export interface DashboardStats {
  pipelines: {
    total: number
    running: number
    completed_today: number
  }
  models: {
    total: number
    in_production: number
    in_staging: number
  }
  drift: {
    features_drifted: number
    drift_ratio: number
    last_check: string
  }
  experiments: {
    active: number
    completed_today: number
    total_trials: number
  }
}

export interface ActivityLog {
  id: string
  action: string
  resource_type: string
  resource_id?: string
  details?: Record<string, unknown>
  user_id?: string
  created_at: string
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
  status: RunStatus
  run_number: number
  started_at?: string
  completed_at?: string
  duration_seconds?: number
  metrics?: Record<string, number>
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
}

export interface ModelVersion {
  id: string
  model_id: string
  version: number
  stage: ModelStage
  metrics?: Record<string, number>
  params?: Record<string, unknown>
  artifact_path: string
  run_id?: string
  created_at: string
}

// Experiment Types
export interface Experiment {
  id: string
  name: string
  description?: string
  status: 'running' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  best_run_id?: string
  best_metric?: number
  metric_name?: string
  best_trial_id?: string
}

export interface Trial {
  id: string
  experiment_id: string
  trial_number: number
  params: Record<string, unknown>
  value?: number
  status: 'running' | 'completed' | 'failed' | 'pruned'
  started_at?: string
  completed_at?: string
}

// Drift Detection Types
export interface DriftReport {
  id: string
  model_id?: string
  drift_score: number
  drift_detected: boolean
  feature_drifts?: Record<string, number>
  created_at: string
  features_drifted?: number
}

export interface DriftAlert {
  id: string
  feature_name: string
  severity: 'info' | 'warning' | 'error' | 'critical'
  drift_score: number
  threshold: number
  drift_type: string
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
  per_page: number
  pages?: number
}

export interface ApiError {
  detail: string
  status_code: number
}
