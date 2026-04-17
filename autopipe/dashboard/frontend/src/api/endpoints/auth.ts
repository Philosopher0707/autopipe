import { apiClient } from '../client'
import type { User } from '@/types'

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface LoginCredentials {
  username: string
  password: string
}

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<TokenResponse> => {
    return apiClient.post<TokenResponse>('/auth/login/json', credentials)
  },

  register: async (data: {
    username: string
    email: string
    password: string
    full_name?: string
    role?: string
  }): Promise<User> => {
    return apiClient.post<User>('/auth/register', data)
  },

  getMe: async (): Promise<User> => {
    return apiClient.get<User>('/auth/me')
  },

  logout: async (): Promise<void> => {
    // Server-side logout if applicable
    return Promise.resolve()
  },
}
