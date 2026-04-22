import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardContent, Skeleton } from '@/components/ui'
import { chartsApi } from '@/api/endpoints'
import { useQuery } from '@tanstack/react-query'

interface TrainingMetricsChartProps {
  runId: string
}

type MetricTab = 'loss' | 'accuracy'

export function TrainingMetricsChart({ runId }: TrainingMetricsChartProps) {
  const [activeTab, setActiveTab] = useState<MetricTab>('loss')

  const { data, isLoading } = useQuery({
    queryKey: ['charts', 'training-metrics-trace', runId],
    queryFn: () => chartsApi.getTrainingMetricsTrace(runId),
    enabled: !!runId,
  })

  const points = data?.points ?? []

  const hasLoss = points.some((p) => p.loss != null || p.val_loss != null)
  const hasAccuracy = points.some((p) => p.accuracy != null || p.val_accuracy != null)

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Training Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (points.length === 0 || (!hasLoss && !hasAccuracy)) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Training Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64 text-sm text-muted-foreground">
            No training metrics available
          </div>
        </CardContent>
      </Card>
    )
  }

  const tabs: { key: MetricTab; label: string }[] = []
  if (hasLoss) tabs.push({ key: 'loss', label: 'Loss' })
  if (hasAccuracy) tabs.push({ key: 'accuracy', label: 'Accuracy' })

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Training Metrics</CardTitle>
          {tabs.length > 1 && (
            <div className="flex gap-1">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                    activeTab === tab.key
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted hover:bg-muted/80'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="epoch"
                stroke="#6b7280"
                fontSize={12}
                label={{ value: 'Epoch', position: 'insideBottomRight', offset: -5 }}
              />
              <YAxis stroke="#6b7280" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                }}
                formatter={(v: number) => [v != null ? v.toFixed(4) : '--']}
              />
              <Legend />
              {activeTab === 'loss' && (
                <>
                  <Line
                    type="monotone"
                    dataKey="loss"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#ef4444' }}
                    name="Train Loss"
                  />
                  <Line
                    type="monotone"
                    dataKey="val_loss"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#3b82f6' }}
                    name="Validation Loss"
                  />
                </>
              )}
              {activeTab === 'accuracy' && (
                <>
                  <Line
                    type="monotone"
                    dataKey="accuracy"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#10b981' }}
                    name="Train Accuracy"
                  />
                  <Line
                    type="monotone"
                    dataKey="val_accuracy"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#8b5cf6' }}
                    name="Validation Accuracy"
                  />
                </>
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
