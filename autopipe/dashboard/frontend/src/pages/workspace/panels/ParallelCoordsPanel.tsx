import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { runsApi } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import { useWorkspace } from '../WorkspaceContext'
import type { PanelLayout } from '../WorkspaceContext'

interface ParallelCoordsPanelProps {
  panel: PanelLayout
}

const RUN_COLORS = [
  '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444',
  '#06b6d4', '#f97316', '#84cc16', '#d946ef', '#6b7280',
]

export function ParallelCoordsPanel({ panel }: ParallelCoordsPanelProps) {
  const { runIds = [] } = panel.config
  const { state } = useWorkspace()
  const { data: runsData, isLoading } = useQuery({
    queryKey: ['runs', 'list', { page_size: 100, project_id: state.selectedProjectId }],
    queryFn: () => runsApi.list({ page_size: 100, project_id: state.selectedProjectId }),
  })

  const filtered = useMemo(() => {
    if (!runsData?.items) return []
    return runIds.length > 0
      ? runsData.items.filter((r) => runIds.includes(r.id))
      : runsData.items
  }, [runsData, runIds])

  // Extract numeric parameters and metrics from run configs to plot axes
  const axisKeys = useMemo(() => {
    const paramKeys = new Set<string>()
    const metricKeys = new Set<string>()
    for (const r of filtered) {
      Object.entries(r.config ?? {}).forEach(([k, v]) => {
        if (typeof v === 'number') paramKeys.add(k)
      })
      Object.entries(r.metrics ?? {}).forEach(([k, v]) => {
        if (typeof v === 'number') metricKeys.add(k)
      })
    }
    return {
      params: Array.from(paramKeys).sort(),
      metrics: Array.from(metricKeys).sort(),
    }
  }, [filtered])

  if (runIds.length === 0) {
    return (
      <PanelWrapper panel={panel}>
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <p>No runs selected.</p>
          <p className="text-xs mt-1">Select runs to visualize their configuration sweep.</p>
        </div>
      </PanelWrapper>
    )
  }

  if (axisKeys.params.length === 0 && axisKeys.metrics.length === 0) {
    return (
      <PanelWrapper panel={panel} isLoading={isLoading}>
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <p>No numeric parameters or metrics found.</p>
          <p className="text-xs mt-1">Runs need numeric config values or metrics for parallel coordinates.</p>
        </div>
      </PanelWrapper>
    )
  }

  return (
    <PanelWrapper panel={panel} isLoading={isLoading}>
      <ParallelCoordsChart runs={filtered} axisKeys={axisKeys} />
    </PanelWrapper>
  )
}

