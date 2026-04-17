import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardTitle, Badge, Button } from '@/components/ui'
import { runsApi } from '@/api/endpoints'
import { Clock, Terminal, BarChart3, ArrowLeft } from 'lucide-react'
import { formatDate, formatDuration, getStatusBgColor } from '@/utils/helpers'
import type { PipelineRun, Step } from '@/types'

export function RunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'logs' | 'metrics'>('logs')
  const [logs, setLogs] = useState<string[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)

  const { data: run, isLoading } = useQuery<PipelineRun>({
    queryKey: ['runs', runId],
    queryFn: () => runsApi.getById(runId!),
    enabled: !!runId,
  })

  const { data: stepsData } = useQuery({
    queryKey: ['runs', runId, 'steps'],
    queryFn: () => runsApi.getSteps(runId!),
    enabled: !!runId,
  })

  const { data: logsData } = useQuery({
    queryKey: ['runs', runId, 'logs'],
    queryFn: () => runsApi.getLogs(runId!),
    enabled: !!runId && activeTab === 'logs',
    refetchInterval: run?.status === 'running' ? 3000 : false,
  })

  const steps = stepsData?.items || []
  const apiLogs = logsData?.logs || []

  useEffect(() => {
    setLogs(
      apiLogs.map((entry) => `[${entry.level}] ${entry.step ? `(${entry.step}) ` : ''}${entry.message}`)
    )
  }, [apiLogs])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-muted rounded w-1/3" />
        <div className="h-32 bg-muted rounded" />
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
      <div className="flex items-start justify-between">
        <div>
          <Button variant="ghost" size="sm" onClick={() => navigate('/runs')}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
          <div className="mt-3 flex items-center gap-3">
            <h1 className="text-3xl font-bold text-foreground">
              Run #{run.run_number ?? runId?.slice(0, 8)}
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
              <span className="text-xs">Created</span>
            </div>
            <p className="text-lg font-semibold mt-1">
              {run.created_at ? formatDate(run.created_at) : '--'}
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
      </div>

      <Card>
        <CardContent className="p-6">
          <CardTitle className="text-lg mb-4">Steps</CardTitle>
          <div className="space-y-2">
            {steps.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No steps recorded</p>
            ) : steps.map((step: Step) => (
              <div
                key={step.id}
                className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    step.status === 'success' ? 'bg-green-500' :
                    step.status === 'failed' ? 'bg-red-500' :
                    step.status === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-amber-500'
                  }`}
                  />
                  <span className="font-medium">{step.name}</span>
                  <span className="text-xs text-muted-foreground">{step.step_type}</span>
                </div>
                <span className="text-sm text-muted-foreground">
                  {step.duration_seconds ? formatDuration(step.duration_seconds) : '--'}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <CardTitle className="text-lg">Execution Details</CardTitle>
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
            <div className="p-8">
              {run.metrics && Object.keys(run.metrics).length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(run.metrics).map(([key, value]) => (
                    <div key={key} className="text-center p-4 bg-muted/50 rounded-lg">
                      <div className="flex justify-center mb-2">
                        <BarChart3 className="w-4 h-4 text-muted-foreground" />
                      </div>
                      <p className="text-2xl font-bold text-primary">
                        {typeof value === 'number' ? value.toFixed(4) : String(value)}
                      </p>
                      <p className="text-xs text-muted-foreground uppercase mt-1">{key}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-center">No metrics recorded</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
