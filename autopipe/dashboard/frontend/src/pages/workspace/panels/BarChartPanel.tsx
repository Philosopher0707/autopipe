import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { chartsApi, runsApi } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import { useWorkspace } from '../WorkspaceContext'
import type { PanelLayout } from '../WorkspaceContext'

interface BarChartPanelProps {
  panel: PanelLayout
}

const PALETTE = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']

export function BarChartPanel({ panel }: BarChartPanelProps) {
  const { updatePanel } = useWorkspace()
  const { metricName, runIds = [] } = panel.config
  const [showConfig, setShowConfig] = useState(false)

  const { data: availableMetrics } = useQuery({
    queryKey: ['charts', 'available-metrics', runIds],
    queryFn: () => chartsApi.getAvailableMetrics(runIds),
    enabled: runIds.length > 0,
  })

  const { data: runsData } = useQuery({
    queryKey: ['runs', 'list', { page_size: 100 }],
    queryFn: () => runsApi.list({ page_size: 100 }),
  })

  // Build chart data from run metrics
  const chartData = useMemo(() => {
    if (!runsData?.items || !metricName) return []
    const filtered = runIds.length > 0
      ? runsData.items.filter((r) => runIds.includes(r.id))
      : runsData.items
    return filtered
      .filter((r) => r.metrics && metricName in r.metrics)
      .map((r) => ({
        run: `Run #${r.run_number}`,
        run_id: r.id,
        value: Number(r.metrics![metricName]) ?? 0,
        status: r.status,
      }))
      .sort((a, b) => b.value - a.value)
  }, [runsData, metricName, runIds])

  const errorMessage = null

  const handleConfigSave = (newMetric: string) => {
    updatePanel(panel.id, { config: { ...panel.config, metricName: newMetric } })
    setShowConfig(false)
  }

  return (
    <PanelWrapper
      panel={panel}
      onConfigure={() => setShowConfig(!showConfig)}
      isLoading={false}
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
        <EmptyState metricName={metricName} runIds={runIds} />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="run" fontSize={11} />
            <YAxis fontSize={12} />
            <Tooltip
              cursor={{ fill: '#f3f4f6' }}
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                fontSize: 12,
              }}
            />
            <Bar
              dataKey="value"
              fill={PALETTE[0]}
              radius={[4, 4, 0, 0]}
              maxBarSize={60}
            />
          </BarChart>
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
      <div className="max-h-48 overflow-y-auto border border-border rounded-md">
        {metrics.map((m) => (
          <button
            key={m}
            onClick={() => setSelected(m)}
            className={`w-full text-left px-3 py-2 text-sm transition-colors ${
              selected === m ? 'bg-primary/10 text-primary font-medium' : 'hover:bg-muted'
            }`}
          >
            {m}
          </button>
        ))}
        {metrics.length === 0 && (
          <div className="p-3 text-sm text-muted-foreground">No metrics found.</div>
        )}
      </div>
      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded-md border border-border hover:bg-muted"
        >
          Cancel
        </button>
        <button
          onClick={() => onSave(selected)}
          className="px-3 py-1.5 text-xs rounded-md bg-primary text-primary-foreground hover:bg-primary/90"
        >
          Apply
        </button>
      </div>
    </div>
  )
}

function EmptyState({ metricName, runIds }: { metricName?: string; runIds: string[] }) {
  if (runIds.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
        <p>No runs selected.</p>
        <p className="text-xs mt-1">Select runs from the toolbar to populate this chart.</p>
      </div>
    )
  }
  if (!metricName) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
        <p>No metric configured. Click settings to choose a metric.</p>
      </div>
    )
  }
  return (
    <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
      <p>No data for metric "{metricName}" on selected runs.</p>
    </div>
  )
}
