import { useEffect, useState } from 'react'
import {
  GitBranch,
  Box,
  AlertTriangle,
  FlaskConical,
} from 'lucide-react'
import { Skeleton } from '@/components/ui'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi, runsApi } from '@/api/endpoints'
import type { ActivityLog, PipelineRun } from '@/types'
import {
  StatCard,
  PipelinePerformanceChart,
  ModelAccuracyChart,
  ActivePipelines,
  ActivityFeed,
  DriftAlertBanner,
} from './components'

// Stats loaded from API - no hardcoded defaults

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    </div>
  )
}

export function Dashboard() {
  const [mounted, setMounted] = useState(false)
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: () => dashboardApi.getOverview(),
    refetchInterval: 30000,
  })

  const { data: runsData } = useQuery<PipelineRun[]>({
    queryKey: ['runs', 'recent'],
    queryFn: async () => {
      const response = await runsApi.list({ page_size: 5 })
      return response.items || []
    },
    refetchInterval: 10000,
    initialData: [],
  })

  const { data: activities } = useQuery<ActivityLog[]>({
    queryKey: ['dashboard', 'activity'],
    queryFn: async () => {
      const response = await dashboardApi.getActivity(20)
      const items = response.items ?? []
      return items.map(a => ({
        ...a,
        created_at: a.created_at || a.timestamp || new Date().toISOString(),
      }))
    },
    refetchInterval: 30000,
    initialData: [],
  })

  // Handle hydration mismatch for client-only rendering
  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted || isLoading) {
    return <LoadingSkeleton />
  }

  const runs = runsData || []
  const featuresDrifted = stats?.drift?.features_drifted ?? 0

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground mt-1">Real-time ML pipeline monitoring</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Pipelines"
          value={stats?.pipelines.total ?? 0}
          trend="up"
          trendValue="12% today"
          icon={GitBranch}
          color="bg-blue-500"
          status={{ running: stats?.pipelines.running ?? 0 }}
          subtext={`${stats?.pipelines.completed_today ?? 0} completed today`}
        />
        <StatCard
          title="Models in Production"
          value={stats?.models.in_production ?? 0}
          trend="up"
          trendValue="3 new"
          icon={Box}
          color="bg-green-500"
          subtext={`${stats?.models.in_staging ?? 0} in staging`}
        />
        <StatCard
          title="Drift Alerts"
          value={featuresDrifted}
          trend="down"
          trendValue="1 Alert"
          icon={AlertTriangle}
          color="bg-amber-500"
          subtext={`PSI Avg: ${stats?.drift?.drift_ratio?.toFixed(2) ?? 'N/A'}`}
        />
        <StatCard
          title="Active Experiments"
          value={stats?.experiments.active ?? 0}
          icon={FlaskConical}
          color="bg-purple-500"
          subtext={`${stats?.experiments.total_trials ?? 0} trials today`}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PipelinePerformanceChart />
        <ModelAccuracyChart />
      </div>

      {/* Active Runs & Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ActivePipelines runs={runs} />
        <ActivityFeed activities={activities || []} />
      </div>

      {/* Drift Alert Banner */}
      {featuresDrifted > 0 && (
        <DriftAlertBanner featuresDrifted={featuresDrifted} />
      )}
    </div>
  )
}
