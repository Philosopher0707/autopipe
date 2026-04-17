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
    stage?: string
    search?: string
    page?: number
    page_size?: number
  }): Promise<PaginatedResponse<Model>> => {
    return apiClient.get<PaginatedResponse<Model>>('/models', {
      params: {
        framework: params?.framework,
        task_type: params?.task_type,
        tag: params?.tag,
        stage: params?.stage,
        search: params?.search,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 20,
      },
    })
  },

  getById: async (id: string): Promise<Model> => {
    return apiClient.get<Model>(`/models/${id}`)
  },

  create: async (data: Partial<Model>): Promise<Model> => {
    return apiClient.post<Model>('/models', data)
  },

  update: async (id: string, data: Partial<Model>): Promise<Model> => {
    return apiClient.patch<Model>(`/models/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return apiClient.delete(`/models/${id}`)
  },

  listVersions: async (
    id: string,
    params?: { page?: number; page_size?: number }
  ): Promise<PaginatedResponse<ModelVersion>> => {
    return apiClient.get<PaginatedResponse<ModelVersion>>(`/models/${id}/versions`, { params })
  },

  getVersion: async (id: string, version: number): Promise<ModelVersion> => {
    return apiClient.get<ModelVersion>(`/models/${id}/versions/${version}`)
  },

  createVersion: async (
    id: string,
    data: Partial<ModelVersion>
  ): Promise<ModelVersion> => {
    return apiClient.post<ModelVersion>(`/models/${id}/versions`, data)
  },

  updateVersionStage: async (
    id: string,
    version: number,
    data: { stage: string; description?: string }
  ): Promise<ModelVersion> => {
    return apiClient.post<ModelVersion>(`/models/${id}/versions/${version}/promote`, data)
  },

  compare: async (data: {
    model_id: string
    version_a: number
    version_b: number
  }): Promise<ModelComparisonResponse> => {
    return apiClient.post<ModelComparisonResponse>(`/models/${data.model_id}/compare`, undefined, {
      params: {
        version_a: data.version_a,
        version_b: data.version_b,
      },
    })
  },
}
