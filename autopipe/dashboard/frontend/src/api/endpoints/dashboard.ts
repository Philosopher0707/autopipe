import { apiClient } from '../client'
import type {
  DashboardStats,
  ActivityLog,
  ResourceUsageResponse,
} from '@/types'

export const dashboardApi = {
  /** GET /api/v1/dashboard/overview */
  getOverview: async (): Promise<DashboardStats> => {
    return apiClient.get<DashboardStats>('/dashboard/overview')
  },

  /** GET /api/v1/dashboard/counts — sidebar badge counts */
  getCounts: async (): Promise<{
    pipelines_total: number
    pipelines_active: number
    experiments_total: number
    experiments_active: number
    models_total: number
    models_in_production: number
    drift_alerts_unacknowledged: number
    drift_features_drifted: number
  }> => {
    return apiClient.get('/dashboard/counts')
  },

  /** GET /api/v1/dashboard/activity */
  getActivity: async (limit = 20): Promise<{ items: ActivityLog[] }> => {
    return apiClient.get<{ items: ActivityLog[] }>('/dashboard/activity', {
      params: { page_size: limit },
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

  /** GET /api/v1/dashboard/resources */
  getResources: async (hours = 24, project_id?: string): Promise<ResourceUsageResponse> => {
    return apiClient.get<ResourceUsageResponse>('/dashboard/resources', {
      params: { hours, project_id },
    })
  },
}
