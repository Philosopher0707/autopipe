import { apiClient } from '../client'
import type { PaginatedResponse, Project } from '@/types'

export const projectsApi = {
  list: async (params?: {
    search?: string
    status?: string
    skip?: number
    limit?: number
  }): Promise<PaginatedResponse<Project>> => {
    return apiClient.get<PaginatedResponse<Project>>('/projects', {
      params: {
        search: params?.search,
        status: params?.status,
        skip: params?.skip ?? 0,
        limit: params?.limit ?? 20,
      },
    })
  },

  getById: async (id: string): Promise<Project> => {
    return apiClient.get<Project>(`/projects/${id}`)
  },

  create: async (data: Partial<Project>): Promise<Project> => {
    return apiClient.post<Project>('/projects', data)
  },

  update: async (id: string, data: Partial<Project>): Promise<Project> => {
    return apiClient.patch<Project>(`/projects/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return apiClient.delete(`/projects/${id}`)
  },
}
