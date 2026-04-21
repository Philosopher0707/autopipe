import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { chartsApi, runsApi } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import { useWorkspace } from '../WorkspaceContext'
import type { PanelLayout } from '../WorkspaceContext'

interface HistogramPanelProps {
  panel: PanelLayout
}

const PALETTE = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444']

function computeHistogram(values: number[], binCount: number) {
  if (values.length === 0) return []
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) return [{ range: `${min.toFixed(3)}`, count: values.length, low: min, high: max }]
  const step = (max - min) / binCount
  const bins = Array.from({ length: binCount }, (_, i) => {
    const low = min + i * step
    const high = i === binCount - 1 ? max : min + (i + 1) * step
    return {
      range: `${low.toFixed(2)}–${high.toFixed(2)}`,
      count: 0,
      low,
      high,
    }
  })
  for (const v of values) {
    const idx = Math.min(Math.floor((v - min) / step), binCount - 1)
    bins[idx].count++
  }
  return bins.filter((b) => b.count > 0)
}

export function HistogramPanel({ panel }: HistogramPanelProps) {
  const { updatePanel } = useWorkspace()
  const { metricName, runIds = [] } = panel.config
  const [showConfig, setShowConfig] = useState(false)
  const [binCount, setBinCount] = useState(10)

  const { data: availableMetrics } = useQuery({
    queryKey: ['charts', 'available-metrics', runIds],
    queryFn: () => chartsApi.getAvailableMetrics(runIds),
    enabled: runIds.length > 0,
  })

  const { data: runsData } = useQuery({
    queryKey: ['runs', 'list', { page_size: 100 }],
    queryFn: () => runsApi.list({ page_size: 100 }),
  })

  const histogramData = useMemo(() => {
    if (!runsData?.items || !metricName) return []
    const filtered = runIds.length > 0
      ? runsData.items.filter((r) => runIds.includes(r.id))
      : runsData.items
    const values = filtered
      .map((r) => Number(r.metrics?.[metricName]))
      .filter((v) => !Number.isNaN(v))
    return computeHistogram(values, binCount)
  }, [runsData, metricName, runIds, binCount])

  const handleConfigSave = (newMetric: string) => {
    updatePanel(panel.id, { config: { ...panel.config, metricName: newMetric } })
    setShowConfig(false)
  }

  return (
    <PanelWrapper
      panel={panel}
      onConfigure={() => setShowConfig(!showConfig)}
      isLoading={false}
      error={null}
    >
      {showConfig ? (
        <div className="space-y-3 py-2">
          <p className="text-xs text-muted-foreground">Select a metric for histogram distribution</p>
          <div className="max-h-48 overflow-y-auto border border-border rounded-md">
            {(availableMetrics?.metrics ?? []).map((m) => (
              <button
                key={m}
                onClick={() => handleConfigSave(m)}
                className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                  metricName === m ? 'bg-primary/10 text-primary font-medium' : 'hover:bg-muted'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Bins:</span>
            <input
              type="range"
              min={5}
              max={30}
              value={binCount}
              onChange={(e) => setBinCount(Number(e.target.value))}
              className="w-24"
            />
            <span className="text-xs">{binCount}</span>
          </div>
          <button
            onClick={() => setShowConfig(false)}
            className="text-xs px-3 py-1.5 rounded-md border border-border hover:bg-muted"
          >
            Close
          </button>
        </div>
      ) : histogramData.length === 0 ? (
        <EmptyState metricName={metricName} runIds={runIds} />
      ) : (
        <div className="flex flex-col h-full">
          <div className="text-[10px] text-muted-foreground mb-1">
            {metricName} distribution (n={histogramData.reduce((a, b) => a + b.count, 0)})
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={histogramData} margin={{ top: 5, right: 10, bottom: 20, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="range" tick={{ fontSize: 9 }} interval={0} angle={-30} textAnchor="end" height={50} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  fontSize: 12,
                }}
              />
              <Bar dataKey="count" >
                {histogramData.map((_, i) => (
                  <Cell key={i} fill={PALETTE[i % PALETTE.length]} radius={2} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </PanelWrapper>
  )
}

function EmptyState({ metricName, runIds }: { metricName?: string; runIds: string[] }) {
  if (runIds.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
        <p>No runs selected.</p>
        <p className="text-xs mt-1">Select runs from the toolbar.</p>
      </div>
    )
  }
  if (!metricName) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
        <p>No metric configured.</p>
        <p className="text-xs mt-1">Click settings to choose a metric.</p>
      </div>
    )
  }
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
      <p>No numeric data for <span className="font-medium">{metricName}</span>.</p>
    </div>
  )
}
