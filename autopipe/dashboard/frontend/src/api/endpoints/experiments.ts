import { apiClient } from '../client'
import type { Experiment, PaginatedResponse, PipelineRun, ExperimentArtifactsResponse } from '@/types'

export interface ExperimentDetail extends Experiment {
  runs: PipelineRun[]
}

export interface ExperimentRunsResponse {
  items: PipelineRun[]
}

export interface TrialLaunchResponse {
  experiment_id: string
  runs: PipelineRun[]
  strategy: string
  n_trials: number
}

export interface ExperimentComparison {
  experiment_id: string
  metric: string
  runs: Array<{
    id: string
    metric_value: number | null
    params: Record<string, unknown> | null
    started_at: string | null
  }>
}

export const experimentsApi = {
  list: async (params?: {
    search?: string
    status?: string
    page?: number
    page_size?: number
  }): Promise<PaginatedResponse<Experiment>> => {
    return apiClient.get<PaginatedResponse<Experiment>>('/experiments', {
      params: {
        search: params?.search,
        status: params?.status,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 20,
      },
    })
  },

  getById: async (id: string): Promise<Experiment> => {
    return apiClient.get<Experiment>(`/experiments/${id}`)
  },

  create: async (data: Partial<Experiment>): Promise<Experiment> => {
    return apiClient.post<Experiment>('/experiments', data)
  },

  update: async (id: string, data: Partial<Experiment>): Promise<Experiment> => {
    return apiClient.patch<Experiment>(`/experiments/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return apiClient.delete(`/experiments/${id}`)
  },

  listRuns: async (id: string): Promise<ExperimentRunsResponse> => {
    return apiClient.get<ExperimentRunsResponse>(`/experiments/${id}/runs`)
  },

  launchTrials: async (experimentId: string, body: {
    pipeline_id: string
    strategy?: 'random' | 'grid'
    n_trials?: number
  }): Promise<TrialLaunchResponse> => {
    return apiClient.post<TrialLaunchResponse>(`/experiments/${experimentId}/trials`, body)
  },

  compare: async (experimentId: string, metric?: string): Promise<ExperimentComparison> => {
    return apiClient.get<ExperimentComparison>(`/experiments/${experimentId}/compare`, {
      params: metric ? { metric } : undefined,
    })
  },

  getArtifacts: async (experimentId: string): Promise<ExperimentArtifactsResponse> => {
    return apiClient.get<ExperimentArtifactsResponse>(`/experiments/${experimentId}/artifacts`)
  },
}
