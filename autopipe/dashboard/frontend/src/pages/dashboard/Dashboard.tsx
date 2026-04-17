import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  GitBranch,
  Box,
  AlertTriangle,
  FlaskConical,
  TrendingUp,
  Clock,
  ArrowRight,
  Activity,
} from 'lucide-react'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Badge,
  Skeleton,
} from '@/components/ui'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi, runsApi } from '@/api/endpoints'
import { cn, formatRelativeTime, getStatusBgColor, formatDuration } from '@/utils/helpers'
import type { ActivityLog, PipelineRun } from '@/types'

// Mock data for charts until backend provides real data
const performanceData = [
  { name: 'Mon', success: 12, failed: 2 },
  { name: 'Tue', success: 19, failed: 3 },
  { name: 'Wed', success: 15, failed: 1 },
  { name: 'Thu', success: 25, failed: 4 },
  { name: 'Fri', success: 22, failed: 2 },
  { name: 'Sat', success: 30, failed: 1 },
  { name: 'Sun', success: 28, failed: 2 },
]

const accuracyData = [
  { version: 'v1.0', accuracy: 0.87, f1: 0.85 },
  { version: 'v1.1', accuracy: 0.89, f1: 0.87 },
  { version: 'v1.2', accuracy: 0.88, f1: 0.86 },
  { version: 'v1.3', accuracy: 0.91, f1: 0.89 },
  { version: 'v2.0', accuracy: 0.92, f1: 0.90 },
  { version: 'v2.1', accuracy: 0.94, f1: 0.92 },
  { version: 'v2.2', accuracy: 0.942, f1: 0.925 },
]

