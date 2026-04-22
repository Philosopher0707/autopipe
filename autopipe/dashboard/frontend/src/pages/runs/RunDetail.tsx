import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardTitle, Badge, Button } from '@/components/ui'
import { chartsApi, runsApi } from '@/api/endpoints'
import { wsClient } from '@/api/endpoints/websocket'
import { ChartArtifactList } from '@/components/charts/ChartRenderer'
import { Clock, Terminal, BarChart3, ArrowLeft, Settings2, ChevronDown, ChevronRight } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { formatDate, formatDuration, getStatusBgColor } from '@/utils/helpers'
import type { PipelineRun, Step } from '@/types'
import { TrainingMetricsChart } from '@/components/charts/TrainingMetricsChart'

export function RunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'logs' | 'metrics' | 'checkpoints'>('logs')
  const [logs, setLogs] = useState<string[]>([])
  const [configOpen, setConfigOpen] = useState(false)
  const wsConnectedRef = useRef(false)
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
    enabled: !!runId && activeTab === 'logs' && !wsConnectedRef.current,
    refetchInterval: run?.status === 'running' && !wsConnectedRef.current ? 3000 : false,
  })

  const steps = stepsData?.items || []
  const apiLogs = logsData?.logs || []

  const { data: stepDurations } = useQuery({
    queryKey: ['charts', 'step-durations', runId],
    queryFn: () => chartsApi.getStepDurations(runId!),
    enabled: !!runId,
  })

  const { data: chartArtifactsData } = useQuery({
    queryKey: ['charts', 'artifacts', 'run', runId],
    queryFn: () => chartsApi.listArtifacts({ run_id: runId!, page_size: 50 }),
    enabled: !!runId,
  })

  const { data: trainingConfig } = useQuery({
    queryKey: ['runs', runId, 'config'],
    queryFn: () => runsApi.getConfig(runId!),
    enabled: !!runId,
  })

  const { data: checkpointsData } = useQuery({
    queryKey: ['runs', runId, 'checkpoints'],
    queryFn: () => runsApi.getCheckpoints(runId!),
    enabled: !!runId && activeTab === 'checkpoints',
  })

  useEffect(() => {
    if (!wsConnectedRef.current) {
      setLogs(
        apiLogs.map((entry) => `[${entry.level}] ${entry.step ? `(${entry.step}) ` : ''}${entry.message}`)
      )
    }
  }, [apiLogs])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    if (!runId) return

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws/runs/${runId}`

    wsClient.connect(wsUrl)

    const unsubStatus = wsClient.subscribe('run.status', () => {
      queryClient.invalidateQueries({ queryKey: ['runs', runId] })
      queryClient.invalidateQueries({ queryKey: ['runs', runId, 'steps'] })
    })

    const unsubLog = wsClient.subscribe('run.log', (msg) => {
      const level = (msg.data.level as string) || 'INFO'
      const step = msg.data.step_id ? `(${msg.data.step_id}) ` : ''
      const text = (msg.data.message as string) || ''
      setLogs((prev) => [...prev, `[${level}] ${step}${text}`])
    })

    const unsubMetric = wsClient.subscribe('run.metric', () => {
      queryClient.invalidateQueries({ queryKey: ['runs', runId] })
    })

    wsConnectedRef.current = true

    return () => {
      unsubStatus()
      unsubLog()
      unsubMetric()
      wsClient.disconnect()
      wsConnectedRef.current = false
    }
  }, [runId])

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

      {trainingConfig && (
        <Card>
          <CardContent className="p-6">
            <button
              className="flex items-center gap-2 w-full text-left"
              onClick={() => setConfigOpen(!configOpen)}
            >
              <Settings2 className="w-4 h-4 text-muted-foreground" />
              <CardTitle className="text-lg">Training Config</CardTitle>
              {configOpen ? (
                <ChevronDown className="w-4 h-4 ml-auto text-muted-foreground" />
              ) : (
                <ChevronRight className="w-4 h-4 ml-auto text-muted-foreground" />
              )}
            </button>
            {configOpen && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">
                {[
                  { label: 'Architecture', value: trainingConfig.architecture },
                  { label: 'Optimizer', value: trainingConfig.optimizer },
                  { label: 'Learning Rate', value: trainingConfig.learning_rate?.toString() },
                  { label: 'Weight Decay', value: trainingConfig.weight_decay?.toString() },
                  { label: 'Batch Size', value: trainingConfig.batch_size?.toString() },
                  { label: 'Epochs', value: trainingConfig.epochs?.toString() },
                  { label: 'AMP', value: trainingConfig.amp != null ? (trainingConfig.amp ? 'Yes' : 'No') : undefined },
                  { label: 'Gradient Clip', value: trainingConfig.gradient_clip?.toString() },
                ]
                  .filter((r) => r.value != null)
                  .map((r) => (
                    <div key={r.label} className="bg-muted/50 rounded-lg p-3">
                      <p className="text-xs text-muted-foreground">{r.label}</p>
                      <p className="text-sm font-mono font-medium">{r.value}</p>
                    </div>
                  ))}
                {trainingConfig.early_stopping && (
                  <div className="bg-muted/50 rounded-lg p-3 col-span-2 md:col-span-3">
                    <p className="text-xs text-muted-foreground mb-1">Early Stopping</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(trainingConfig.early_stopping).map(([k, v]) => (
                        <span key={k} className="text-xs font-mono bg-background px-2 py-0.5 rounded">
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {trainingConfig.lr_scheduler && (
                  <div className="bg-muted/50 rounded-lg p-3 col-span-2 md:col-span-3">
                    <p className="text-xs text-muted-foreground mb-1">LR Scheduler</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(trainingConfig.lr_scheduler).map(([k, v]) => (
                        <span key={k} className="text-xs font-mono bg-background px-2 py-0.5 rounded">
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {stepDurations && stepDurations.steps.length > 0 && (
        <Card>
          <CardContent className="p-6">
            <CardTitle className="text-lg mb-4">Step Durations</CardTitle>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stepDurations.steps} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" fontSize={12} />
                  <YAxis dataKey="name" type="category" width={120} fontSize={12} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                    formatter={(v: number) => [`${v.toFixed(1)}s`, 'Duration']}
                  />
                  <Bar dataKey="duration_seconds" fill="#3b82f6" name="Duration (s)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {runId && (
        <TrainingMetricsChart runId={runId} />
      )}

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
              <button
                onClick={() => setActiveTab('checkpoints')}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  activeTab === 'checkpoints'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted hover:bg-muted/80'
                }`}
              >
                Checkpoints
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
          ) : activeTab === 'checkpoints' ? (
            <div className="overflow-x-auto">
              {checkpointsData && checkpointsData.checkpoints.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-2 pr-4">Epoch</th>
                      <th className="pb-2 pr-4">Val Loss</th>
                      <th className="pb-2 pr-4">Val Accuracy</th>
                      <th className="pb-2 pr-4">Path</th>
                      <th className="pb-2 pr-4">Best</th>
                      <th className="pb-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {checkpointsData.checkpoints.map((cp) => (
                      <tr key={cp.id} className="border-b hover:bg-muted/50">
                        <td className="py-2 pr-4 font-mono">{cp.epoch}</td>
                        <td className="py-2 pr-4 font-mono">{cp.val_loss.toFixed(4)}</td>
                        <td className="py-2 pr-4 font-mono">{cp.val_accuracy.toFixed(4)}</td>
                        <td className="py-2 pr-4 text-xs text-muted-foreground truncate max-w-[200px]">{cp.file_path}</td>
                        <td className="py-2 pr-4">{cp.is_best ? '⭐' : ''}</td>
                        <td className="py-2">
                          <a href={cp.file_path} className="text-xs text-primary hover:underline">Download</a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-muted-foreground text-center py-4">No checkpoints</p>
              )}
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

      {chartArtifactsData && chartArtifactsData.items.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Generated Charts</h2>
          <ChartArtifactList artifacts={chartArtifactsData.items} />
        </div>
      )}
    </div>
  )
}
