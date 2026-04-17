import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { Dashboard } from '@/pages/dashboard/Dashboard'
import { Login } from '@/pages/auth/Login'
import { PipelineList } from '@/pages/pipelines/PipelineList'
import { PipelineDetail } from '@/pages/pipelines/PipelineDetail'
import { RunList } from '@/pages/runs/RunList'
import { RunDetail } from '@/pages/runs/RunDetail'
import { ModelList } from '@/pages/models/ModelList'
import { ModelDetail } from '@/pages/models/ModelDetail'
import { ExperimentList } from '@/pages/experiments/ExperimentList'
import { ExperimentDetail } from '@/pages/experiments/ExperimentDetail'
import { DriftList } from '@/pages/drift/DriftList'
import { DriftReport } from '@/pages/drift/DriftReport'
import { SettingsPage } from '@/pages/settings/Settings'
import { TeamPage } from '@/pages/settings/Team'
import { useAuthStore } from '@/stores'

// Protected route wrapper - requires authentication
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  return <>{children}</>
}

// Auth route wrapper - redirects to dashboard if already logged in
function AuthRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }
  
  return <>{children}</>
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Auth routes */}
      <Route
        path="/login"
        element={
          <AuthRoute>
            <Login />
          </AuthRoute>
        }
      />

      {/* Protected routes with Layout */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Pipelines */}
      <Route
        path="/pipelines"
        element={
          <ProtectedRoute>
            <Layout>
              <PipelineList />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/pipelines/:pipelineId"
        element={
          <ProtectedRoute>
            <Layout>
              <PipelineDetail />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/pipelines/new"
        element={
          <ProtectedRoute>
            <Layout>
              <PipelineDetail />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Runs */}
      <Route
        path="/runs"
        element={
          <ProtectedRoute>
            <Layout>
              <RunList />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/runs/:runId"
        element={
          <ProtectedRoute>
            <Layout>
              <RunDetail />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Models */}
      <Route
        path="/models"
        element={
          <ProtectedRoute>
            <Layout>
              <ModelList />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/models/:modelId"
        element={
          <ProtectedRoute>
            <Layout>
              <ModelDetail />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Experiments */}
      <Route
        path="/experiments"
        element={
          <ProtectedRoute>
            <Layout>
              <ExperimentList />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/experiments/:experimentId"
        element={
          <ProtectedRoute>
            <Layout>
              <ExperimentDetail />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Drift */}
      <Route
        path="/drift"
        element={
          <ProtectedRoute>
            <Layout>
              <DriftList />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/drift/:reportId"
        element={
          <ProtectedRoute>
            <Layout>
              <DriftReport />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Settings */}
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <Layout>
              <SettingsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/team"
        element={
          <ProtectedRoute>
            <Layout>
              <TeamPage />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
