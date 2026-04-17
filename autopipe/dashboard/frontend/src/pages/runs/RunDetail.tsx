import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardTitle, Badge } from '@/components/ui'
import { runsApi } from '@/api/endpoints'
import {
  Play, Trash2,
  Clock, ChevronDown, ChevronUp,
  Terminal, BarChart3
} from 'lucide-react'
import { formatDate, formatDuration, getStatusBgColor } from '@/utils/helpers'
import type { PipelineRun } from '@/types'

export function RunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'logs' | 'metrics' >('logs')
  const [logs, setLogs] = useState<string[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)

  const { data: run, isLoading } = useQuery<PipelineRun>({
    queryKey: ['runs', runId],
    queryFn: () => runsApi.get(runId!),
  })

  // Auto-scroll logs
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs])

  // Poll for run updates
  useEffect(() => {
    if (!run || (run.status !== 'running' && run.status !== 'pending')) return

    const interval = setInterval(() => {
      // In real app, fetch run update
    }, 5000)

    return () => clearInterval(interval)
  }, [run])

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-muted rounded w-1/3"></div>
        <div className="h-32 bg-muted rounded"></div>
      </div>
    )
  }

  if (!run) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold">Run not found</h2>
        <button onClick={() => navigate('/runs')} className="mt-4 text-primary">
          Back to runs
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-foreground">
              Run #{runId?.slice(0, 8)}
            </h1>
            <Badge className={getStatusBgColor(run.status)}>
              {run.status}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">
            {run.pipeline_name || run.pipeline_id}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="px-4 py-2 border border-input rounded-lg hover:bg-muted">
            <Terminal className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock className="w-4 h-4" />
              <span className="text-xs">Duration</span>
            </div>
            <p className="text-lg font-semibold mt-1">
              {run.duration_seconds ? formatDuration(run.duration_seconds) : '--'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock className="w-4 h-4" />
              <span className="text-xs">Started</span>
            </div>
            <p className="text-lg font-semibold mt-1">
              {run.started_at ? formatDate(run.started_at) : '--'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock className="w-4 h-4" />
              <span className="text-xs">Completed</span>
            </div>
            <p className="text-lg font-semibold mt-1">
              {run.completed_at ? formatDate(run.completed_at) : '--'}
            </p>
          </CardContent>
        </Card>

        {run.metrics && Object.keys(run.metrics).length > 0 && (
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-muted-foreground">
                <BarChart3 className="w-4 h-4" />
                <span className="text-xs">Metrics</span>
              </div>
              <div className="mt-1 space-y-1">
                {Object.entries(run.metrics).slice(0, 2).map(([key, value]) => (
                  <p key={key} className="text-sm">
                    <span className="text-muted-foreground">{key}: </span>
                    <span className="font-medium">{value}</span>
                  </p>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Steps Section */}
      <Card>
        <CardContent className="p-6">
          <CardTitle className="text-lg mb-4">Steps</CardTitle>
          <div className="space-y-2">
            {['Loading...'].map((stepName, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    run.status === 'success' ? 'bg-green-500' :
                    run.status === 'failed' ? 'bg-red-500' :
                    run.status === 'running' ? 'bg-blue-500' : 'bg-amber-500'
                  }`} />
                  <span>{stepName}</span>
                </div>
                <span className="text-sm text-muted-foreground">--</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Logs Section */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <CardTitle className="text-lg">Execution Logs</CardTitle>
            <div className="flex gap-2">
              <button
                onClick={() => setActiveTab('logs')}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  activeTab === 'logs'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted hover:bg-muted/80'
                }`}
              >
                Logs
              </button>
              <button
                onClick={() => setActiveTab('metrics')}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  activeTab === 'metrics'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted hover:bg-muted/80'
                }`}
              >
                Metrics
              </button>
            </div>
          </div>

          {activeTab === 'logs' ? (
            <div className="bg-slate-950 text-slate-50 rounded-lg p-4 font-mono text-sm h-96 overflow-auto">
              {logs.length === 0 ? (
                <span className="text-slate-500">No logs available...</span>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className="py-0.5">
                    {log}
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              Metrics visualization will appear here
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
