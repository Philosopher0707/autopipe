import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Trophy, TrendingUp, TrendingDown } from 'lucide-react'
import { runsApi } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import { useWorkspace } from '../WorkspaceContext'
import type { PanelLayout } from '../WorkspaceContext'

interface MetricSummaryPanelProps {
  panel: PanelLayout
}

interface MetricCard {
  name: string
  value: number | null
  runNumber: number
  runId: string
  best: boolean
  allValues: number[]
}

export function MetricSummaryPanel({ panel }: MetricSummaryPanelProps) {
  const { runIds = [] } = panel.config
  const { state } = useWorkspace()

  const { data: runsData, isLoading } = useQuery({
    queryKey: ['runs', 'list', { page_size: 100, project_id: state.selectedProjectId }],
    queryFn: () => runsApi.list({ page_size: 100, project_id: state.selectedProjectId }),
  })

  const metrics: MetricCard[] = useMemo(() => {
    if (!runsData?.items) return []
    const filtered = runIds.length > 0
      ? runsData.items.filter((r) => runIds.includes(r.id))
      : runsData.items

    // Collect all scalar metrics
    const metricMap = new Map<string, { values: { v: number; runId: string; runNumber: number }[] }>()
    filtered.forEach((r) => {
      if (!r.metrics) return
      Object.entries(r.metrics).forEach(([key, val]) => {
        const num = Number(val)
        if (!Number.isNaN(num)) {
          const existing = metricMap.get(key) ?? { values: [] }
          existing.values.push({ v: num, runId: r.id, runNumber: r.run_number })
          metricMap.set(key, existing)
        }
      })
    })

    return Array.from(metricMap.entries())
      .filter(([, data]) => data.values.length > 0)
      .map(([name, data]) => {
        const keyLower = name.toLowerCase().replace('-', '_')
        const isLowerBetter = ['loss', 'error', 'mse', 'rmse', 'mae', 'duration', 'cost', 'latency'].some(
          (w) => keyLower.includes(w)
        )
        const sorted = [...data.values].sort((a, b) =>
          isLowerBetter ? a.v - b.v : b.v - a.v
        )
        const best = sorted[0]
        return {
          name,
          value: best.v,
          runNumber: best.runNumber,
          runId: best.runId,
          best: true,
          allValues: data.values.map((d) => d.v),
        }
      })
      .sort((a, b) => {
        // Prioritize common metrics
        const priority = { accuracy: 0, loss: 1, f1: 2, precision: 3, recall: 4, auc: 5 }
        const pa = priority[a.name as keyof typeof priority] ?? 99
        const pb = priority[b.name as keyof typeof priority] ?? 99
        return pa - pb
      })
  }, [runsData, runIds])

  return (
    <PanelWrapper panel={panel} isLoading={isLoading} error={null}>
      {metrics.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <p>No metrics found on selected runs.</p>
          {runIds.length === 0 && (
            <p className="text-xs mt-1">Select runs from the toolbar.</p>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-3 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {metrics.map((m) => (
            <div
              key={m.name}
              className="bg-muted/50 rounded-lg p-3 border border-border/50 hover:border-border transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-muted-foreground truncate" title={m.name}>
                  {m.name}
                </span>
                {m.best && (
                  <Trophy className="w-3 h-3 text-amber-500" />
                )}
              </div>
              <div className="text-lg font-semibold">
                {m.value === null ? '--' : typeof m.value === 'number' ? m.value.toFixed(4) : m.value}
              </div>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                {m.allValues.length > 1 && (
                  <>
                    {m.allValues[m.allValues.length - 1] >= (m.allValues[m.allValues.length - 2] ?? 0) ? (
                      <TrendingUp className="w-3 h-3 text-emerald-500" />
                    ) : (
                      <TrendingDown className="w-3 h-3 text-red-500" />
                    )}
                    <span>Run #{m.runNumber}</span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </PanelWrapper>
  )
}
