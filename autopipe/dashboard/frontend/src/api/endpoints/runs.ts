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
    return apiClient.get<PaginatedResponse<PipelineRun>>('/', {
      params: {
        pipeline_id: params?.pipeline_id,
        status: params?.status,
        experiment_id: params?.experiment_id,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 20,
      },
    })
  },

  getById: async (id: string): Promise<PipelineRun> => {
    return apiClient.get<PipelineRun>(`/${id}`)
  },

  update: async (
    id: string,
    data: { status?: string; metrics?: Record<string, number>; error_message?: string }
  ): Promise<PipelineRun> => {
    return apiClient.patch<PipelineRun>(`/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return apiClient.delete(`/${id}`)
  },

  getLogs: async (
    id: string,
    params?: { tail?: number; level?: string }
  ): Promise<RunLogsResponse> => {
    return apiClient.get<RunLogsResponse>(`/${id}/logs`, { params })
  },

  getSteps: async (id: string): Promise<StepsResponse> => {
    return apiClient.get<StepsResponse>(`/${id}/steps`)
  },

  compare: async (id: string, otherId: string): Promise<RunCompareResponse> => {
    return apiClient.get<RunCompareResponse>(`/${id}/compare/${otherId}`)
  },

  addStepLog: async (
    runId: string,
    stepId: string,
    data: { message: string }
  ): Promise<{ message: string }> => {
    return apiClient.post(`/runs/${runId}/steps/${stepId}/logs`, data)
  },
}
