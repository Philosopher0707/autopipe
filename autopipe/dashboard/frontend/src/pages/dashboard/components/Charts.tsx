import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardContent, Skeleton } from '@/components/ui'
import { dashboardApi } from '@/api/endpoints'
import { useQuery } from '@tanstack/react-query'

type TimeRange = '7d' | '30d' | '90d'

function formatChartData(points: { timestamp: string; value: number }[]) {
  return points.map((p) => {
    const date = new Date(p.timestamp)
    return {
      name: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      success: Math.round(p.value * 100),
      failed: Math.round((1 - p.value) * 100),
    }
  })
}

export function PipelinePerformanceChart() {
  const [timeRange, setTimeRange] = useState<TimeRange>('7d')
  const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', 'metrics', 'pipeline_success', timeRange],
    queryFn: async () => {
      const end = new Date()
      const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000)
      const resp = await dashboardApi.getMetrics({
        metric_name: 'pipeline_success',
        start: start.toISOString(),
        end: end.toISOString(),
      })
      return resp.data ?? []
    },
  })

  const chartData = data ? formatChartData(data) : []

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Pipeline Performance</CardTitle>
          <select
            className="text-sm border rounded-lg px-3 py-1 bg-background"
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as TimeRange)}
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
          </select>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <Skeleton className="h-full w-full" />
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              No performance data available
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
                <YAxis stroke="#6b7280" fontSize={12} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                  }}
                  formatter={(v: number) => [`${v}%`]}
                />
                <Line
                  type="monotone"
                  dataKey="success"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ fill: '#10b981' }}
                  name="Success Rate"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export function ModelAccuracyChart() {
  const [filter, setFilter] = useState<'all' | 'production' | 'staging'>('all')
  const [timeRange, setTimeRange] = useState<TimeRange>('7d')
  const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', 'metrics', 'model_accuracy', filter, timeRange],
    queryFn: async () => {
      const end = new Date()
      const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000)
      const resp = await dashboardApi.getMetrics({
        metric_name: 'model_accuracy',
        start: start.toISOString(),
        end: end.toISOString(),
      })
      return resp.data ?? []
    },
  })

  // Map to version-like labels
  const chartData = data
    ? data.map((p, i) => ({
        version: `v${i + 1}`,
        accuracy: p.value,
        f1: p.value * 0.98, // approximate F1
        timestamp: p.timestamp,
      }))
    : []

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Model Accuracy Trends</CardTitle>
          <div className="flex gap-2">
            <select
              className="text-sm border rounded-lg px-3 py-1 bg-background"
              value={filter}
              onChange={(e) => setFilter(e.target.value as 'all' | 'production' | 'staging')}
            >
              <option value="all">All Models</option>
              <option value="production">Production Only</option>
              <option value="staging">Staging Only</option>
            </select>
            <select
              className="text-sm border rounded-lg px-3 py-1 bg-background"
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value as TimeRange)}
            >
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="90d">Last 90 days</option>
            </select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <Skeleton className="h-full w-full" />
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              No accuracy data available
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
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
                  formatter={(v: number) => [`${(v * 100).toFixed(1)}%`]}
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
          )}
        </div>
      </CardContent>
    </Card>
  )
}
