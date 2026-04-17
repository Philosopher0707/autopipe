import { apiClient } from '../client'
import { type DriftReport, type DriftAlert } from '@/types'

export interface DriftTrigger {
  model_version_id: string
  current_dataset: string
  reference_dataset?: string
  method?: 'psi' | 'ks' | 'chi2' | 'wasserstein' | 'all'
  threshold?: number
}

export const driftApi = {
  listReports: (params?: { model_id?: string; drift_detected?: boolean }) =>
    apiClient.get<DriftReport[]>('/drift', { params }),
  
  getReport: (id: string) => apiClient.get<DriftReport>(`/drift/${id}`),
  
  trigger: (data: DriftTrigger) => apiClient.post<{ id: string }>('/drift/detect', data),
  
  getLatest: (modelId?: string) =>
    apiClient.get<DriftReport>('/drift/latest', { params: modelId ? { model_id: modelId } : undefined }),
  
  // Alerts
  listAlerts: (params?: { severity?: string; acknowledged?: boolean }) =>
    apiClient.get<DriftAlert[]>('/drift/alerts', { params }),
  
  acknowledgeAlert: (id: string) =>
    apiClient.post<void>(`/drift/alerts/${id}/acknowledge`),
}
