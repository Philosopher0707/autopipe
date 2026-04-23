import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { chartsApi, runsApi } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import { useWorkspace } from '../WorkspaceContext'
import type { PanelLayout } from '../WorkspaceContext'

interface LinePlotPanelProps {
  panel: PanelLayout
}

const PALETTE = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1']

export function LinePlotPanel({ panel }: LinePlotPanelProps) {
  const { updatePanel } = useWorkspace()
  const { metricName, runIds = [], showLegend = true } = panel.config
  const [showConfig, setShowConfig] = useState(false)

  // Fetch available metrics if none selected
  const { data: availableMetrics } = useQuery({
    queryKey: ['charts', 'available-metrics', runIds],
    queryFn: () => chartsApi.getAvailableMetrics(runIds),
    enabled: runIds.length > 0,
  })

  // Fetch metric series data
  const { data: seriesData, isLoading, error } = useQuery({
    queryKey: ['charts', 'metric-series', metricName, runIds],
    queryFn: () =>
      chartsApi.getMetricSeries({
        run_ids: runIds ?? [],
        metric_name: metricName ?? 'loss',
      }),
    enabled: !!metricName && runIds.length > 0 && runIds.length <= 10,
  })

  // Fetch run metadata for legend labels
  const { state } = useWorkspace()
  const { data: runsData } = useQuery({
    queryKey: ['runs', 'list', { page_size: 100, project_id: state.selectedProjectId }],
    queryFn: () => runsApi.list({ page_size: 100, project_id: state.selectedProjectId }),
  })

  const runMap = useMemo(() => {
    const map: Record<string, { run_number: number; pipeline_name?: string }> = {}
    runsData?.items?.forEach((r) => {
      map[r.id] = { run_number: r.run_number, pipeline_name: r.pipeline_name }
    })
    return map
  }, [runsData])

  // Merge series into chart data: every point has step_index, and each run gets a column
  const chartData = useMemo(() => {
    if (!seriesData || seriesData.length === 0) return []
    const stepMap = new Map<number, Record<string, number | null>>()
    seriesData.forEach((series) => {
      series.points.forEach((pt) => {
        const step = pt.step_index ?? 0
        const existing = stepMap.get(step) ?? {}
        const key = `run_${series.run_id}`
        stepMap.set(step, { ...existing, [key]: pt.value, step })
      })
    })
    return Array.from(stepMap.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([, data]) => data)
  }, [seriesData])

  const runSeries = seriesData ?? []

  const errorMessage = error
    ? (error as Error).message || 'Failed to load metric data'
    : null

  const handleConfigSave = (newMetric: string) => {
    updatePanel(panel.id, { config: { ...panel.config, metricName: newMetric } })
    setShowConfig(false)
  }

  return (
    <PanelWrapper
      panel={panel}
      onConfigure={() => setShowConfig(!showConfig)}
      isLoading={isLoading}
      error={errorMessage}
    >
      {showConfig ? (
        <ConfigModal
          metrics={availableMetrics?.metrics ?? []}
          currentMetric={metricName ?? ''}
          onSave={handleConfigSave}
          onCancel={() => setShowConfig(false)}
        />
      ) : chartData.length === 0 ? (
        <EmptyState runIds={runIds} />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="step"
              type="number"
              fontSize={12}
              tickFormatter={(v) => `${v}`}
              label={{ value: 'Step', position: 'insideBottomRight', offset: -5, fontSize: 11 }}
            />
            <YAxis
              fontSize={12}
              label={{ value: metricName || 'Value', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                fontSize: 12,
              }}
              formatter={(value: number, name: string) => {
                const runId = name.replace('run_', '')
                const info = runMap[runId]
                const label = info ? `Run #${info.run_number}` : name
                return [typeof value === 'number' ? value.toFixed(4) : value, label]
              }}
            />
            {showLegend && <Legend fontSize={11} />}
            {runSeries.map((s, i) => (
              <Line
                key={s.run_id}
                type="monotone"
                dataKey={`run_${s.run_id}`}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                name={`Run #${s.run_number}`}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </PanelWrapper>
  )
}

function ConfigModal({
  metrics,
  currentMetric,
  onSave,
  onCancel,
}: {
  metrics: string[]
  currentMetric: string
  onSave: (m: string) => void
  onCancel: () => void
}) {
  const [selected, setSelected] = useState(currentMetric)

  return (
    <div className="space-y-4 py-2">
      <p className="text-xs text-muted-foreground">Select a metric to display</p>
      <div className="max-h-48 overflow-y-auto border border-border rounded-md divide-y divide-border">
        {metrics.length === 0 ? (
          <div className="p-3 text-sm text-muted-foreground">No metrics available. Log metrics first.</div>
        ) : (
          metrics.map((m) => (
            <button
              key={m}
              onClick={() => setSelected(m)}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                selected === m
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'hover:bg-muted'
              }`}
            >
              {m}
            </button>
          ))
        )}
      </div>
      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded-md border border-border hover:bg-muted transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={() => onSave(selected)}
          className="px-3 py-1.5 text-xs rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Apply
        </button>
      </div>
    </div>
  )
}

function EmptyState({ runIds }: { runIds: string[] }) {
  if (runIds.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
        <p>No runs selected.</p>
        <p className="text-xs mt-1">Select runs from the toolbar to populate this chart.</p>
      </div>
    )
  }
  return (
    <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
      <p>No metric data for the selected runs.</p>
    </div>
  )
}
