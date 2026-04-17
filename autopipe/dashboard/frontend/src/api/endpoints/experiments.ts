import { apiClient } from '../client'
import type { Experiment, PaginatedResponse, PipelineRun } from '@/types'

export interface ExperimentDetail extends Experiment {
  runs: PipelineRun[]
}

export interface ExperimentRunsResponse {
  items: PipelineRun[]
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
}
