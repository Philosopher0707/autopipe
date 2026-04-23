import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRightLeft, ChevronDown, ChevronUp } from 'lucide-react'
import { runsApi } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import { useWorkspace } from '../WorkspaceContext'
import type { PanelLayout } from '../WorkspaceContext'

interface ParamImportancePanelProps {
  panel: PanelLayout
}

interface DiffRow {
  param: string
  values: Record<string, string>
  isDifferent: boolean
  metricDeltas: Record<string, number | null>
}

export function ParamImportancePanel({ panel }: ParamImportancePanelProps) {
  const { runIds = [] } = panel.config
  const [showDiffOnly, setShowDiffOnly] = useState(true)
  const [expandedMetrics, setExpandedMetrics] = useState(true)

  const { state } = useWorkspace()
  const { data: runsData, isLoading } = useQuery({
    queryKey: ['runs', 'list', { page_size: 100, project_id: state.selectedProjectId }],
    queryFn: () => runsApi.list({ page_size: 100, project_id: state.selectedProjectId }),
  })

  const diff = useMemo(() => {
    if (!runsData?.items || runIds.length < 2) return { params: [] as DiffRow[], metrics: [] as DiffRow[] }

    const runs = runsData.items.filter((r) => runIds.includes(r.id))
    if (runs.length < 2) return { params: [] as DiffRow[], metrics: [] as DiffRow[] }

    // Build param diffs
    const allParams = new Set<string>()
    runs.forEach((r) => {
      Object.keys(r.config || {}).forEach((k) => allParams.add(k))
    })

    const paramRows: DiffRow[] = Array.from(allParams)
      .sort()
      .map((param) => {
        const values: Record<string, string> = {}
        const rawValues: Set<string> = new Set()
        runs.forEach((r) => {
          const val = r.config?.[param]
          const str = val === undefined ? '—' : JSON.stringify(val)
          values[r.id] = str
          rawValues.add(str)
        })
        return {
          param,
          values,
          isDifferent: rawValues.size > 1,
          metricDeltas: {},
        }
      })

    // Build metric rows with deltas from first run
    const allMetrics = new Set<string>()
    runs.forEach((r) => {
      Object.keys(r.metrics || {}).forEach((k) => allMetrics.add(k))
    })

    const baselineMetrics = runs[0].metrics || {}
    const metricRows: DiffRow[] = Array.from(allMetrics)
      .sort()
      .map((metric) => {
        const values: Record<string, string> = {}
        const metricDeltas: Record<string, number | null> = {}
        const rawValues = new Set<string>()

        const baseline = Number(baselineMetrics[metric])

        runs.forEach((r) => {
          const val = r.metrics?.[metric]
          const str = val === undefined ? '—' : String(Number(val).toFixed(4))
          values[r.id] = str
          rawValues.add(str)

          const numVal = Number(val)
          if (!Number.isNaN(numVal) && !Number.isNaN(baseline) && baseline !== 0) {
            metricDeltas[r.id] = ((numVal - baseline) / Math.abs(baseline)) * 100
          } else {
            metricDeltas[r.id] = null
          }
        })

        return {
          param: metric,
          values,
          isDifferent: rawValues.size > 1,
          metricDeltas,
        }
      })

    return { params: paramRows, metrics: metricRows }
  }, [runsData, runIds])

  const allRunIds = runIds
  const visibleParams = showDiffOnly ? diff.params.filter((p) => p.isDifferent) : diff.params
  const visibleMetrics = showDiffOnly ? diff.metrics.filter((m) => m.isDifferent) : diff.metrics

  return (
    <PanelWrapper panel={panel} isLoading={isLoading} error={null}>
      {runIds.length < 2 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <ArrowRightLeft className="w-6 h-6 mb-2 opacity-50" />
          <p>Select 2+ runs to compare parameters.</p>
        </div>
      ) : (
        <div className="space-y-4 overflow-auto max-h-full">
          {/* Controls */}
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={showDiffOnly}
                onChange={() => setShowDiffOnly(!showDiffOnly)}
                className="rounded border-border"
              />
              Show different only
            </label>
          </div>

          {/* Parameters Table */}
          {visibleParams.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                Parameters (diff)
              </h4>
              <div className="border border-border rounded-lg overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-muted/50 border-b border-border">
                      <th className="text-left py-1.5 px-2 font-medium">Parameter</th>
                      {allRunIds.map((rid) => (
                        <th key={rid} className="text-left py-1.5 px-2 font-medium">
                          Run #{runsData?.items?.find((r) => r.id === rid)?.run_number ?? rid.slice(0, 4)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {visibleParams.map((row) => (
                      <tr key={row.param} className="border-b border-border last:border-0 hover:bg-muted/30">
                        <td className="py-1.5 px-2 font-medium">{row.param}</td>
                        {allRunIds.map((rid) => (
                          <td key={rid} className="py-1.5 px-2">
                            {row.values[rid]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Metrics Table */}
          {visibleMetrics.length > 0 && (
            <div>
              <button
                onClick={() => setExpandedMetrics(!expandedMetrics)}
                className="flex items-center gap-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2"
              >
                {expandedMetrics ? (
                  <ChevronUp className="w-3 h-3" />
                ) : (
                  <ChevronDown className="w-3 h-3" />
                )}
                Metrics ({visibleMetrics.length})
              </button>
              {expandedMetrics && (
                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-muted/50 border-b border-border">
                        <th className="text-left py-1.5 px-2 font-medium">Metric</th>
                        {allRunIds.map((rid, idx) => (
                          <th key={rid} className="text-left py-1.5 px-2 font-medium">
                            {idx === 0 ? 'Baseline' : `Run #${runsData?.items?.find((r) => r.id === rid)?.run_number ?? '?'}`}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleMetrics.map((row) => (
                        <tr key={row.param} className="border-b border-border last:border-0 hover:bg-muted/30">
                          <td className="py-1.5 px-2 font-medium">{row.param}</td>
                          {allRunIds.map((rid, idx) => (
                            <td key={rid} className="py-1.5 px-2">
                              <div className="flex items-center gap-1">
                                <span>{row.values[rid]}</span>
                                {idx > 0 && row.metricDeltas[rid] !== null && row.metricDeltas[rid] !== undefined && (
                                  <span
                                    className={`text-[10px] ${
                                      (row.metricDeltas[rid] ?? 0) >= 0
                                        ? 'text-emerald-600'
                                        : 'text-red-600'
                                    }`}
                                  >
                                    {row.metricDeltas[rid]! >= 0 ? '+' : ''}
                                    {row.metricDeltas[rid]!.toFixed(1)}%
                                  </span>
                                )}
                              </div>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {visibleParams.length === 0 && visibleMetrics.length === 0 && (
            <div className="text-sm text-muted-foreground text-center">
              No differences found between selected runs.
            </div>
          )}
        </div>
      )}
    </PanelWrapper>
  )
}
