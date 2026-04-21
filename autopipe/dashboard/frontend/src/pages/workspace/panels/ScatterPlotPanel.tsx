import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ZAxis,
} from 'recharts'
import { runsApi } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import { useWorkspace } from '../WorkspaceContext'
import type { PanelLayout } from '../WorkspaceContext'

interface ScatterPlotPanelProps {
  panel: PanelLayout
}

const PALETTE = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']

interface DataPoint {
  x: number
  y: number
  run: string
  run_number: number
  size: number
}

export function ScatterPlotPanel({ panel }: ScatterPlotPanelProps) {
  const { updatePanel } = useWorkspace()
  const { xMetric, yMetric, runIds = [] } = panel.config
  const [showConfig, setShowConfig] = useState(false)

  const { data: runsData } = useQuery({
    queryKey: ['runs', 'list', { page_size: 100 }],
    queryFn: () => runsApi.list({ page_size: 100 }),
  })

  // Extract metric keys from all runs
  const allMetricKeys = useMemo(() => {
    const keys = new Set<string>()
    runsData?.items?.forEach((r) => {
      if (r.metrics) Object.keys(r.metrics).forEach((k) => keys.add(k))
    })
    return Array.from(keys).sort()
  }, [runsData])

  // Build scatter data
  const data: DataPoint[] = useMemo(() => {
    if (!xMetric || !yMetric || !runsData?.items) return []
    const filtered = runIds.length > 0
      ? runsData.items.filter((r) => runIds.includes(r.id))
      : runsData.items
    return filtered
      .filter((r) => {
        const m = r.metrics || {}
        return xMetric in m && yMetric in m && m[xMetric] != null && m[yMetric] != null
      })
      .map((r) => ({
        x: Number(r.metrics![xMetric]),
        y: Number(r.metrics![yMetric]),
        run: r.id,
        run_number: r.run_number,
        size: r.duration_seconds ? Math.min(Math.max(r.duration_seconds / 10, 20), 200) : 60,
      }))
  }, [runsData, xMetric, yMetric, runIds])

  const handleConfigSave = (nx: string, ny: string) => {
    updatePanel(panel.id, { config: { ...panel.config, xMetric: nx, yMetric: ny } })
    setShowConfig(false)
  }

  const xLabel = xMetric ?? 'X Metric'
  const yLabel = yMetric ?? 'Y Metric'

  return (
    <PanelWrapper
      panel={panel}
      onConfigure={() => setShowConfig(!showConfig)}
      isLoading={false}
      error={null}
    >
      {showConfig ? (
        <ConfigModal
          metrics={allMetricKeys}
          currentX={xMetric ?? ''}
          currentY={yMetric ?? ''}
          onSave={handleConfigSave}
          onCancel={() => setShowConfig(false)}
        />
      ) : data.length === 0 ? (
        <EmptyState xMetric={xMetric} yMetric={yMetric} runIds={runIds} />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              type="number"
              dataKey="x"
              fontSize={12}
              label={{ value: xLabel, position: 'insideBottomRight', offset: -5, fontSize: 11 }}
            />
            <YAxis
              type="number"
              dataKey="y"
              fontSize={12}
              label={{ value: yLabel, angle: -90, position: 'insideLeft', offset: 10, fontSize: 11 }}
            />
            <ZAxis type="number" dataKey="size" range={[40, 200]} />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                fontSize: 12,
              }}
              formatter={(value: number, name: string) => {
                const label = name === 'x' ? xLabel : yLabel
                return [typeof value === 'number' ? value.toFixed(4) : value, label]
              }}
              labelFormatter={(_, payload) => {
                const p = payload as unknown as Array<{ payload?: DataPoint }> | { payload?: DataPoint }
                const dp = Array.isArray(p) ? p[0]?.payload : p?.payload
                if (!dp) return ''
                return `Run #${dp.run_number}`
              }}
            />
            <Scatter data={data} fill={PALETTE[0]} />
          </ScatterChart>
        </ResponsiveContainer>
      )}
    </PanelWrapper>
  )
}

function ConfigModal({
  metrics,
  currentX,
  currentY,
  onSave,
  onCancel,
}: {
  metrics: string[]
  currentX: string
  currentY: string
  onSave: (x: string, y: string) => void
  onCancel: () => void
}) {
  const [selX, setSelX] = useState(currentX)
  const [selY, setSelY] = useState(currentY)

  return (
    <div className="space-y-4 py-2">
      <div className="space-y-2">
        <label className="text-xs font-medium">X Axis Metric</label>
        <select
          value={selX}
          onChange={(e) => setSelX(e.target.value)}
          className="w-full text-sm border border-border rounded-md px-2 py-1.5 bg-background"
        >
          <option value="">Select metric...</option>
          {metrics.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>
      <div className="space-y-2">
        <label className="text-xs font-medium">Y Axis Metric</label>
        <select
          value={selY}
          onChange={(e) => setSelY(e.target.value)}
          className="w-full text-sm border border-border rounded-md px-2 py-1.5 bg-background"
        >
          <option value="">Select metric...</option>
          {metrics.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>
      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded-md border border-border hover:bg-muted"
        >
          Cancel
        </button>
        <button
          onClick={() => onSave(selX, selY)}
          disabled={!selX || !selY}
          className="px-3 py-1.5 text-xs rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
        >
          Apply
        </button>
      </div>
    </div>
  )
}

function EmptyState({ xMetric, yMetric, runIds }: { xMetric?: string; yMetric?: string; runIds: string[] }) {
  if (runIds.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
        <p>No runs selected.</p>
        <p className="text-xs mt-1">Select runs from the toolbar to populate this chart.</p>
      </div>
    )
  }
  if (!xMetric || !yMetric) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
        <p>Configure X and Y metrics. Click the settings icon.</p>
      </div>
    )
  }
  return (
    <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
      <p>No runs have both "{xMetric}" and "{yMetric}" metrics.</p>
    </div>
  )
}
