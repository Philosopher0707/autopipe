import { apiClient } from '../client'

export interface RunMetricsOverTimeResponse {
  metric: string
  points: Array<{ run_number: number; value: number; completed_at: string | null }>
}

export interface StepDurationsResponse {
  run_id: string
  steps: Array<{
    name: string
    duration_seconds: number | null
    status: string
    order_index: number
  }>
}

export interface ExperimentMetricTraceResponse {
  experiment_id: string
  metrics: string[]
  points: Array<Record<string, number>>
}

export interface ModelVersionMetricsResponse {
  model_id: string
  model_name: string
  metrics: string[]
  points: Array<Record<string, number | string>>
}

export interface DriftFeatureScoresResponse {
  report_id: string
  drift_detected: boolean
  features: Array<{
    name: string
    drift_score: number
    threshold: number
    is_drifted: boolean
    test_type: string
  }>
}

export interface DriftTrendResponse {
  model_id: string | null
  points: Array<{
    created_at: string
    drift_score: number
    drift_detected: boolean
    features_drifted: number
  }>
}

export interface ChartArtifact {
  id: string
  run_id: string | null
  step_id: string | null
  experiment_id: string | null
  chart_type: 'line' | 'bar' | 'scatter' | 'area' | 'pie' | 'heatmap'
  title: string
  data: Record<string, unknown>
  config: Record<string, unknown> | null
  created_at: string
}

export interface MetricLogPoint {
  step_index: number | null
  value: number
  recorded_at: string
}

export interface MetricSeriesResponse {
  metric_name: string
  run_id: string
  run_number: number
  points: MetricLogPoint[]
}

export interface AvailableMetricsResponse {
  metrics: string[]
}

export interface MetricLogCreate {
  run_id: string
  step_id?: string
  pipeline_id?: string
  experiment_id?: string
  metric_name: string
  step_index?: number
  value: number
}

export interface TrainingEpochPoint {
  epoch: number
  loss: number | null
  val_loss: number | null
  accuracy: number | null
  val_accuracy: number | null
}

export interface TrainingMetricsTraceResponse {
  run_id: string
  run_number: number
  points: TrainingEpochPoint[]
}

export const chartsApi = {
  getRunMetricsOverTime: async (params: {
    metric: string
    pipeline_id?: string
    experiment_id?: string
    limit?: number
  }): Promise<RunMetricsOverTimeResponse> => {
    return apiClient.get('/charts/run-metrics-over-time', { params })
  },

  getStepDurations: async (runId: string): Promise<StepDurationsResponse> => {
    return apiClient.get('/charts/step-durations', { params: { run_id: runId } })
  },

  getExperimentMetricTrace: async (params: {
    experiment_id: string
    metrics?: string
  }): Promise<ExperimentMetricTraceResponse> => {
    return apiClient.get('/charts/experiment-metric-trace', { params })
  },

  getModelVersionMetrics: async (params: {
    model_id: string
    metrics?: string
  }): Promise<ModelVersionMetricsResponse> => {
    return apiClient.get('/charts/model-version-metrics', { params })
  },

  getDriftFeatureScores: async (reportId: string): Promise<DriftFeatureScoresResponse> => {
    return apiClient.get('/charts/drift-feature-scores', { params: { report_id: reportId } })
  },

  getDriftTrend: async (params?: {
    model_id?: string
    days?: number
  }): Promise<DriftTrendResponse> => {
    return apiClient.get('/charts/drift-trend', { params })
  },

  listArtifacts: async (params: {
    run_id?: string
    step_id?: string
    experiment_id?: string
    chart_type?: string
    page?: number
    page_size?: number
  }): Promise<{ items: ChartArtifact[]; total: number; pages: number }> => {
    return apiClient.get('/charts/artifacts', { params })
  },

  getArtifact: async (id: string): Promise<ChartArtifact> => {
    return apiClient.get(`/charts/artifacts/${id}`)
  },

  createArtifact: async (body: {
    run_id?: string
    step_id?: string
    experiment_id?: string
    chart_type: string
    title: string
    data: Record<string, unknown>
    config?: Record<string, unknown>
  }): Promise<ChartArtifact> => {
    return apiClient.post('/charts/artifacts', body)
  },

  getAvailableMetrics: async (runIds?: string[]): Promise<AvailableMetricsResponse> => {
    const params: Record<string, unknown> = {}
    if (runIds && runIds.length > 0) params.run_ids = runIds.join(',')
    return apiClient.get('/charts/available-metrics', { params })
  },

  getMetricSeries: async (params: {
    run_ids: string[]
    metric_name: string
  }): Promise<MetricSeriesResponse[]> => {
    return apiClient.get('/charts/metric-series', {
      params: { run_ids: params.run_ids.join(','), metric_name: params.metric_name },
    })
  },

  createMetricLog: async (body: MetricLogCreate): Promise<MetricLogPoint> => {
    return apiClient.post('/charts/metric-logs', body)
  },

  getTrainingMetricsTrace: async (runId: string): Promise<TrainingMetricsTraceResponse> => {
    return apiClient.get('/charts/training-metrics-trace', { params: { run_id: runId } })
  },
}