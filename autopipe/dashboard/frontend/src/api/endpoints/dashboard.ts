import { apiClient } from '../client'
import type {
  DashboardStats,
  ActivityLog,
} from '@/types'

export const dashboardApi = {
  /** GET /api/v1/dashboard/overview */
  getOverview: async (): Promise<DashboardStats> => {
    return apiClient.get<DashboardStats>('/dashboard/overview')
  },

  /** GET /api/v1/dashboard/activity */
  getActivity: async (limit = 20): Promise<{ items: ActivityLog[] }> => {
    return apiClient.get<{ items: ActivityLog[] }>('/dashboard/activity', {
      params: { limit },
    })
  },

  /** GET /api/v1/dashboard/health */
  getHealth: async (): Promise<{ status: string; services?: Record<string, string> }> => {
    return apiClient.get('/dashboard/health')
  },

  /** GET /api/v1/dashboard/metrics */
  getMetrics: async (params?: {
    metric_name?: string
    pipeline_id?: string
    start?: string
    end?: string
  }): Promise<{ data: Array<{ timestamp: string; value: number }> }> => {
    return apiClient.get('/dashboard/metrics', { params })
  },
}
