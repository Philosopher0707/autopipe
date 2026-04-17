import { apiClient } from '../client'
import type { PipelineRun, Step, PaginatedResponse } from '@/types'

export interface RunLogsResponse {
  logs: Array<{
    step?: string
    level: string
    message: string
    timestamp?: string
  }>
}

export interface RunCompareResponse {
  run_a_id: string
  run_b_id: string
  run_a_status: string
  run_b_status: string
  run_a_duration: number | null
  run_b_duration: number | null
  metric_comparison: Record<string, { a: number | null; b: number | null; diff: number | null }>
}

export interface StepsResponse {
  items: Step[]
}

export const runsApi = {
  list: async (params?: {
    pipeline_id?: string
    status?: string
    experiment_id?: string
    search?: string
    page?: number
    page_size?: number
  }): Promise<PaginatedResponse<PipelineRun>> => {
    return apiClient.get<PaginatedResponse<PipelineRun>>('/runs', {
      params: {
        pipeline_id: params?.pipeline_id,
        status: params?.status,
        experiment_id: params?.experiment_id,
        search: params?.search,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 20,
      },
    })
  },

  getById: async (id: string): Promise<PipelineRun> => {
    return apiClient.get<PipelineRun>(`/runs/${id}`)
  },

  update: async (
    id: string,
    data: { status?: string; metrics?: Record<string, number>; error_message?: string }
  ): Promise<PipelineRun> => {
    return apiClient.patch<PipelineRun>(`/runs/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return apiClient.delete(`/runs/${id}`)
  },

  getLogs: async (
    id: string,
    params?: { tail?: number; level?: string }
  ): Promise<RunLogsResponse> => {
    return apiClient.get<RunLogsResponse>(`/runs/${id}/logs`, { params })
  },

  getSteps: async (id: string): Promise<StepsResponse> => {
    return apiClient.get<StepsResponse>(`/runs/${id}/steps`)
  },

  compare: async (id: string, otherId: string): Promise<RunCompareResponse> => {
    return apiClient.get<RunCompareResponse>(`/runs/${id}/compare/${otherId}`)
  },

  addStepLog: async (
    runId: string,
    stepId: string,
    data: { message: string }
  ): Promise<{ message: string }> => {
    return apiClient.post(`/runs/${runId}/steps/${stepId}/logs`, data)
  },
}
