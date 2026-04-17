import { useState, type FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  ArrowLeft, Play, GitBranch, Loader2,
} from 'lucide-react'
import {
  Card, CardContent, CardHeader, CardTitle, Badge, Button, Skeleton,
} from '@/components/ui'
import { pipelinesApi } from '@/api/endpoints'
import { cn, formatDate, formatDuration, getStatusBgColor } from '@/utils/helpers'

type PipelineFormState = {
  name: string
  description: string
  tags: string
  configText: string
}

const DEFAULT_FORM: PipelineFormState = {
  name: '',
  description: '',
  tags: '',
  configText: '{\n  "steps": []\n}',
}

function parseJsonConfig(configText: string): Record<string, unknown> | undefined {
  const trimmed = configText.trim()
  if (!trimmed) return undefined
  return JSON.parse(trimmed) as Record<string, unknown>
}

function parseTags(tags: string): string[] | undefined {
  const items = tags
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean)
  return items.length > 0 ? items : undefined
}

export function PipelineDetail() {
  const { pipelineId } = useParams<{ pipelineId: string }>()
  const navigate = useNavigate()
  const isNew = !pipelineId
  const [activeTab, setActiveTab] = useState<'overview' | 'runs' | 'config'>('overview')
  const [form, setForm] = useState<PipelineFormState>(DEFAULT_FORM)
  const [formError, setFormError] = useState<string | null>(null)

  const { data: pipeline, isLoading } = useQuery({
    queryKey: ['pipeline', pipelineId],
    queryFn: () => pipelinesApi.getById(pipelineId!),
    enabled: !!pipelineId,
  })

  const { data: runsData } = useQuery({
    queryKey: ['pipeline', pipelineId, 'runs'],
    queryFn: () => pipelinesApi.listRuns(pipelineId!, { limit: 20 }),
    enabled: !!pipelineId,
  })

  const triggerMutation = useMutation({
    mutationFn: () => pipelinesApi.triggerRun(pipelineId!),
    onSuccess: (run) => navigate(`/runs/${run.id}`),
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      const config = parseJsonConfig(form.configText)
      return pipelinesApi.create({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        tags: parseTags(form.tags),
        config,
      })
    },
    onSuccess: (createdPipeline) => {
      navigate(`/pipelines/${createdPipeline.id}`)
    },
  })

  const runs = runsData?.items || []

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError(null)

    if (!form.name.trim()) {
      setFormError('Pipeline name is required.')
      return
    }

    try {
      await createMutation.mutateAsync()
    } catch (error) {
      if (error instanceof SyntaxError) {
        setFormError('Configuration must be valid JSON.')
        return
      }
      setFormError('Unable to create pipeline.')
    }
  }

  if (isNew) {
    return (
      <div className="space-y-6 max-w-3xl">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/pipelines')}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold">New Pipeline</h1>
            <p className="text-muted-foreground">Create a runnable pipeline definition.</p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Pipeline Details</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleCreate}>
              <div>
                <label className="text-sm font-medium">Name</label>
                <input
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  placeholder="daily-feature-pipeline"
                />
              </div>

              <div>
                <label className="text-sm font-medium">Description</label>
                <textarea
                  value={form.description}
                  onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                  className="mt-1 min-h-24 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  placeholder="Describe what this pipeline runs and why it exists."
                />
              </div>

              <div>
                <label className="text-sm font-medium">Tags</label>
                <input
                  value={form.tags}
                  onChange={(event) => setForm((current) => ({ ...current, tags: event.target.value }))}
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  placeholder="batch, nightly, feature-store"
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

              {formError && (
                <p className="text-sm text-destructive">{formError}</p>
              )}

              <div className="flex items-center justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => navigate('/pipelines')}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  Create Pipeline
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-96" />
      </div>
    )
  }

  if (!pipeline) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Pipeline not found</p>
        <Button variant="ghost" onClick={() => navigate('/pipelines')} className="mt-4">
          Back to Pipelines
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button variant="ghost" onClick={() => navigate('/pipelines')}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold">{pipeline.name}</h1>
              <Badge variant={pipeline.is_active ? 'default' : 'secondary'}>
                {pipeline.is_active ? 'Active' : 'Inactive'}
              </Badge>
            </div>
            {pipeline.description && (
              <p className="text-muted-foreground mt-1">{pipeline.description}</p>
            )}
            {pipeline.tags && pipeline.tags.length > 0 && (
              <div className="flex gap-2 mt-2">
                {pipeline.tags.map((tag) => (
                  <Badge key={tag} variant="outline" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>
        <Button
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending}
          className="flex items-center gap-2"
        >
          {triggerMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          Run Pipeline
        </Button>
      </div>

      <div className="border-b border-border">
        <div className="flex gap-6">
          {(['overview', 'runs', 'config'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'pb-3 text-sm font-medium capitalize transition-colors border-b-2 -mb-px',
                activeTab === tab
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Pipeline Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Pipeline ID</span>
                <span className="text-sm font-mono">{pipeline.id.slice(0, 8)}...</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Total Runs</span>
                <span className="text-sm">{pipeline.run_count ?? runs.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Created</span>
                <span className="text-sm">{formatDate(pipeline.created_at)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Last Updated</span>
                <span className="text-sm">{formatDate(pipeline.updated_at)}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Runs</CardTitle>
            </CardHeader>
            <CardContent>
              {runs.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No runs yet</p>
              ) : (
                <div className="space-y-2">
                  {runs.slice(0, 5).map((run) => (
                    <button
                      key={run.id}
                      className="flex w-full items-center justify-between rounded-lg p-2 text-left hover:bg-muted"
                      onClick={() => navigate(`/runs/${run.id}`)}
                    >
                      <div className="flex items-center gap-2">
                        <div className={cn('w-2 h-2 rounded-full',
                          run.status === 'success' ? 'bg-green-500' :
                          run.status === 'failed' ? 'bg-red-500' :
                          run.status === 'running' ? 'bg-blue-500 animate-pulse' :
                          'bg-amber-500')}
                        />
                        <span className="text-sm font-medium">
                          Run #{run.run_number || run.id.slice(0, 8)}
                        </span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {run.duration_seconds ? formatDuration(run.duration_seconds) : '--'}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'runs' && (
        <Card>
          <CardContent className="p-0">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Run</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Status</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Duration</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Started</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-muted-foreground">
                      No runs found
                    </td>
                  </tr>
                ) : (
                  runs.map((run) => (
                    <tr key={run.id} className="border-b last:border-0 hover:bg-muted/50">
                      <td className="py-3 px-4">
                        <span className="text-sm font-medium">
                          #{run.run_number || run.id.slice(0, 8)}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <Badge className={getStatusBgColor(run.status)}>{run.status}</Badge>
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {run.duration_seconds ? formatDuration(run.duration_seconds) : '--'}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {run.started_at ? formatDate(run.started_at) : '--'}
                      </td>
                      <td className="py-3 px-4">
                        <button
                          onClick={() => navigate(`/runs/${run.id}`)}
                          className="text-sm text-primary hover:underline"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {activeTab === 'config' && (
        <Card>
          <CardHeader>
            <CardTitle>Pipeline Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            {pipeline.config ? (
              <pre className="text-sm bg-muted p-4 rounded-lg overflow-auto max-h-96 font-mono">
                {JSON.stringify(pipeline.config, null, 2)}
              </pre>
            ) : (
              <div className="py-8 text-center text-sm text-muted-foreground">
                <GitBranch className="mx-auto mb-3 h-10 w-10" />
                No configuration saved
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
