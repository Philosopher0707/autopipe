import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  GitBranch,
  GitCompare,
  Layers,
  Settings2,
  Trophy,
  X,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, Button, Badge, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui'
import { runsApi, type MultiRunCompareResponse } from '@/api/endpoints/runs'
import { formatDistanceToNow } from '@/utils/helpers'

function formatDuration(seconds: number | null): string {
  if (!seconds) return 'N/A'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1000) return value.toFixed(0)
    if (Math.abs(value) >= 1) return value.toFixed(2)
    return value.toFixed(4)
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

function formatDelta(delta: number | null): { text: string; color: string; icon: React.ReactNode } {
  if (delta === null || delta === undefined) return { text: '-', color: 'text-muted-foreground', icon: null }
  if (!isFinite(delta)) return { text: delta > 0 ? '+∞%' : '-∞%', color: delta > 0 ? 'text-green-600' : 'text-red-600', icon: null }
  const sign = delta > 0 ? '+' : ''
  return {
    text: `${sign}${delta.toFixed(1)}%`,
    color: delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-600' : 'text-muted-foreground',
    icon: delta > 0 ? <ArrowUp className="w-3 h-3 inline" /> : delta < 0 ? <ArrowDown className="w-3 h-3 inline" /> : null
  }
}

function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; className: string }> = {
    success: { variant: 'default', className: 'bg-green-500 hover:bg-green-600 text-white' },
    failed: { variant: 'destructive', className: '' },
    running: { variant: 'default', className: 'bg-blue-500 hover:bg-blue-600 text-white' },
    pending: { variant: 'secondary', className: '' },
    cancelled: { variant: 'outline', className: '' },
  }
  const variant = variants[status] || { variant: 'secondary', className: '' }
  return (
    <Badge variant={variant.variant} className={variant.className}>
      {status}
    </Badge>
  )
}

interface ConfusionMatrixProps {
  data: number[][]
  labels?: string[]
}

