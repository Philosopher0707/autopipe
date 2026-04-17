import { apiClient } from '../client'
import type { Model, ModelVersion, PaginatedResponse } from '@/types'

export interface ModelComparisonResponse {
  model_name: string
  version_a: number
  version_b: number
  metric_differences: Record<string, number>
  is_better: boolean
  report: string
}

export const modelsApi = {
  list: async (params?: {
    framework?: string
    task_type?: string
    tag?: string
    search?: string
    page?: number
    page_size?: number
  }): Promise<PaginatedResponse<Model>> => {
    return apiClient.get<PaginatedResponse<Model>>('/', {
      params: {
        framework: params?.framework,
        task_type: params?.task_type,
        tag: params?.tag,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 20,
      },
    })
  },

  getById: async (id: string): Promise<Model> => {
    return apiClient.get<Model>(`/${id}`)
  },

  create: async (data: Partial<Model>): Promise<Model> => {
    return apiClient.post<Model>('/', data)
  },

  update: async (id: string, data: Partial<Model>): Promise<Model> => {
    return apiClient.put<Model>(`/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return apiClient.delete(`/${id}`)
  },

  listVersions: async (
    id: string,
    params?: { page?: number; page_size?: number }
  ): Promise<PaginatedResponse<ModelVersion>> => {
    return apiClient.get<PaginatedResponse<ModelVersion>>(`/${id}/versions`, { params })
  },

  getVersion: async (id: string, version: number): Promise<ModelVersion> => {
    return apiClient.get<ModelVersion>(`/${id}/versions/${version}`)
  },

  createVersion: async (
    id: string,
    data: Partial<ModelVersion>
  ): Promise<ModelVersion> => {
    return apiClient.post<ModelVersion>(`/${id}/versions`, data)
  },

  updateVersionStage: async (
    id: string,
    version: number,
    data: { stage: string; description?: string }
  ): Promise<ModelVersion> => {
    return apiClient.put<ModelVersion>(`/${id}/versions/${version}/stage`, data)
  },

  compare: async (data: {
    model_id: string
    version_a: number
    version_b: number
  }): Promise<ModelComparisonResponse> => {
    return apiClient.post<ModelComparisonResponse>('/compare', data)
  },
}
