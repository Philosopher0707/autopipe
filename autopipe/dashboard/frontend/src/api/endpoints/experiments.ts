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
    return apiClient.get<PaginatedResponse<Experiment>>('/', {
      params: {
        search: params?.search,
        status: params?.status,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 20,
      },
    })
  },

  getById: async (id: string): Promise<Experiment> => {
    return apiClient.get<Experiment>(`/${id}`)
  },

  create: async (data: Partial<Experiment>): Promise<Experiment> => {
    return apiClient.post<Experiment>('/', data)
  },

  update: async (id: string, data: Partial<Experiment>): Promise<Experiment> => {
    return apiClient.put<Experiment>(`/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return apiClient.delete(`/${id}`)
  },

  listTrials: async (id: string): Promise<TrialsResponse> => {
    return apiClient.get<TrialsResponse>(`/${id}/trials`)
  },

  getTrial: async (experimentId: string, trialId: string): Promise<Trial> => {
    return apiClient.get<Trial>(`/${experimentId}/trials/${trialId}`)
  },

  getVisualization: async (id: string): Promise<unknown> => {
    return apiClient.get(`/${id}/visualize`)
  },
}
