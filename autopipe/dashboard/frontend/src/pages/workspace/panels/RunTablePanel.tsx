import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowUpDown, ArrowDown, ArrowUp } from 'lucide-react'
import { runsApi } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import { useWorkspace } from '../WorkspaceContext'
import type { PanelLayout } from '../WorkspaceContext'

interface RunTablePanelProps {
  panel: PanelLayout
}

type SortKey = 'run_number' | 'status' | 'duration_seconds' | 'created_at'
type SortDir = 'asc' | 'desc'

interface SortState {
  key: SortKey
  dir: SortDir
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800 animate-pulse',
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
}

function MiniSparkline({ values, width = 60, height = 20 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return <span className="text-[10px] text-muted-foreground">—</span>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width
    const y = height - ((v - min) / range) * height
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke="#3b82f6"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {values.length > 0 && (
        <circle cx={width} cy={height - ((values[values.length - 1] - min) / range) * height} r={2} fill="#3b82f6" />
      )}
    </svg>
  )
}

export function RunTablePanel({ panel }: RunTablePanelProps) {
  const { runIds = [] } = panel.config
  const [sort, setSort] = useState<SortState>({ key: 'run_number', dir: 'desc' })
  const { state } = useWorkspace()

  const { data: runsData, isLoading } = useQuery({
    queryKey: ['runs', 'list', { page_size: 100, project_id: state.selectedProjectId }],
    queryFn: () => runsApi.list({ page_size: 100, project_id: state.selectedProjectId }),
  })

  const handleSort = (key: SortKey) => {
    setSort((prev) => ({
      key,
      dir: prev.key === key && prev.dir === 'asc' ? 'desc' : 'asc',
    }))
  }

  const rows = useMemo(() => {
    if (!runsData?.items) return []
    const filtered = runIds.length > 0
      ? runsData.items.filter((r) => runIds.includes(r.id))
      : runsData.items

    const sorted = [...filtered].sort((a, b) => {
      const dir = sort.dir === 'asc' ? 1 : -1
      const av = a[sort.key] ?? 0
      const bv = b[sort.key] ?? 0
      if (typeof av === 'string' && typeof bv === 'string') return av.localeCompare(bv) * dir
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
      return String(av).localeCompare(String(bv)) * dir
    })

    return sorted
  }, [runsData, runIds, sort])

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sort.key !== col) return <ArrowUpDown className="w-3 h-3 text-muted-foreground/50" />
    return sort.dir === 'asc'
      ? <ArrowUp className="w-3 h-3 text-primary" />
      : <ArrowDown className="w-3 h-3 text-primary" />
  }

  return (
    <PanelWrapper panel={panel} isLoading={isLoading} error={null}>
      {rows.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <p>No runs to display.</p>
          {runIds.length === 0 && <p className="text-xs mt-1">Select runs from the toolbar.</p>}
        </div>
      ) : (
        <div className="flex-1 overflow-auto min-h-0">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-background z-10">
              <tr className="border-b border-border">
                <th className="text-left px-2 py-1.5 font-medium text-muted-foreground cursor-pointer hover:text-foreground" onClick={() => handleSort('run_number')}>
                  <span className="flex items-center gap-1">Run # <SortIcon col="run_number" /></span>
                </th>
                <th className="text-left px-2 py-1.5 font-medium text-muted-foreground cursor-pointer hover:text-foreground" onClick={() => handleSort('status')}>
                  <span className="flex items-center gap-1">Status <SortIcon col="status" /></span>
                </th>
                <th className="text-left px-2 py-1.5 font-medium text-muted-foreground cursor-pointer hover:text-foreground" onClick={() => handleSort('duration_seconds')}>
                  <span className="flex items-center gap-1">Duration <SortIcon col="duration_seconds" /></span>
                </th>
                <th className="text-left px-2 py-1.5 font-medium text-muted-foreground">Metrics</th>
                <th className="text-left px-2 py-1.5 font-medium text-muted-foreground">Spark</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((run) => {
                const metricEntries = run.metrics ? Object.entries(run.metrics).filter(([, v]) => typeof v === 'number') : []
                const metricValues = metricEntries.map(([, v]) => Number(v))
                return (
                  <tr key={run.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                    <td className="px-2 py-1.5 font-medium">#{run.run_number}</td>
                    <td className="px-2 py-1.5">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium ${STATUS_COLORS[run.status] ?? 'bg-gray-100 text-gray-800'}`}>
                        {run.status}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-muted-foreground">
                      {run.duration_seconds != null ? `${run.duration_seconds.toFixed(1)}s` : '—'}
                    </td>
                    <td className="px-2 py-1.5">
                      {metricEntries.length === 0 ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {metricEntries.slice(0, 3).map(([k, v]) => (
                            <span key={k} className="inline-flex items-center gap-0.5 bg-muted px-1.5 py-0.5 rounded text-[10px]">
                              {k}: {typeof v === 'number' ? v.toFixed(3) : v}
                            </span>
                          ))}
                          {metricEntries.length > 3 && (
                            <span className="text-[10px] text-muted-foreground">+{metricEntries.length - 3}</span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-2 py-1.5">
                      <MiniSparkline values={metricValues} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </PanelWrapper>
  )
}
