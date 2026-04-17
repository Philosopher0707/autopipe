import { apiClient } from '../client'
import type { Experiment, Trial, PaginatedResponse } from '@/types'

export interface ExperimentDetail extends Experiment {
  trials: Trial[]
}

export interface TrialsResponse {
  items: Trial[]
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
    return apiClient.put<Experiment>(`/experiments/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return apiClient.delete(`/experiments/${id}`)
  },

  listTrials: async (id: string): Promise<TrialsResponse> => {
    return apiClient.get<TrialsResponse>(`/experiments/${id}/trials`)
  },

  getTrial: async (experimentId: string, trialId: string): Promise<Trial> => {
    return apiClient.get<Trial>(`/experiments/${experimentId}/trials/${trialId}`)
  },

  getVisualization: async (id: string): Promise<unknown> => {
    return apiClient.get(`/experiments/${id}/visualize`)
  },
}
