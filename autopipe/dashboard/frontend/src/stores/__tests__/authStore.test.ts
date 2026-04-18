import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from '../authStore'
import type { AuthUser } from '../authStore'

describe('useAuthStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    })
    localStorage.clear()
  })

  it('starts unauthenticated', () => {
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(state.isAuthenticated).toBe(false)
  })

  it('setUser sets user and isAuthenticated', () => {
    const user: AuthUser = {
      id: '1',
      username: 'testuser',
      email: 'test@example.com',
      role: 'admin',
      is_active: true,
    }
    useAuthStore.getState().setUser(user)
    const state = useAuthStore.getState()
    expect(state.user).toEqual(user)
    expect(state.isAuthenticated).toBe(true)
  })

  it('setUser with null clears authentication', () => {
    const user: AuthUser = {
      id: '1',
      username: 'testuser',
      email: 'test@example.com',
      role: 'admin',
      is_active: true,
    }
    useAuthStore.getState().setUser(user)
    useAuthStore.getState().setUser(null)
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('setToken stores the token', () => {
    useAuthStore.getState().setToken('abc123')
    expect(useAuthStore.getState().token).toBe('abc123')
  })

  it('logout clears all auth state', () => {
    const user: AuthUser = {
      id: '1',
      username: 'testuser',
      email: 'test@example.com',
      role: 'admin',
      is_active: true,
    }
    useAuthStore.getState().setUser(user)
    useAuthStore.getState().setToken('abc123')
    useAuthStore.getState().logout()

    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(state.isAuthenticated).toBe(false)
  })
})