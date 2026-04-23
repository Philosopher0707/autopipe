import { useEffect, useRef, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardTitle,
  Button,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  StatusPill,
  ChartCard,
} from '@/components/ui'
import { chartsApi, runsApi } from '@/api/endpoints'
import { wsClient } from '@/api/endpoints/websocket'
import { ChartArtifactList } from '@/components/charts/ChartRenderer'
import { SyncCrosshairProvider } from '@/components/SyncCrosshairProvider'
import { QueryBar } from '@/components/QueryBar'
import { DataTable } from '@/components/DataTable'
import {
  Clock,
  Terminal,
  BarChart3,
  ArrowLeft,
  Settings2,
  ChevronDown,
  ChevronRight,
  FileText,
  SearchX,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { formatDate, formatDuration } from '@/utils/helpers'
import type { PipelineRun, Step } from '@/types'
import { TrainingMetricsChart } from '@/components/charts/TrainingMetricsChart'

export function RunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'charts' | 'overview' | 'logs' | 'files' | 'artifacts'>('charts')
  const [logs, setLogs] = useState<string[]>([])
  const [configOpen, setConfigOpen] = useState(false)
  const wsConnectedRef = useRef(false)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const [filters, setFilters] = useState<{ key: string; value: string }[]>([])

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

  const filteredSteps = useMemo(() => {
    let result = [...steps]
    const nameFilter = filters.find((f) => f.key === 'name')?.value ?? ''
    const statusFilter = filters.find((f) => f.key === 'status')?.value ?? ''
    if (nameFilter) {
      result = result.filter((s) => s.name.toLowerCase().includes(nameFilter.toLowerCase()))
    }
    if (statusFilter) {
      result = result.filter((s) => s.status === statusFilter)
    }
    return result
  }, [steps, filters])

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
    enabled: !!runId,
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

  const paramHistogramData = useMemo(() => {
    if (!run?.metrics) return []
    return Object.entries(run.metrics).map(([key, value]) => ({
      name: key,
      value: typeof value === 'number' ? value : 0,
    }))
  }, [run?.metrics])

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

  const statusOptions = ['pending', 'running', 'success', 'failed', 'cancelled', 'skipped']

  return (
    <div className="space-y-6">
      {/* Header */}
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
            <StatusPill status={run.status} />
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

      {/* QueryBar */}
      <QueryBar
        filters={[
          { key: 'name', label: 'Filter steps...', type: 'text' },
          { key: 'status', label: 'Status', type: 'select', options: statusOptions },
        ]}
        values={filters}
        onChange={setFilters}
      />

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
        <TabsList>
          <TabsTrigger value="charts">Charts</TabsTrigger>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
          <TabsTrigger value="files">Files</TabsTrigger>
          <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
        </TabsList>

        <TabsContent value="charts" className="pt-4 space-y-6">
          <SyncCrosshairProvider>
            {runId && (
              <TrainingMetricsChart runId={runId} />
            )}
            {stepDurations && stepDurations.steps.length > 0 && (
              <ChartCard title="Step Durations">
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
              </ChartCard>
            )}
          </SyncCrosshairProvider>
        </TabsContent>

        <TabsContent value="overview" className="pt-4 space-y-6">
          {/* Stat cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Clock className="w-4 h-4" />
                  <span className="text-xs">Duration</span>
                </div>
                <p className="text-lg font-semibold mt-1 tabular-nums">
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
                <p className="text-lg font-semibold mt-1 tabular-nums">
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
                <p className="text-lg font-semibold mt-1 tabular-nums">
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
                <p className="text-lg font-semibold mt-1 tabular-nums">
                  {run.completed_at ? formatDate(run.completed_at) : '--'}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Steps table */}
          <ChartCard title="Steps">
            {filteredSteps.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <SearchX className="w-6 h-6 mb-2 opacity-50" />
                <p className="text-sm">No steps match your filters.</p>
              </div>
            ) : (
              <DataTable
                columns={[
                  {
                    key: 'name',
                    header: 'Name',
                    accessor: (s: Step) => s.name,
                  },
                  {
                    key: 'type',
                    header: 'Type',
                    accessor: (s: Step) => s.step_type,
                  },
                  {
                    key: 'status',
                    header: 'Status',
                    accessor: (s: Step) => <StatusPill status={s.status} />,
                  },
                  {
                    key: 'duration',
                    header: 'Duration',
                    accessor: (s: Step) => (s.duration_seconds ? formatDuration(s.duration_seconds) : '--'),
                    align: 'right',
                  },
                ]}
                data={filteredSteps}
              />
            )}
          </ChartCard>

          {/* Parameter histograms */}
          {paramHistogramData.length > 0 && (
            <ChartCard title="Parameters">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={paramHistogramData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" fontSize={12} />
                    <YAxis fontSize={12} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                    />
                    <Bar dataKey="value" name="Value">
                      {paramHistogramData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.value >= 0 ? '#22c55e' : '#ef4444'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          )}

          {/* Training Config */}
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

          {/* Checkpoints */}
          {checkpointsData && checkpointsData.checkpoints.length > 0 && (
            <ChartCard title="Checkpoints">
              <DataTable
                columns={[
                  { key: 'epoch', header: 'Epoch', accessor: (c) => c.epoch, align: 'right' },
                  { key: 'val_loss', header: 'Val Loss', accessor: (c) => c.val_loss.toFixed(4), align: 'right' },
                  { key: 'val_accuracy', header: 'Val Accuracy', accessor: (c) => c.val_accuracy.toFixed(4), align: 'right' },
                  { key: 'path', header: 'Path', accessor: (c) => <span className="text-xs text-muted-foreground truncate max-w-[200px] block">{c.file_path}</span> },
                  { key: 'best', header: 'Best', accessor: (c) => (c.is_best ? '⭐' : '') },
                ]}
                data={checkpointsData.checkpoints}
              />
            </ChartCard>
          )}
        </TabsContent>

        <TabsContent value="logs" className="pt-4">
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
        </TabsContent>

        <TabsContent value="files" className="pt-4">
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <FileText className="w-10 h-10 mb-3 opacity-40" />
            <p className="text-sm font-medium">No files attached</p>
            <p className="text-xs mt-1">Files associated with this run will appear here.</p>
          </div>
        </TabsContent>

        <TabsContent value="artifacts" className="pt-4">
          {chartArtifactsData && chartArtifactsData.items.length > 0 ? (
            <div className="space-y-4">
              <ChartArtifactList artifacts={chartArtifactsData.items} />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <BarChart3 className="w-10 h-10 mb-3 opacity-40" />
              <p className="text-sm font-medium">No chart artifacts</p>
              <p className="text-xs mt-1">Generated charts will appear here.</p>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
