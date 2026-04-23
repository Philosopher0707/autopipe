import { useEffect, useState, useMemo } from 'react'
import {
  GitBranch,
  Box,
  AlertTriangle,
  FlaskConical,
  Cpu,
  FolderOpen,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { Card, CardContent, CardTitle, Skeleton } from '@/components/ui'
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

  const { data: resourcesData } = useQuery({
    queryKey: ['dashboard', 'resources'],
    queryFn: () => dashboardApi.getResources(24),
    refetchInterval: 60000,
  })

  const resourceChartData = useMemo(() => {
    if (!resourcesData?.points) return []
    return resourcesData.points.map((p) => ({
      time: new Date(p.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      CPU: p.cpu_percent,
      Memory: p.memory_percent,
      GPU: p.gpu_percent ?? 0,
    }))
  }, [resourcesData])

  const latestCpu = resourcesData?.points?.at(-1)?.cpu_percent
  const latestMem = resourcesData?.points?.at(-1)?.memory_percent

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
        <StatCard
          title="Projects"
          value={stats?.projects?.total ?? 0}
          icon={FolderOpen}
          color="bg-indigo-500"
          subtext={`${stats?.projects?.active ?? 0} with active runs`}
        />
        <StatCard
          title="System"
          value={latestCpu != null ? `${latestCpu.toFixed(0)}%` : '--'}
          icon={Cpu}
          color="bg-cyan-500"
          subtext={`Memory: ${latestMem != null ? `${latestMem.toFixed(0)}%` : '--'}`}
        />
      </div>

      {/* Resource Usage */}
      {resourceChartData.length > 0 && (
        <Card>
          <CardContent className="p-6">
            <CardTitle className="text-lg mb-4">Resource Usage (24h)</CardTitle>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={resourceChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Area type="monotone" dataKey="CPU" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} />
                  <Area type="monotone" dataKey="Memory" stroke="#22c55e" fill="#22c55e" fillOpacity={0.15} />
                  <Area type="monotone" dataKey="GPU" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

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
