import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GitBranch, Eye, EyeOff, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/stores'
import { authApi } from '@/api/endpoints'
import { cn } from '@/utils/helpers'

export function Login() {
  const navigate = useNavigate()
  const { setUser, setToken } = useAuthStore()
  
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const tokenResponse = await authApi.login({ username, password })
      
      // Store token
      setToken(tokenResponse.access_token)
      localStorage.setItem('auth_token', tokenResponse.access_token)
      
      // Fetch user info
      try {
        const userResponse = await authApi.getMe()
        setUser({
          id: userResponse.id,
          username: userResponse.username,
          email: userResponse.email,
          full_name: userResponse.full_name,
          role: userResponse.role as 'admin' | 'data_scientist' | 'viewer',
          is_active: userResponse.is_active,
          last_login: userResponse.last_login,
        })
      } catch {
        // If getMe fails, use basic user info from token
        setUser({
          id: username,
          username: username,
          email: `${username}@autopipe.io`,
          role: 'data_scientist',
          is_active: true,
        })
      }
      
      navigate('/')
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error?.response?.data?.detail || 'Invalid username or password')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-900 dark:to-slate-800 p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary rounded-2xl mb-4 shadow-lg">
            <GitBranch className="w-8 h-8 text-primary-foreground" />
          </div>
          <h1 className="text-3xl font-bold text-foreground">AutoPipe</h1>
          <p className="text-muted-foreground mt-1">ML Dashboard</p>
        </div>

        {/* Login Card */}
        <div className="bg-card rounded-2xl border border-border shadow-xl p-8">
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-foreground">Sign in</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Enter your credentials to access the dashboard
            </p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-foreground mb-1.5">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                required
                autoComplete="username"
                className="w-full h-10 px-3 border border-input rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-colors"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-foreground mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  className="w-full h-10 px-3 pr-10 border border-input rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className={cn(
                'w-full h-10 bg-primary text-primary-foreground rounded-lg font-medium',
                'hover:bg-primary/90 transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'flex items-center justify-center gap-2'
              )}
            >
              {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          {/* Demo credentials hint */}
          <div className="mt-6 pt-6 border-t border-border">
            <p className="text-xs text-muted-foreground text-center mb-2">Demo credentials</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => { setUsername('admin'); setPassword('admin123') }}
                className="p-2 bg-muted rounded-lg hover:bg-muted/80 text-left transition-colors"
              >
                <span className="font-medium text-foreground">admin</span>
                <br />
                <span className="text-muted-foreground">admin123</span>
              </button>
              <button
                type="button"
                onClick={() => { setUsername('data_scientist'); setPassword('ds123456') }}
                className="p-2 bg-muted rounded-lg hover:bg-muted/80 text-left transition-colors"
              >
                <span className="font-medium text-foreground">data_scientist</span>
                <br />
                <span className="text-muted-foreground">ds123456</span>
              </button>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          AutoPipe Dashboard v1.0.0
        </p>
      </div>
    </div>
  )
}
