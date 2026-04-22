import { useState, useMemo, type FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2, Rocket } from 'lucide-react'
import { Card, CardContent, CardHeader, Badge, Button, Skeleton } from '@/components/ui'
import { chartsApi, experimentsApi, pipelinesApi } from '@/api/endpoints'
import { ChartArtifactList } from '@/components/charts/ChartRenderer'
import { cn, formatDate, formatDuration, getStatusBgColor } from '@/utils/helpers'
import type { PipelineRun } from '@/types'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'

type ExperimentFormState = {
  name: string
  description: string
  tags: string
  configText: string
}

const DEFAULT_FORM: ExperimentFormState = {
  name: '',
  description: '',
  tags: '',
  configText: '{\n  "strategy": "bayesian"\n}',
}

function parseTags(tags: string): string[] | undefined {
  const items = tags.split(',').map((tag) => tag.trim()).filter(Boolean)
  return items.length > 0 ? items : undefined
}

function parseJsonConfig(configText: string): Record<string, unknown> | undefined {
  const trimmed = configText.trim()
  if (!trimmed) return undefined
  return JSON.parse(trimmed) as Record<string, unknown>
}

export function ExperimentDetail() {
  const { experimentId } = useParams<{ experimentId: string }>()
  const navigate = useNavigate()
  const isNew = !experimentId
  const [activeTab, setActiveTab] = useState<'overview' | 'runs' | 'compare' | 'artifacts'>('overview')
  const [form, setForm] = useState<ExperimentFormState>(DEFAULT_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [showTrials, setShowTrials] = useState(false)
  const [trialPipeline, setTrialPipeline] = useState('')
  const [trialStrategy, setTrialStrategy] = useState<'random' | 'grid'>('random')
  const [trialCount, setTrialCount] = useState(5)
  const [trialError, setTrialError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: experiment, isLoading } = useQuery({
    queryKey: ['experiment', experimentId],
    queryFn: () => experimentsApi.getById(experimentId!),
    enabled: !!experimentId,
  })

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['experiment', experimentId, 'runs'],
    queryFn: () => experimentsApi.listRuns(experimentId!),
    enabled: !!experimentId,
  })

  const createMutation = useMutation({
    mutationFn: () => experimentsApi.create({
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      tags: parseTags(form.tags),
      config: parseJsonConfig(form.configText),
    }),
    onSuccess: (createdExperiment) => navigate(`/experiments/${createdExperiment.id}`),
  })

  const runs = runsData?.items ?? []
  const metricName = experiment?.metric_name
    || Object.keys(runs.find((run) => run.metrics && Object.keys(run.metrics).length > 0)?.metrics || {})[0]
    || 'score'

  const { data: traceData } = useQuery({
    queryKey: ['charts', 'experiment-metric-trace', experimentId],
    queryFn: () => chartsApi.getExperimentMetricTrace({ experiment_id: experimentId! }),
    enabled: !!experimentId,
  })

  const chartData = traceData?.points ?? []
  const chartMetrics = traceData?.metrics ?? (metricName ? [metricName] : [])

  const { data: chartArtifactsData } = useQuery({
    queryKey: ['charts', 'artifacts', 'experiment', experimentId],
    queryFn: () => chartsApi.listArtifacts({ experiment_id: experimentId!, page_size: 50 }),
    enabled: !!experimentId,
  })

  const { data: artifactsData } = useQuery({
    queryKey: ['experiments', experimentId, 'artifacts'],
    queryFn: () => experimentsApi.getArtifacts(experimentId!),
    enabled: !!experimentId && activeTab === 'artifacts',
  })

  const { data: pipelinesData } = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => pipelinesApi.list(),
    enabled: showTrials,
  })

  const launchTrialsMutation = useMutation({
    mutationFn: () => experimentsApi.launchTrials(experimentId!, {
      pipeline_id: trialPipeline,
      strategy: trialStrategy,
      n_trials: trialCount,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiment', experimentId] })
      queryClient.invalidateQueries({ queryKey: ['experiment', experimentId, 'runs'] })
      queryClient.invalidateQueries({ queryKey: ['charts', 'experiment-metric-trace', experimentId] })
      setShowTrials(false)
    },
    onError: (err: Error) => setTrialError(err.message),
  })

  const compareMutation = useMutation({
    mutationFn: () => experimentsApi.compare(experimentId!, metricName),
  })

  const bestRun = useMemo(() =>
    runs.find((run) => run.id === experiment?.best_run_id)
    || [...runs]
      .filter((run) => typeof run.metrics?.[metricName] === 'number')
      .sort((left, right) => Number(right.metrics?.[metricName] ?? 0) - Number(left.metrics?.[metricName] ?? 0))[0]
  , [runs, experiment?.best_run_id, metricName])

  const { completedRuns, failedRuns, runningRuns } = useMemo(() =>
    runs.reduce((acc, run) => {
      if (run.status === 'success') acc.completedRuns++
      else if (run.status === 'failed') acc.failedRuns++
      else if (run.status === 'running' || run.status === 'pending') acc.runningRuns++
      return acc
    }, { completedRuns: 0, failedRuns: 0, runningRuns: 0 })
  , [runs])

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError(null)

    if (!form.name.trim()) {
      setFormError('Experiment name is required.')
      return
    }

    try {
      await createMutation.mutateAsync()
    } catch (error) {
      if (error instanceof SyntaxError) {
        setFormError('Configuration must be valid JSON.')
        return
      }
      setFormError('Unable to create experiment.')
    }
  }

  if (isNew) {
    return (
      <div className="space-y-6 max-w-3xl">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/experiments')}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold">New Experiment</h1>
            <p className="text-muted-foreground">Create an experiment record before attaching runs.</p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Experiment Setup</h2>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleCreate}>
              <div>
                <label className="text-sm font-medium">Name</label>
                <input
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  placeholder="xgboost-hyperparameter-search"
                />
              </div>

              <div>
                <label className="text-sm font-medium">Description</label>
                <textarea
                  value={form.description}
                  onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                  className="mt-1 min-h-24 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  placeholder="What hypothesis or search strategy does this experiment cover?"
                />
              </div>

              <div>
                <label className="text-sm font-medium">Tags</label>
                <input
                  value={form.tags}
                  onChange={(event) => setForm((current) => ({ ...current, tags: event.target.value }))}
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  placeholder="bayesian, xgboost, tuning"
                />
              </div>

              <div>
                <label className="text-sm font-medium">Config JSON</label>
                <textarea
                  value={form.configText}
                  onChange={(event) => setForm((current) => ({ ...current, configText: event.target.value }))}
                  className="mt-1 min-h-56 w-full rounded-lg border border-input bg-background px-3 py-2 font-mono text-sm"
                  spellCheck={false}
                />
              </div>

              {formError && <p className="text-sm text-destructive">{formError}</p>}

              <div className="flex justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => navigate('/experiments')}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  Create Experiment
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoading || runsLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-32" />
        <Skeleton className="h-96" />
      </div>
    )
  }

  if (!experiment) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Experiment not found</p>
        <Button variant="ghost" onClick={() => navigate('/experiments')} className="mt-4">
          Back to Experiments
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{experiment.name}</h1>
            <Badge className={getStatusBgColor(experiment.status)}>
              {experiment.status}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">{experiment.description}</p>
        </div>
        <Button onClick={() => setShowTrials(true)} className="shrink-0">
          <Rocket className="w-4 h-4 mr-2" />
          Launch Trials
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-primary">{runs.length}</p>
            <p className="text-xs text-muted-foreground">Total Runs</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-green-600">{completedRuns}</p>
            <p className="text-xs text-muted-foreground">Completed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-purple-600">
              {bestRun && typeof bestRun.metrics?.[metricName] === 'number'
                ? Number(bestRun.metrics?.[metricName]).toFixed(4)
                : experiment.best_metric?.toFixed(4) ?? '--'}
            </p>
            <p className="text-xs text-muted-foreground">Best {metricName}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-amber-600">{runningRuns}</p>
            <p className="text-xs text-muted-foreground">Active</p>
          </CardContent>
        </Card>
      </div>

      <div className="border-b">
        <div className="flex gap-1">
          {(['overview', 'runs', 'compare', 'artifacts'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize',
                activeTab === tab ? 'border-primary text-primary' : 'border-transparent text-muted-foreground'
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'overview' && (
        <Card>
          <CardContent className="p-6">
            {chartData.length > 0 ? (
              <>
                <h3 className="font-semibold mb-4">Run Performance ({chartMetrics.join(', ')})</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="run_number" fontSize={12} label={{ value: 'Run #', position: 'insideBottomRight', offset: -5 }} />
                      <YAxis fontSize={12} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                        formatter={(v: number) => [v.toFixed(4)]}
                      />
                      {chartMetrics.map((m, i) => (
                        <Line
                          key={m}
                          type="monotone"
                          dataKey={m}
                          stroke={['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'][i % 5]}
                          strokeWidth={2}
                          dot={{ r: 3 }}
                          name={m}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </>
            ) : (
              <div className="py-10 text-center text-sm text-muted-foreground">
                No numeric run metrics are available for charting yet.
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 'runs' && (
        <Card>
          <CardContent className="p-0">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Run</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Status</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">{metricName}</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Started</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Duration</th>
                </tr>
              </thead>
              <tbody>
                {runs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-muted-foreground">
                      No runs attached to this experiment.
                    </td>
                  </tr>
                ) : (
                  runs.map((run: PipelineRun) => (
                    <tr key={run.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="py-3 px-4 font-mono text-sm">#{run.run_number ?? run.id.slice(0, 8)}</td>
                      <td className="py-3 px-4">
                        <Badge className={getStatusBgColor(run.status)}>
                          {run.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 font-mono text-sm">
                        {typeof run.metrics?.[metricName] === 'number'
                          ? Number(run.metrics?.[metricName]).toFixed(4)
                          : '--'}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {run.started_at ? formatDate(run.started_at) : '--'}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {run.duration_seconds ? formatDuration(run.duration_seconds) : '--'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {activeTab === 'compare' && (
        <Card>
          <CardContent className="p-6">
            {completedRuns < 2 ? (
              <p className="text-center text-sm text-muted-foreground py-8">
                Need at least 2 completed runs to compare.
              </p>
            ) : (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold">Run Comparison ({metricName})</h3>
                  <Button
                    size="sm"
                    disabled={compareMutation.isPending}
                    onClick={() => compareMutation.mutate()}
                  >
                    {compareMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                    Compare
                  </Button>
                </div>

                {compareMutation.data && (
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground uppercase">Run ID</th>
                        <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground uppercase">{metricName}</th>
                        <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground uppercase">Started</th>
                        <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground uppercase">Params</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compareMutation.data.runs.map((cr) => (
                        <tr key={cr.id} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="py-2 px-3 font-mono text-sm">{cr.id.slice(0, 8)}</td>
                          <td className="py-2 px-3 font-mono text-sm">
                            {cr.metric_value != null ? cr.metric_value.toFixed(4) : '--'}
                          </td>
                          <td className="py-2 px-3 text-sm text-muted-foreground">
                            {cr.started_at ? formatDate(cr.started_at) : '--'}
                          </td>
                          <td className="py-2 px-3 text-sm text-muted-foreground">
                            {cr.params ? JSON.stringify(cr.params).slice(0, 60) : '--'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 'artifacts' && (
        <div>
          {artifactsData && artifactsData.artifacts.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {artifactsData.artifacts.map((art) => (
                <Card key={art.id}>
                  <CardContent className="p-4">
                    {art.artifact_type === 'image' || art.artifact_type === 'figure' ? (
                      <div className="aspect-video bg-muted rounded-md flex items-center justify-center mb-3 overflow-hidden">
                        <img
                          src={art.file_path}
                          alt={art.title}
                          className="max-w-full max-h-full object-contain"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none'
                            const parent = (e.target as HTMLImageElement).parentElement
                            if (parent) parent.innerHTML = `<span class="text-xs text-muted-foreground">${art.artifact_type.toUpperCase()}</span>`
                          }}
                        />
                      </div>
                    ) : (
                      <div className="aspect-video bg-muted rounded-md flex items-center justify-center mb-3">
                        <span className="text-xs font-mono text-muted-foreground">
                          {art.artifact_type.toUpperCase()}
                        </span>
                      </div>
                    )}
                    <div className="space-y-1">
                      <p className="text-sm font-medium truncate">{art.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {art.artifact_type} · {(art.file_size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <a
                      href={art.file_path}
                      className="mt-2 inline-block text-xs text-primary hover:underline"
                    >
                      Download
                    </a>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <p className="text-center text-sm text-muted-foreground py-8">No artifacts</p>
          )}
        </div>
      )}

      {failedRuns > 0 && (
        <p className="text-sm text-muted-foreground">
          {failedRuns} failed {failedRuns === 1 ? 'run was' : 'runs were'} recorded for this experiment.
        </p>
      )}

      {chartArtifactsData && chartArtifactsData.items.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Generated Charts</h2>
          <ChartArtifactList artifacts={chartArtifactsData.items} />
        </div>
      )}

      {showTrials && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowTrials(false)}>
          <div className="bg-background rounded-lg shadow-lg p-6 w-full max-w-md space-y-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold">Launch Trials</h2>
            <p className="text-sm text-muted-foreground">
              Generate trial runs for this experiment using its search-space config.
            </p>

            <div>
              <label className="text-sm font-medium">Pipeline</label>
              <select
                value={trialPipeline}
                onChange={(e) => setTrialPipeline(e.target.value)}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">Select a pipeline...</option>
                {pipelinesData?.items?.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium">Strategy</label>
              <div className="mt-1 flex gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    checked={trialStrategy === 'random'}
                    onChange={() => setTrialStrategy('random')}
                  />
                  Random
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    checked={trialStrategy === 'grid'}
                    onChange={() => setTrialStrategy('grid')}
                  />
                  Grid
                </label>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">Number of trials</label>
              <input
                type="number"
                min={1}
                max={100}
                value={trialCount}
                onChange={(e) => setTrialCount(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              />
            </div>

            {experiment?.config?.search_space && typeof experiment.config.search_space === 'object' ? (
              <div>
                <label className="text-sm font-medium">Search space</label>
                <pre className="mt-1 text-xs bg-muted p-3 rounded-lg overflow-auto max-h-40">
                  {JSON.stringify(experiment.config.search_space as Record<string, unknown>, null, 2)}
                </pre>
              </div>
            ) : null}

            {trialError && <p className="text-sm text-destructive">{trialError}</p>}

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setShowTrials(false)}>Cancel</Button>
              <Button
                onClick={() => launchTrialsMutation.mutate()}
                disabled={!trialPipeline || launchTrialsMutation.isPending}
              >
                {launchTrialsMutation.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Launch
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
