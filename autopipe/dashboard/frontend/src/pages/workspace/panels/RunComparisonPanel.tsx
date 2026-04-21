import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Trophy } from 'lucide-react'
import { runsApi, type MultiRunCompareResponse } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import type { PanelLayout } from '../WorkspaceContext'

interface RunComparisonPanelProps {
  panel: PanelLayout
}

export function RunComparisonPanel({ panel }: RunComparisonPanelProps) {
  const { runIds = [] } = panel.config

  const shouldCompare = runIds.length >= 2 && runIds.length <= 10
  const {
    data: compareData,
    isLoading,
    error,
  } = useQuery<MultiRunCompareResponse>({
    queryKey: ['runs', 'compare', runIds],
    queryFn: () => runsApi.compareMultiple(runIds),
    enabled: shouldCompare,
  })

  if (runIds.length === 0) {
    return (
      <PanelWrapper panel={panel}>
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <p>No runs selected.</p>
          <p className="text-xs mt-1">Select 2–10 runs to compare.</p>
        </div>
      </PanelWrapper>
    )
  }

  if (runIds.length === 1) {
    return (
      <PanelWrapper panel={panel}>
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <p>Only 1 run selected.</p>
          <p className="text-xs mt-1">Select at least 2 runs to compare.</p>
        </div>
      </PanelWrapper>
    )
  }

  if (runIds.length > 10) {
    return (
      <PanelWrapper panel={panel}>
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <p>Too many runs selected ({runIds.length}).</p>
          <p className="text-xs mt-1">Maximum 10 runs can be compared.</p>
        </div>
      </PanelWrapper>
    )
  }

  const errMsg = error instanceof Error ? error.message : null

  return (
    <PanelWrapper panel={panel} isLoading={isLoading} error={errMsg}>
      {compareData ? (
        <ComparisonView data={compareData} />
      ) : (
        <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
          Loading comparison...
        </div>
      )}
    </PanelWrapper>
  )
}

function ComparisonView({ data }: { data: MultiRunCompareResponse }) {
  const { runs, parameters, metrics, diff_summary } = data
  const [activeTab, setActiveTab] = useState<'params' | 'metrics'>('metrics')

  const runColors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#f97316', '#84cc16', '#d946ef', '#6b7280']

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Run headers */}
      <div className="flex gap-1.5 flex-wrap">
        {runs.map((r, i) => (
          <div key={r.id} className="flex items-center gap-1.5 bg-muted/50 rounded px-2 py-1 text-[10px] border border-border/50">
            <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: runColors[i] }} />
            <span className="font-medium">Run #{r.run_number}</span>
            <span className="text-muted-foreground">{r.status}</span>
            {r.duration_seconds != null && (
              <span className="text-muted-foreground">{r.duration_seconds.toFixed(1)}s</span>
            )}
          </div>
        ))}
      </div>

      {/* Diff summary */}
      <div className="flex gap-3 text-[10px] text-muted-foreground border-b border-border pb-2">
        <span>{diff_summary.total_params} params, {diff_summary.different_params} differ</span>
        <span>{diff_summary.total_metrics} metrics</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        <button
          onClick={() => setActiveTab('metrics')}
          className={`px-2 py-1 text-[10px] font-medium rounded-t transition-colors ${
            activeTab === 'metrics' ? 'bg-muted text-foreground border-b-2 border-primary' : 'text-muted-foreground hover:bg-muted/50'
          }`}
        >
          Metrics
        </button>
        <button
          onClick={() => setActiveTab('params')}
          className={`px-2 py-1 text-[10px] font-medium rounded-t transition-colors ${
            activeTab === 'params' ? 'bg-muted text-foreground border-b-2 border-primary' : 'text-muted-foreground hover:bg-muted/50'
          }`}
        >
          Parameters
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto min-h-0">
        {activeTab === 'metrics' && metrics.length > 0 ? (
          <MetricsTable metrics={metrics} runs={runs} runColors={runColors} />
        ) : activeTab === 'params' && parameters.length > 0 ? (
          <ParamsTable parameters={parameters} runs={runs} />
        ) : (
          <div className="text-center text-xs text-muted-foreground py-4">No {activeTab} to display.</div>
        )}
      </div>
    </div>
  )
}

function MetricsTable({ metrics, runs, runColors }: { metrics: MultiRunCompareResponse['metrics']; runs: MultiRunCompareResponse['runs']; runColors: string[] }) {
  return (
    <div className="overflow-auto">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-background z-10">
          <tr className="border-b border-border">
            <th className="text-left px-2 py-1.5 font-medium text-muted-foreground">Metric</th>
            {runs.map((r, i) => (
              <th key={r.id} className="text-right px-2 py-1.5 font-medium text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: runColors[i] }} />
                  #{r.run_number}
                </span>
              </th>
            ))}
            <th className="text-center px-2 py-1.5 font-medium text-muted-foreground">Best</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((row) => {
            const isBest = (runId: string) => {
              if (row.best_run_id === runId) return 'best'
              return 'normal'
            }
            return (
              <tr key={row.name} className="border-b border-border/50 hover:bg-muted/20">
                <td className="px-2 py-1.5 font-medium">{row.name}</td>
                {runs.map((r) => {
                  const mv = row.values[r.id]
                  const val = mv?.value
                  const delta = mv?.delta_from_baseline
                  const bestStatus = isBest(r.id)
                  return (
                    <td key={r.id} className={`text-right px-2 py-1.5 whitespace-nowrap ${bestStatus === 'best' ? 'bg-primary/5 font-semibold' : ''}`}>
                      <div className="flex items-center justify-end gap-1">
                        {delta != null && delta !== Infinity && delta !== -Infinity && (
                          <span className={`text-[9px] ${delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-600' : 'text-muted-foreground'}`}>
                            {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
                          </span>
                        )}
                        <span>{val != null ? val.toFixed(4) : '—'}</span>
                      </div>
                    </td>
                  )
                })}
                <td className="px-2 py-1.5 text-center">
                  {row.best_run_id && (
                    <Trophy className="w-3 h-3 text-amber-500 inline-block" />
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ParamsTable({ parameters, runs }: { parameters: MultiRunCompareResponse['parameters']; runs: MultiRunCompareResponse['runs'] }) {
  return (
    <div className="overflow-auto">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-background z-10">
          <tr className="border-b border-border">
            <th className="text-left px-2 py-1.5 font-medium text-muted-foreground">Parameter</th>
            {runs.map((r) => (
              <th key={r.id} className="text-right px-2 py-1.5 font-medium text-muted-foreground">Run #{r.run_number}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {parameters.map((row) => (
            <tr
              key={row.name}
              className={`border-b border-border/50 ${row.is_different ? 'bg-amber-50/30' : 'hover:bg-muted/20'}`}
            >
              <td className={`px-2 py-1.5 font-medium ${row.is_different ? 'text-amber-700' : ''}`}>
                {row.name}
                {row.is_different && <span className="text-[9px] ml-1 text-amber-600">*</span>}
              </td>
              {runs.map((r) => {
                const val = row.values[r.id]
                const display = val == null ? '—' : typeof val === 'boolean' ? String(val) : typeof val === 'number' ? val : JSON.stringify(val)
                return (
                  <td key={r.id} className="text-right px-2 py-1.5 text-muted-foreground">{display}</td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
