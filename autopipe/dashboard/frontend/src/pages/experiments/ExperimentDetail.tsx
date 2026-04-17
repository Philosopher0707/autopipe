import { useMemo, useState, type FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, Badge, Button, Skeleton } from '@/components/ui'
import { experimentsApi } from '@/api/endpoints'
import { cn, formatDate, formatDuration } from '@/utils/helpers'
import type { PipelineRun } from '@/types'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
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
  const [activeTab, setActiveTab] = useState<'overview' | 'runs'>('overview')
  const [form, setForm] = useState<ExperimentFormState>(DEFAULT_FORM)
  const [formError, setFormError] = useState<string | null>(null)

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

  const chartData = useMemo(() => (
    runs
      .filter((run) => typeof run.metrics?.[metricName] === 'number')
      .map((run) => ({
        run: `Run ${run.run_number ?? run.id.slice(0, 8)}`,
        value: Number(run.metrics?.[metricName] ?? 0),
      }))
  ), [metricName, runs])

  const bestRun = runs.find((run) => run.id === experiment?.best_run_id)
    || [...runs]
      .filter((run) => typeof run.metrics?.[metricName] === 'number')
      .sort((left, right) => Number(right.metrics?.[metricName] ?? 0) - Number(left.metrics?.[metricName] ?? 0))[0]

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

  const completedRuns = runs.filter((run) => run.status === 'success').length
  const failedRuns = runs.filter((run) => run.status === 'failed').length
  const runningRuns = runs.filter((run) => run.status === 'running' || run.status === 'pending').length

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
            <Badge className={cn(
              experiment.status === 'running' ? 'bg-blue-100 text-blue-700' :
              experiment.status === 'completed' ? 'bg-green-100 text-green-700' :
              experiment.status === 'failed' ? 'bg-red-100 text-red-700' :
              'bg-amber-100 text-amber-700')}
            >
              {experiment.status}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">{experiment.description}</p>
        </div>
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
          {(['overview', 'runs'] as const).map((tab) => (
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
                <h3 className="font-semibold mb-4">Run Performance ({metricName})</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="run" fontSize={12} />
                      <YAxis fontSize={12} />
                      <Tooltip formatter={(value: number) => [value.toFixed(4), metricName]} />
                      <Bar dataKey="value" fill="#2563eb" name={metricName} />
                    </BarChart>
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
                        <Badge className={cn(
                          run.status === 'success' ? 'bg-green-100 text-green-700' :
                          run.status === 'running' ? 'bg-blue-100 text-blue-700' :
                          run.status === 'failed' ? 'bg-red-100 text-red-700' :
                          'bg-amber-100 text-amber-700')}
                        >
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

      {failedRuns > 0 && (
        <p className="text-sm text-muted-foreground">
          {failedRuns} failed {failedRuns === 1 ? 'run was' : 'runs were'} recorded for this experiment.
        </p>
      )}
    </div>
  )
}
