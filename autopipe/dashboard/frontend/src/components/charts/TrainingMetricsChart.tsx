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
import { ChartCard, Skeleton } from '@/components/ui'
import { chartsApi } from '@/api/endpoints'
import { useQuery } from '@tanstack/react-query'
import { useSyncCrosshair } from '@/components/SyncCrosshairProvider'

interface TrainingMetricsChartProps {
  runId: string
}

type MetricTab = 'loss' | 'accuracy'

export function TrainingMetricsChart({ runId }: TrainingMetricsChartProps) {
  const [activeTab, setActiveTab] = useState<MetricTab>('loss')
  const { setActiveLabel } = useSyncCrosshair()

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
      <ChartCard title="Training Metrics">
        <Skeleton className="h-64 w-full" />
      </ChartCard>
    )
  }

  if (points.length === 0 || (!hasLoss && !hasAccuracy)) {
    return (
      <ChartCard title="Training Metrics">
        <div className="flex items-center justify-center h-64 text-sm text-muted-foreground">
          No training metrics available
        </div>
      </ChartCard>
    )
  }

  const tabs: { key: MetricTab; label: string }[] = []
  if (hasLoss) tabs.push({ key: 'loss', label: 'Loss' })
  if (hasAccuracy) tabs.push({ key: 'accuracy', label: 'Accuracy' })

  return (
    <ChartCard
      title="Training Metrics"
      className="relative"
    >
      {tabs.length > 1 && (
        <div className="flex gap-1 mb-4">
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
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={points}
            onMouseMove={(e) => {
              if (e.activeLabel) setActiveLabel(e.activeLabel)
            }}
            onMouseLeave={() => setActiveLabel(null)}
          >
            <defs>
              <linearGradient id="gradLoss" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradValLoss" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradAcc" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradValAcc" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
              </linearGradient>
            </defs>
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
                  fill="url(#gradLoss)"
                />
                <Line
                  type="monotone"
                  dataKey="val_loss"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#3b82f6' }}
                  name="Validation Loss"
                  fill="url(#gradValLoss)"
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
                  fill="url(#gradAcc)"
                />
                <Line
                  type="monotone"
                  dataKey="val_accuracy"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#8b5cf6' }}
                  name="Validation Accuracy"
                  fill="url(#gradValAcc)"
                />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
