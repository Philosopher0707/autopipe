import { lazy, Suspense, type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores'

const Layout = lazy(() => import('@/components/layout/Layout').then((module) => ({ default: module.Layout })))
const Dashboard = lazy(() => import('@/pages/dashboard/Dashboard').then((module) => ({ default: module.Dashboard })))
const Login = lazy(() => import('@/pages/auth/Login').then((module) => ({ default: module.Login })))
const PipelineList = lazy(() => import('@/pages/pipelines/PipelineList').then((module) => ({ default: module.PipelineList })))
const PipelineDetail = lazy(() => import('@/pages/pipelines/PipelineDetail').then((module) => ({ default: module.PipelineDetail })))
const RunList = lazy(() => import('@/pages/runs/RunList').then((module) => ({ default: module.RunList })))
const RunDetail = lazy(() => import('@/pages/runs/RunDetail').then((module) => ({ default: module.RunDetail })))
const RunCompare = lazy(() => import('@/pages/runs/RunCompare').then((module) => ({ default: module.RunCompare })))
const ModelList = lazy(() => import('@/pages/models/ModelList').then((module) => ({ default: module.ModelList })))
const ModelDetail = lazy(() => import('@/pages/models/ModelDetail').then((module) => ({ default: module.ModelDetail })))
const ExperimentList = lazy(() => import('@/pages/experiments/ExperimentList').then((module) => ({ default: module.ExperimentList })))
const ExperimentDetail = lazy(() => import('@/pages/experiments/ExperimentDetail').then((module) => ({ default: module.ExperimentDetail })))
const DriftList = lazy(() => import('@/pages/drift/DriftList').then((module) => ({ default: module.DriftList })))
const DriftReport = lazy(() => import('@/pages/drift/DriftReport').then((module) => ({ default: module.DriftReport })))
const Workspace = lazy(() => import('@/pages/workspace/Workspace').then((module) => ({ default: module.Workspace })))
const SettingsPage = lazy(() => import('@/pages/settings/Settings').then((module) => ({ default: module.SettingsPage })))
const TeamPage = lazy(() => import('@/pages/settings/Team').then((module) => ({ default: module.TeamPage })))
const ExplainabilityPage = lazy(() => import('@/pages/explainability/ExplainabilityPage').then((module) => ({ default: module.ExplainabilityPage })))
const AutomlPage = lazy(() => import('@/pages/automl/AutoMLPage').then((module) => ({ default: module.AutoMLPage })))
const FeatureEngineeringPage = lazy(() => import('@/pages/features/FeaturesPage').then((module) => ({ default: module.FeaturesPage })))
const ProjectsPage = lazy(() => import('@/pages/projects/ProjectsPage').then((module) => ({ default: module.ProjectsPage })))
const ProfilePage = lazy(() => import('@/pages/profile/ProfilePage').then((module) => ({ default: module.ProfilePage })))

function PageFallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
      Loading...
    </div>
  )
}

function Suspended({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<PageFallback />}>
      {children}
    </Suspense>
  )
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function AuthRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function ProtectedLayout({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <Suspended>
        <Layout>{children}</Layout>
      </Suspended>
    </ProtectedRoute>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <AuthRoute>
            <Suspended>
              <Login />
            </Suspended>
          </AuthRoute>
        }
      />

      <Route
        path="/"
        element={
          <ProtectedLayout>
            <Dashboard />
          </ProtectedLayout>
        }
      />

      <Route
        path="/pipelines"
        element={
          <ProtectedLayout>
            <PipelineList />
          </ProtectedLayout>
        }
      />
      <Route
        path="/pipelines/new"
        element={
          <ProtectedLayout>
            <PipelineDetail />
          </ProtectedLayout>
        }
      />
      <Route
        path="/pipelines/:pipelineId"
        element={
          <ProtectedLayout>
            <PipelineDetail />
          </ProtectedLayout>
        }
      />

      <Route
        path="/runs"
        element={
          <ProtectedLayout>
            <RunList />
          </ProtectedLayout>
        }
      />
      <Route
        path="/runs/:runId"
        element={
          <ProtectedLayout>
            <RunDetail />
          </ProtectedLayout>
        }
      />

      <Route
        path="/runs/compare"
        element={
          <ProtectedLayout>
            <RunCompare />
          </ProtectedLayout>
        }
      />

      <Route
        path="/workspace"
        element={
          <ProtectedLayout>
            <Workspace />
          </ProtectedLayout>
        }
      />

      <Route
        path="/models"
        element={
          <ProtectedLayout>
            <ModelList />
          </ProtectedLayout>
        }
      />
      <Route
        path="/models/new"
        element={
          <ProtectedLayout>
            <ModelDetail />
          </ProtectedLayout>
        }
      />
      <Route
        path="/models/:modelId"
        element={
          <ProtectedLayout>
            <ModelDetail />
          </ProtectedLayout>
        }
      />

      <Route
        path="/experiments"
        element={
          <ProtectedLayout>
            <ExperimentList />
          </ProtectedLayout>
        }
      />
      <Route
        path="/experiments/new"
        element={
          <ProtectedLayout>
            <ExperimentDetail />
          </ProtectedLayout>
        }
      />
      <Route
        path="/experiments/:experimentId"
        element={
          <ProtectedLayout>
            <ExperimentDetail />
          </ProtectedLayout>
        }
      />

      <Route
        path="/drift"
        element={
          <ProtectedLayout>
            <DriftList />
          </ProtectedLayout>
        }
      />
      <Route
        path="/drift/:reportId"
        element={
          <ProtectedLayout>
            <DriftReport />
          </ProtectedLayout>
        }
      />

      <Route
        path="/explainability"
        element={
          <ProtectedLayout>
            <ExplainabilityPage />
          </ProtectedLayout>
        }
      />

      <Route
        path="/automl"
        element={
          <ProtectedLayout>
            <AutomlPage />
          </ProtectedLayout>
        }
      />

      <Route
        path="/features"
        element={
          <ProtectedLayout>
            <FeatureEngineeringPage />
          </ProtectedLayout>
        }
      />

      <Route
        path="/settings"
        element={
          <ProtectedLayout>
            <SettingsPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/team"
        element={
          <ProtectedLayout>
            <TeamPage />
          </ProtectedLayout>
        }
      />

      <Route
        path="/projects"
        element={
          <ProtectedLayout>
            <ProjectsPage />
          </ProtectedLayout>
        }
      />

      <Route
        path="/profile"
        element={
          <ProtectedLayout>
            <ProfilePage />
          </ProtectedLayout>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
