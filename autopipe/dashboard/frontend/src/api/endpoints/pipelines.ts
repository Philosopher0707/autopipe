import { apiClient } from '../client'
import type { Pipeline, PipelineRun, PaginatedResponse } from '@/types'

export const pipelinesApi = {
  list: async (params?: {
    search?: string
    status?: string
    tag?: string
    skip?: number
    limit?: number
    sort_by?: string
    sort_order?: string
  }): Promise<PaginatedResponse<Pipeline>> => {
    return apiClient.get<PaginatedResponse<Pipeline>>('/pipelines', {
      params: {
        search: params?.search,
        status: params?.status,
        tag: params?.tag,
        skip: params?.skip ?? 0,
        limit: params?.limit ?? 20,
        sort_by: params?.sort_by ?? 'created_at',
        sort_order: params?.sort_order ?? 'desc',
      },
    })
  },

  getById: async (id: string): Promise<Pipeline> => {
    return apiClient.get<Pipeline>(`/pipelines/${id}`)
  },

  create: async (data: Partial<Pipeline>): Promise<Pipeline> => {
    return apiClient.post<Pipeline>('/pipelines', data)
  },

  update: async (id: string, data: Partial<Pipeline>): Promise<Pipeline> => {
    return apiClient.put<Pipeline>(`/pipelines/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return apiClient.delete(`/pipelines/${id}`)
  },

  triggerRun: async (id: string, configOverride?: Record<string, unknown>): Promise<PipelineRun> => {
    return apiClient.post<PipelineRun>(`/pipelines/${id}/runs`, configOverride)
  },

  listRuns: async (
    id: string,
    params?: { skip?: number; limit?: number; status?: string }
  ): Promise<PaginatedResponse<PipelineRun>> => {
    return apiClient.get<PaginatedResponse<PipelineRun>>(`/pipelines/${id}/runs`, { params })
  },
}
