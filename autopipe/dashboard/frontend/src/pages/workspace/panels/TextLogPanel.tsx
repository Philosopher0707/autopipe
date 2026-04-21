import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { runsApi, type RunLogsResponse } from '@/api/endpoints'
import { PanelWrapper } from '../PanelWrapper'
import type { PanelLayout } from '../WorkspaceContext'

interface TextLogPanelProps {
  panel: PanelLayout
}

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: 'text-gray-500',
  INFO: 'text-blue-500',
  WARN: 'text-amber-500',
  WARNING: 'text-amber-500',
  ERROR: 'text-red-500',
  CRITICAL: 'text-red-700',
  FATAL: 'text-red-700',
}

export function TextLogPanel({ panel }: TextLogPanelProps) {
  const { runIds = [] } = panel.config
  const [selectedRunId, setSelectedRunId] = useState<string | null>(runIds[0] ?? null)
  const [filterLevel, setFilterLevel] = useState<string | 'ALL'>('ALL')
  const [search, setSearch] = useState('')
  const [tail, setTail] = useState(100)

  const shouldFetch = selectedRunId != null
  const {
    data: logsData,
    isLoading,
    error,
  } = useQuery<RunLogsResponse>({
    queryKey: ['runs', 'logs', selectedRunId, filterLevel, tail],
    queryFn: () => runsApi.getLogs(selectedRunId!, { tail, level: filterLevel === 'ALL' ? undefined : filterLevel }),
    enabled: shouldFetch,
    refetchInterval: shouldFetch ? 3000 : false,
  })

  const errMsg = error instanceof Error ? error.message : null

  const filteredLogs = useMemo(() => {
    if (!logsData?.logs) return []
    let logs = logsData.logs
    if (search.trim()) {
      const s = search.toLowerCase()
      logs = logs.filter((l) => l.message.toLowerCase().includes(s) || (l.step && l.step.toLowerCase().includes(s)))
    }
    return logs
  }, [logsData, search])

  if (runIds.length === 0) {
    return (
      <PanelWrapper panel={panel}>
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <p>No runs selected.</p>
          <p className="text-xs mt-1">Select a run to view its logs.</p>
        </div>
      </PanelWrapper>
    )
  }

  return (
    <PanelWrapper panel={panel} isLoading={isLoading} error={errMsg}>
      <div className="flex flex-col h-full gap-2">
        {/* Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Run selector */}
          <select
            value={selectedRunId ?? ''}
            onChange={(e) => setSelectedRunId(e.target.value)}
            className="text-[10px] rounded border border-border bg-background px-1.5 py-1"
          >
            {runIds.map((id, i) => (
              <option key={id} value={id}>Run {i + 1} ({id.slice(0, 8)}...)</option>
            ))}
          </select>

          {/* Level filter */}
          <select
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value)}
            className="text-[10px] rounded border border-border bg-background px-1.5 py-1"
          >
            <option value="ALL">All levels</option>
            <option value="DEBUG">Debug</option>
            <option value="INFO">Info</option>
            <option value="WARN">Warn</option>
            <option value="ERROR">Error</option>
          </select>

          {/* Tail count */}
          <select
            value={tail}
            onChange={(e) => setTail(Number(e.target.value))}
            className="text-[10px] rounded border border-border bg-background px-1.5 py-1"
          >
            <option value={50}>50 lines</option>
            <option value={100}>100 lines</option>
            <option value={200}>200 lines</option>
            <option value={500}>500 lines</option>
            <option value={1000}>1000 lines</option>
          </select>

          {/* Search */}
          <div className="relative flex-1 min-w-[120px]">
            <Search className="absolute left-1.5 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
            <input
              type="text"
              placeholder="Filter logs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full text-[10px] pl-5 pr-5 py-1 rounded border border-border bg-background"
            />
            {search && (
              <button onClick={() => setSearch('')} className="absolute right-1.5 top-1/2 -translate-y-1/2">
                <X className="w-3 h-3 text-muted-foreground" />
              </button>
            )}
          </div>
        </div>

        {/* Log lines */}
        <div className="flex-1 overflow-auto min-h-0 bg-muted/20 rounded border border-border/50 font-mono text-[10px] leading-4">
          {filteredLogs.length === 0 ? (
            <div className="p-3 text-muted-foreground text-center">No logs to display.</div>
          ) : (
            <div className="divide-y divide-border/30">
              {filteredLogs.map((log, i) => (
                <div key={i} className="px-2 py-0.5 hover:bg-muted/30 transition-colors">
                  <span className="text-muted-foreground/60">
                    {log.step && <span className="font-medium text-muted-foreground/80 mr-1">[{log.step}]</span>}
                    {log.timestamp && <span className="mr-1">{new Date(log.timestamp).toLocaleTimeString([], {hour12: false})}</span>}
                  </span>
                  <span className={`font-semibold mr-1.5 ${LEVEL_COLORS[log.level] ?? 'text-muted-foreground'}`}>
                    {log.level}
                  </span>
                  <span className="text-foreground">{log.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="text-[9px] text-muted-foreground text-right">
          {filteredLogs.length} log lines · auto-refresh
        </div>
      </div>
    </PanelWrapper>
  )
}