function ConfusionMatrix({ data, labels }: ConfusionMatrixProps) {
  const maxVal = Math.max(...data.flat(), 1)
  const size = data.length
  const rowLabels = labels || Array.from({ length: size }, (_, i) => `Class ${i}`)
  const colLabels = labels || Array.from({ length: size }, (_, i) => `Class ${i}`)

  return (
    <div className="overflow-auto">
      <div className="inline-block">
        <div className="flex">
          <div className="w-24" />
          {colLabels.map((label, i) => (
            <div key={i} className="w-20 text-center text-xs text-muted-foreground py-1">
              {label}
            </div>
          ))}
        </div>
        {data.map((row, ri) => (
          <div key={ri} className="flex">
            <div className="w-24 flex items-center justify-end pr-2 text-xs text-muted-foreground">
              {rowLabels[ri]}
            </div>
            {row.map((val, ci) => {
              const intensity = val / maxVal
              return (
                <div
                  key={ci}
                  className="w-20 h-12 flex items-center justify-center text-sm font-medium"
                  style={{
                    backgroundColor: `rgba(59, 130, 246, ${0.1 + intensity * 0.7})`,
                    color: intensity > 0.5 ? 'white' : 'inherit'
                  }}
                >
                  {val.toFixed(1)}%
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

export function RunCompare() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [expandedParams, setExpandedParams] = useState(false)
  const [selectedRuns, setSelectedRuns] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState('parameters')

  const runIds = searchParams.get('ids')?.split(',').filter(Boolean) || []

  const { data, isLoading, error } = useQuery<MultiRunCompareResponse>({
    queryKey: ['runs', 'compare', runIds.join(',')],
    queryFn: () => runsApi.compareMultiple(runIds),
    enabled: runIds.length >= 2,
  })

  // Fetch logs for runs
  const { data: logsData } = useQuery({
    queryKey: ['runs', 'logs', runIds.join(',')],
    queryFn: async () => {
      const logs = await Promise.all(
        runIds.map(id => runsApi.getLogs(id, { tail: 50 }).catch(() => ({ logs: [] })))
      )
      return runIds.reduce((acc, id, i) => {
        acc[id] = logs[i]?.logs || []
        return acc
      }, {} as Record<string, any[]>)
    },
    enabled: runIds.length >= 2 && activeTab === 'logs',
  })

  useEffect(() => {
    if (data?.runs && selectedRuns.length === 0) {
      setSelectedRuns(data.runs.map(r => r.id))
    }
  }, [data, selectedRuns.length])

  const handleRemoveRun = (runId: string) => {
    const newIds = runIds.filter(id => id !== runId)
    if (newIds.length < 2) {
      navigate('/runs')
    } else {
      setSearchParams({ ids: newIds.join(',') })
    }
  }

  const handleAddRun = () => navigate('/runs')

  if (runIds.length < 2) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="py-12">
            <div className="text-center">
              <GitCompare className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <h2 className="text-lg font-semibold mb-2">Select Runs to Compare</h2>
              <p className="text-muted-foreground mb-4">Select at least 2 runs from the runs list to compare them.</p>
              <Button onClick={handleAddRun}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                Go to Run List
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center gap-2 mb-6">
          <Skeleton className="h-9 w-32" />
          <Skeleton className="h-9 w-48" />
        </div>
        <div className="grid gap-4">
          {runIds.map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="py-12">
            <div className="text-center">
              <X className="w-12 h-12 mx-auto mb-4 text-destructive" />
              <h2 className="text-lg font-semibold mb-2">Failed to Load Comparison</h2>
              <p className="text-muted-foreground mb-4">{(error as Error)?.message || 'Unknown error'}</p>
              <Button onClick={() => window.location.reload()}>Retry</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const { runs, parameters, metrics, diff_summary } = data
  const visibleRuns = runs.filter(r => selectedRuns.includes(r.id))

  // Check for confusion matrices in run metrics
  const hasConfusionMatrices = visibleRuns.some(r => 
    r.metrics && ('confusion_matrix' in r.metrics || 'cm' in r.metrics)
  )

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link to="/runs">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Runs
              </Button>
            </Link>
            <span className="text-muted-foreground">/</span>
            <h1 className="text-xl font-semibold">Compare Runs</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            {visibleRuns.length} runs selected • {diff_summary.total_params} parameters • {diff_summary.total_metrics} metrics
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleAddRun}>
            <GitBranch className="w-4 h-4 mr-2" />
            Add Run
          </Button>
        </div>
      </div>

      {/* Run Headers */}
      <div className="grid gap-4" style={{ gridTemplateColumns: `200px repeat(${visibleRuns.length}, minmax(180px, 1fr))` }}>
        <div className="font-medium text-muted-foreground p-2">Run</div>
        {visibleRuns.map((run) => (
          <Card key={run.id} className="relative">
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-1 right-1 h-6 w-6 p-0"
              onClick={() => handleRemoveRun(run.id)}
            >
              <X className="w-3 h-3" />
            </Button>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium truncate pr-6">
                {run.pipeline_name || run.pipeline_id}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="flex items-center gap-2 mb-1">
                <StatusBadge status={run.status} />
                <span className="text-xs text-muted-foreground">Run {run.run_number}</span>
              </div>
              <div className="text-xs text-muted-foreground">
                {formatDuration(run.duration_seconds || null)} • {formatDistanceToNow(run.created_at)}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="parameters" className="flex items-center gap-1">
            <Settings2 className="w-4 h-4" />
            Parameters
            <span className="ml-1 text-xs text-muted-foreground">({diff_summary.different_params} diff)</span>
          </TabsTrigger>
          <TabsTrigger value="metrics" className="flex items-center gap-1">
            <Trophy className="w-4 h-4" />
            Metrics
            <span className="ml-1 text-xs text-muted-foreground">({metrics.length})</span>
          </TabsTrigger>
          {hasConfusionMatrices && (
            <TabsTrigger value="confusion" className="flex items-center gap-1">
              <Layers className="w-4 h-4" />
              Confusion Matrix
            </TabsTrigger>
          )}
          <TabsTrigger value="artifacts" className="flex items-center gap-1">
            <FileText className="w-4 h-4" />
            Artifacts
          </TabsTrigger>
          <TabsTrigger value="logs" className="flex items-center gap-1">
            <Clock className="w-4 h-4" />
            Logs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="parameters" className="mt-4">
          {parameters.length > 0 ? (
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-muted-foreground">
                  {diff_summary.different_params} of {diff_summary.total_params} parameters differ across runs
                </span>
                <Button variant="ghost" size="sm" onClick={() => setExpandedParams(!expandedParams)}>
                  {expandedParams ? (
                    <><ChevronUp className="w-4 h-4 mr-1" />Show only different</>
                  ) : (
                    <><ChevronDown className="w-4 h-4 mr-1" />Show all parameters</>
                  )}
                </Button>
              </div>
              <div className="overflow-x-auto border rounded-lg">
                <table className="w-full">
                  <tbody>
                    {(expandedParams ? parameters : parameters.filter(p => p.is_different)).map((param) => (
                      <tr key={param.name} className={`border-b last:border-0 ${param.is_different ? 'bg-amber-50/50' : ''}`}>
                        <td className="p-3 w-[200px] font-medium sticky left-0 bg-background border-r">{param.name}</td>
                        {visibleRuns.map((run) => (
                          <td key={run.id} className="p-3 min-w-[180px] font-mono text-sm border-r last:border-r-0">
                            {formatValue(param.values[run.id])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <Settings2 className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-muted-foreground">No parameters available for comparison</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="metrics" className="mt-4">
          {metrics.length > 0 ? (
            <div className="overflow-x-auto border rounded-lg">
              <table className="w-full">
                <tbody>
                  {metrics.map((metric) => {
                    const isHighlighted = diff_summary.best_metric_per_key[metric.name] && 
                      selectedRuns.includes(diff_summary.best_metric_per_key[metric.name])
                    return (
                      <tr key={metric.name} className="border-b last:border-0">
                        <td className="p-3 w-[200px] font-medium sticky left-0 bg-background border-r">
                          <div className="flex items-center gap-2">
                            {metric.name}
                            {isHighlighted && <Trophy className="w-4 h-4 text-amber-500" />}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {metric.higher_is_better ? 'higher is better' : 'lower is better'}
                          </div>
                        </td>
                        {visibleRuns.map((run) => {
                          const value = metric.values[run.id]
                          const isBest = metric.best_run_id === run.id
                          const delta = formatDelta(value?.delta_from_baseline || null)
                          return (
                            <td key={run.id} className="p-3 min-w-[180px] border-r last:border-r-0">
                              <div className="flex items-baseline gap-2">
                                <span className={`text-xl font-semibold ${isBest ? 'text-green-600' : ''}`}>
                                  {formatValue(value?.value)}
                                </span>
                                {run.id !== runs[0]?.id && value?.delta_from_baseline !== null && (
                                  <span className={`text-sm ${delta.color}`}>
                                    {delta.icon}
                                    {delta.text}
                                  </span>
                                )}
                              </div>
                            </td>
                          )
                        })}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <Trophy className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-muted-foreground">No metrics available for comparison</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {hasConfusionMatrices && (
          <TabsContent value="confusion" className="mt-4">
            <div className="grid gap-6">
              {visibleRuns.map((run) => {
                const cm = run.metrics?.confusion_matrix as number[][] || run.metrics?.cm as number[][]
                const labels = run.metrics?.labels as string[] || undefined
                if (!cm) return null
                return (
                  <Card key={run.id}>
                    <CardHeader>
                      <CardTitle className="text-sm">
                        {run.pipeline_name || run.pipeline_id} - Run {run.run_number}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ConfusionMatrix data={cm} labels={labels} />
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          </TabsContent>
        )}

        <TabsContent value="artifacts" className="mt-4">
          <Card>
            <CardContent className="py-12 text-center">
              <FileText className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground">Artifacts comparison coming soon</p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="logs" className="mt-4">
          <div className="grid gap-4">
            {visibleRuns.map((run) => (
              <Card key={run.id}>
                <CardHeader>
                  <CardTitle className="text-sm">
                    {run.pipeline_name || run.pipeline_id} - Logs
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="bg-muted p-4 rounded-lg font-mono text-xs overflow-auto max-h-96">
                    {logsData && logsData[run.id]?.length >= 0 ? (
                      logsData?.[run.id]?.map((log, i) => (
                        <div key={i} className="py-0.5">
                          <span className="text-muted-foreground">[{log.timestamp?.slice(11, 19) || '---'}]</span>{' '}
                          <span className={log.level === 'ERROR' ? 'text-red-500' : log.level === 'WARN' ? 'text-amber-500' : ''}>
                            {log.message}
                          </span>
                        </div>
                      ))
                    ) : (
                      <span className="text-muted-foreground">No logs available...</span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}