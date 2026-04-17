import { apiClient } from '../client'
import { type DriftReport, type DriftAlert, type PaginatedResponse } from '@/types'

export interface DriftTrigger {
  model_id?: string
  current_data_path: string
  reference_data_path?: string
  test_types?: Array<'psi' | 'ks' | 'chi2' | 'wasserstein'>
  threshold?: number
}

export const driftApi = {
  listReports: (params?: { model_id?: string; drift_detected?: boolean; page?: number; page_size?: number }) =>
    apiClient.get<PaginatedResponse<DriftReport>>('/drift', { params }),

  getReport: (id: string) => apiClient.get<DriftReport>(`/drift/${id}`),

  trigger: (data: DriftTrigger) => apiClient.post('/drift/detect', data),

  getLatest: (modelId?: string) =>
    apiClient.get<DriftReport>('/drift/latest', { params: modelId ? { model_id: modelId } : undefined }),

  // Alerts
  listAlerts: (params?: { severity?: string; acknowledged?: boolean; feature?: string; page?: number; page_size?: number }) =>
    apiClient.get<PaginatedResponse<DriftAlert>>('/drift/alerts', { params }),

  acknowledgeAlert: (id: string) =>
    apiClient.post<void>(`/drift/alerts/${id}/acknowledge`),
}