function StatCard({
  title,
  value,
  subtext,
  trend,
  trendValue,
  icon: Icon,
  color,
  status,
}: {
  title: string
  value: string | number
  subtext?: string
  trend?: 'up' | 'down'
  trendValue?: string
  icon: React.ElementType
  color: string
  status?: { running: number }
}) {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className={cn('p-3 rounded-lg', color)}>
            <Icon className="w-5 h-5 text-white" />
          </div>
          {trend && (
            <Badge
              variant={trend === 'up' ? 'default' : 'destructive'}
              className="text-xs"
            >
              {trend === 'up' ? '+' : ''}
              {trendValue}
            </Badge>
          )}
        </div>
        <div className="mt-4">
          <h3 className="text-2xl font-bold text-foreground">{value}</h3>
          <p className="text-sm text-muted-foreground">{title}</p>
          {subtext && <p className="text-xs text-muted-foreground mt-1">{subtext}</p>}
          {status && (
            <div className="flex items-center gap-2 mt-2 text-xs">
              <span className="flex items-center text-blue-600">
                <span className="w-2 h-2 rounded-full bg-blue-500 mr-1 animate-pulse" />
                {status.running} Running
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function ActivityIcon({ action }: { action: string }) {
  const config: Record<string, { icon: React.ElementType; color: string }> = {
    run_completed: { icon: Activity, color: 'bg-green-100 text-green-600' },
    run_failed: { icon: AlertTriangle, color: 'bg-red-100 text-red-600' },
    run_started: { icon: Clock, color: 'bg-blue-100 text-blue-600' },
    run_triggered: { icon: GitBranch, color: 'bg-indigo-100 text-indigo-600' },
    model_promoted: { icon: TrendingUp, color: 'bg-blue-100 text-blue-600' },
    drift_alert: { icon: AlertTriangle, color: 'bg-red-100 text-red-600' },
    experiment_started: { icon: FlaskConical, color: 'bg-purple-100 text-purple-600' },
    system_update: { icon: Activity, color: 'bg-gray-100 text-gray-600' },
  }

  const { icon: Icon, color } = config[action] || config.system_update

  return (
    <div className={cn('w-8 h-8 rounded-full flex items-center justify-center', color)}>
      <Icon className="w-4 h-4" />
    </div>
  )
}

export function Dashboard() {
  const [mounted, setMounted] = useState(false)
  const navigate = useNavigate()

  // Handle hydration mismatch for client-only rendering
  useEffect(() => {
    setMounted(true)
  }, [])

  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: () => dashboardApi.getOverview(),
    refetchInterval: 30000,
    // Fallback to mock data if API fails - use null-safe values for hydration
    initialData: {
      pipelines: { total: 42, running: 5, completed_today: 15, failed_today: 2, avg_duration: '12m 30s', success_rate: 88 },
      models: { total: 8, in_production: 8, in_staging: 4, recent_versions: 2 },
      drift: { alerts_today: 2, features_drifted: 3, drift_ratio: 0.28, last_check: null },
      experiments: { total: 10, active: 3, completed_today: 8, total_trials: 156 },
    },
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

  const runs = runsData || []

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

  // Don't render time-sensitive content until client-side hydration
  if (!mounted) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    )
  }

  if (isLoading) {
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
          value={stats?.pipelines.total}
          trend="up"
          trendValue="12% today"
          icon={GitBranch}
          color="bg-blue-500"
          status={{ running: stats?.pipelines.running }}
          subtext={`${stats?.pipelines.completed_today ?? 0} completed today`}
        />
        <StatCard
          title="Models in Production"
          value={stats?.models.in_production}
          trend="up"
          trendValue="3 new"
          icon={Box}
          color="bg-green-500"
          subtext={`${stats?.models.in_staging ?? 0} in staging`}
        />
        <StatCard
          title="Drift Alerts"
          value={stats?.drift.features_drifted}
          trend="down"
          trendValue="1 Alert"
          icon={AlertTriangle}
          color="bg-amber-500"
          subtext={`PSI Avg: ${stats?.drift.drift_ratio ?? 'N/A'}`}
        />
        <StatCard
          title="Active Experiments"
          value={stats?.experiments.active}
          icon={FlaskConical}
          color="bg-purple-500"
          subtext={`${stats?.experiments.total_trials ?? 0} trials today`}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Pipeline Performance</CardTitle>
              <select className="text-sm border rounded-lg px-3 py-1 bg-background">
                <option>Last 7 days</option>
                <option>Last 30 days</option>
                <option>Last 90 days</option>
              </select>
            </div>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={performanceData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
                  <YAxis stroke="#6b7280" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#fff',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="success"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ fill: '#10b981' }}
                    name="Success"
                  />
                  <Line
                    type="monotone"
                    dataKey="failed"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={{ fill: '#ef4444' }}
                    name="Failed"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Model Accuracy Trends</CardTitle>
              <select className="text-sm border rounded-lg px-3 py-1 bg-background">
                <option>All Models</option>
                <option>Production Only</option>
                <option>Staging Only</option>
              </select>
            </div>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={accuracyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="version" stroke="#6b7280" fontSize={12} />
                  <YAxis
                    domain={[0.8, 1]}
                    stroke="#6b7280"
                    fontSize={12}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#fff',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                    }}
                    formatter={(v: number) => `${(v * 100).toFixed(1)}%`}
                  />
                  <Line
                    type="monotone"
                    dataKey="accuracy"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ fill: '#3b82f6', r: 4 }}
                    name="Accuracy"
                  />
                  <Line
                    type="monotone"
                    dataKey="f1"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dot={{ fill: '#8b5cf6', r: 4 }}
                    name="F1 Score"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Active Runs & Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Pipelines */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Active Pipelines</CardTitle>
              <button className="text-sm text-primary hover:underline flex items-center gap-1">
                View All
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Pipeline
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Status
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Progress
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Duration
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr
                      key={run.id}
                      className="border-b border-border last:border-0 hover:bg-muted/50"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div
                            className={cn(
                              'w-8 h-8 rounded-lg flex items-center justify-center',
                              run.status === 'running'
                                ? 'bg-blue-100'
                                : run.status === 'success'
                                ? 'bg-green-100'
                                : 'bg-amber-100'
                            )}
                          >
                            <Activity
                              className={cn(
                                'w-4 h-4',
                                run.status === 'running'
                                  ? 'text-blue-600'
                                  : run.status === 'success'
                                  ? 'text-green-600'
                                  : 'text-amber-600'
                              )}
                            />
                          </div>
                          <div>
                            <p className="font-medium text-foreground">{run.pipeline_name || run.pipeline_id}</p>
                            <p className="text-xs text-muted-foreground">Run #{run.run_number || run.id.slice(0, 8)}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge className={getStatusBgColor(run.status)}>
                          {run.status === 'running' && (
                            <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5 animate-pulse" />
                          )}
                          {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        {run.status === 'running' && (
                          <>
                            <div className="w-full bg-muted rounded-full h-2 mb-1">
                              <div className="bg-primary h-2 rounded-full" style={{ width: '65%' }} />
                            </div>
                            <span className="text-xs text-muted-foreground">65%</span>
                          </>
                        )}
                        {run.status === 'success' && (
                          <>
                            <div className="w-full bg-muted rounded-full h-2 mb-1">
                              <div className="bg-green-500 h-2 rounded-full" style={{ width: '100%' }} />
                            </div>
                            <span className="text-xs text-muted-foreground">100%</span>
                          </>
                        )}
                        {run.status === 'pending' && (
                          <span className="text-sm text-muted-foreground">Queued</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {run.duration_seconds ? formatDuration(run.duration_seconds) : '--'}
                      </td>
                      <td className="py-3 px-4">
                        <button className="text-sm text-primary hover:underline">
                          {run.status === 'running' ? 'Logs' : 'View'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Activity Feed */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {activities?.map((activity: ActivityLog, idx: number) => (
                <div key={activity.id || idx} className="flex gap-3">
                  <ActivityIcon action={activity.action} />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-foreground">
                      {activity.title || activity.action.replace(/_/g, ' ')}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {activity.description || ''}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatRelativeTime(activity.created_at)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Drift Alert Banner */}
      {(stats?.drift?.features_drifted ?? 0) > 0 && (
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between dark:bg-amber-950/20 dark:border-amber-900">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-amber-900 dark:text-amber-200">Data drift detected in production</p>
            <p className="text-xs text-amber-700 dark:text-amber-300">{stats?.drift?.features_drifted} features have drifted above threshold</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => navigate('/drift')} className="px-4 py-2 bg-white border border-amber-300 text-amber-700 rounded-lg text-sm font-medium hover:bg-amber-50 dark:bg-transparent dark:text-amber-300 dark:border-amber-700">
            View Details
          </button>
        </div>
      </div>
      )}
    </div>
  )
}
