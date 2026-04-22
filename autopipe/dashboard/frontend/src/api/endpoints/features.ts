import { apiClient } from '../client'
import type {
  FeatureExtractRequest,
  FeatureExtractResponse,
  FeaturePreviewResponse,
  FeatureTransformsResponse,
} from '@/types'

export const featuresApi = {
  extract: async (body: FeatureExtractRequest): Promise<FeatureExtractResponse> => {
    return apiClient.post('/features/extract', body)
  },

  preview: async (pipelineId: string): Promise<FeaturePreviewResponse> => {
    return apiClient.get(`/features/preview/${pipelineId}`)
  },

  getTransforms: async (runId: string): Promise<FeatureTransformsResponse> => {
    return apiClient.get('/charts/feature-transforms', { params: { run_id: runId } })
  },
}