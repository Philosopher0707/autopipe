import { apiClient } from '../client'
import type {
  AutomlTrialsResponse,
  AutomlVisualizationsResponse,
  TrialDetailResponse,
  TrialHistoryResponse,
} from '@/types'

export const automlApi = {
  listTrials: async (params?: {
    experiment_id?: string
    state?: string
    limit?: number
  }): Promise<AutomlTrialsResponse> => {
    return apiClient.get('/trials', { params })
  },

  getTrial: async (trialId: number): Promise<TrialDetailResponse> => {
    return apiClient.get(`/trials/${trialId}`)
  },

  getTrialHistory: async (trialId: number): Promise<TrialHistoryResponse> => {
    return apiClient.get(`/trials/${trialId}/history`)
  },

  getVisualizations: async (experimentId: string): Promise<AutomlVisualizationsResponse> => {
    return apiClient.get('/charts/automl-visualizations', { params: { experiment_id: experimentId } })
  },
}