function ParallelCoordsChart({
  runs,
  axisKeys,
}: {
  runs: Array<{ id: string; run_number: number; config?: Record<string, unknown>; metrics?: Record<string, unknown> }>
  axisKeys: { params: string[]; metrics: string[] }
}) {
  const [activeMetric, setActiveMetric] = useState<string | null>(
    axisKeys.metrics.length > 0 ? axisKeys.metrics[0] : null
  )
  const [showMetrics, setShowMetrics] = useState(axisKeys.metrics.length > 0)

  const allAxes = showMetrics && activeMetric
    ? [...axisKeys.params, activeMetric]
    : axisKeys.params

  // Compute normalized scales per axis
  const axisRanges = useMemo(() => {
    const ranges: Record<string, { min: number; max: number; range: number }> = {}
    for (const key of allAxes) {
      let values: number[] = []
      if (showMetrics && key === activeMetric) {
        values = runs.map((r) => {
          const v = r.metrics?.[key]
          return typeof v === 'number' ? v : 0
        }).filter((v) => v !== 0 || runs.some((r) => r.metrics?.[key] === 0))
      } else {
        values = runs.map((r) => {
          const v = r.config?.[key]
          return typeof v === 'number' ? v : 0
        }).filter((v) => v !== 0 || runs.some((r) => r.config?.[key] === 0))
      }
      const min = Math.min(...values)
      const max = Math.max(...values)
      ranges[key] = { min, max, range: max - min || 1 }
    }
    return ranges
  }, [allAxes, runs])

  const width = 800
  const height = 300
  const paddingLeft = 60
  const paddingRight = 60
  const paddingTop = 20
  const paddingBottom = 40
  const innerWidth = width - paddingLeft - paddingRight
  const innerHeight = height - paddingTop - paddingBottom

  const xPositions = useMemo(() => {
    const n = allAxes.length
    if (n <= 1) return allAxes.map(() => paddingLeft + innerWidth / 2)
    return allAxes.map((_, i) => paddingLeft + (i / (n - 1)) * innerWidth)
  }, [allAxes, innerWidth])

  function getY(key: string, run: typeof runs[0]) {
    const val = key === activeMetric && showMetrics
      ? Number(run.metrics?.[key] ?? 0)
      : Number(run.config?.[key] ?? 0)
    const { min, range } = axisRanges[key] ?? { min: 0, range: 1 }
    return paddingTop + innerHeight - ((val - min) / range) * innerHeight
  }

  return (
    <div className="flex flex-col h-full">
      {/* Controls */}
      {axisKeys.metrics.length > 0 && (
        <div className="flex items-center gap-2 mb-2">
          <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <input
              type="checkbox"
              checked={showMetrics}
              onChange={(e) => setShowMetrics(e.target.checked)}
              className="rounded"
            />
            Color by metric
          </label>
          {showMetrics && (
            <select
              value={activeMetric ?? ''}
              onChange={(e) => setActiveMetric(e.target.value)}
              className="text-[10px] rounded border border-border bg-background px-1.5 py-0.5"
            >
              {axisKeys.metrics.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          )}
        </div>
      )}

      <div className="flex-1 overflow-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
          {/* Axes */}
          {allAxes.map((key, i) => {
            const x = xPositions[i]
            return (
              <g key={key}>
                {/* Axis line */}
                <line
                  x1={x}
                  y1={paddingTop}
                  x2={x}
                  y2={paddingTop + innerHeight}
                  stroke="#d1d5db"
                  strokeWidth={1}
                />
                {/* Axis labels */}
                <text
                  x={x}
                  y={paddingTop + innerHeight + 12}
                  textAnchor="end"
                  transform={`rotate(-30, ${x}, ${paddingTop + innerHeight + 12})`}
                  fontSize={9}
                  fill="#6b7280"
                >
                  {key.length > 18 ? key.slice(0, 18) + '...' : key}
                </text>
                {/* Min/max labels */}
                <text x={x + 4} y={paddingTop} fontSize={8} fill="#9ca3af">
                  {(axisRanges[key]?.max ?? 0).toFixed(3)}
                </text>
                <text x={x + 4} y={paddingTop + innerHeight} fontSize={8} fill="#9ca3af">
                  {(axisRanges[key]?.min ?? 0).toFixed(3)}
                </text>
              </g>
            )
          })}

          {/* Connecting lines for each run */}
          {runs.map((run, runIdx) => {
            const pts = allAxes.map((key, i) => ({
              x: xPositions[i],
              y: getY(key, run),
            }))
            const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
            return (
              <path
                key={run.id}
                d={d}
                fill="none"
                stroke={RUN_COLORS[runIdx % RUN_COLORS.length]}
                strokeWidth={1.5}
                opacity={0.7}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            )
          })}

          {/* Points */}
          {runs.map((run, runIdx) => (
            <g key={`pts-${run.id}`}>
              {allAxes.map((key, i) => {
                const x = xPositions[i]
                const y = getY(key, run)
                return (
                  <circle
                    key={key}
                    cx={x}
                    cy={y}
                    r={2.5}
                    fill={RUN_COLORS[runIdx % RUN_COLORS.length]}
                    opacity={0.9}
                  />
                )
              })}
            </g>
          ))}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex gap-2 flex-wrap mt-1 max-h-6 overflow-hidden">
        {runs.slice(0, 10).map((r, i) => (
          <span key={r.id} className="inline-flex items-center gap-1 text-[9px] text-muted-foreground">
            <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ backgroundColor: RUN_COLORS[i] }} />
            Run #{r.run_number}
          </span>
        ))}
        {runs.length > 10 && <span className="text-[9px] text-muted-foreground">+{runs.length - 10}</span>}
      </div>
    </div>
  )
}
