import { useState, type FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Download, Loader2, TrendingUp,
} from 'lucide-react'
import {
  Card, CardContent, CardHeader, CardTitle, Badge, Button, Skeleton,
} from '@/components/ui'
import { modelsApi, type ModelComparisonResponse } from '@/api/endpoints'
import { formatRelativeTime } from '@/utils/helpers'
import type { ModelVersion } from '@/types'

type ModelFormState = {
  name: string
  description: string
  framework: string
  taskType: string
  tags: string
}

const DEFAULT_FORM: ModelFormState = {
  name: '',
  description: '',
  framework: 'xgboost',
  taskType: 'classification',
  tags: '',
}

const STAGE_COLORS: Record<string, string> = {
  production: 'bg-green-100 text-green-700',
  staging: 'bg-blue-100 text-blue-700',
  pending: 'bg-amber-100 text-amber-700',
  archived: 'bg-gray-100 text-gray-600',
}

function parseTags(tags: string): string[] | undefined {
  const items = tags.split(',').map((tag) => tag.trim()).filter(Boolean)
  return items.length > 0 ? items : undefined
}

function nextStageForVersion(version: ModelVersion): 'staging' | 'production' | null {
  if (version.stage === 'pending' || version.stage === 'archived') {
    return 'staging'
  }
  if (version.stage === 'staging') {
    return 'production'
  }
  return null
}

export function ModelDetail() {
  const { modelId } = useParams<{ modelId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isNew = !modelId
  const [form, setForm] = useState<ModelFormState>(DEFAULT_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [selectedVersions, setSelectedVersions] = useState<number[]>([])
  const [comparison, setComparison] = useState<ModelComparisonResponse | null>(null)

  const { data: model, isLoading } = useQuery({
    queryKey: ['model', modelId],
    queryFn: () => modelsApi.getById(modelId!),
    enabled: !!modelId,
  })

  // Versions from model response (eager loaded) OR fallback to separate query
  const { data: versionsData, isLoading: versionsLoading } = useQuery({
    queryKey: ['model', modelId, 'versions'],
    queryFn: () => modelsApi.listVersions(modelId!),
    // Skip if model already has versions pre-loaded
    enabled: !!modelId && !model?.versions?.length,
  })
  
  // Use versions from model response when available, otherwise from query
  const versions = model?.versions ?? versionsData?.items ?? []
  
  const bestVersion = versions.find((version) => version.stage === 'production')
    || versions.find((version) => version.stage === 'staging')
    || versions[0]
  
  const isLoadingModel = isLoading || (versionsLoading && !model?.versions)
  
  const createMutation = useMutation({
    mutationFn: () => modelsApi.create({
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      framework: form.framework.trim(),
      task_type: form.taskType.trim() || undefined,
      tags: parseTags(form.tags),
    }),
    onSuccess: (createdModel) => navigate(`/models/${createdModel.id}`),
  })

  const promoteMutation = useMutation({
    mutationFn: ({ version, stage }: { version: number; stage: string }) =>
      modelsApi.updateVersionStage(modelId!, version, { stage }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['model', modelId] })
      queryClient.invalidateQueries({ queryKey: ['model', modelId, 'versions'] })
    },
  })

  const compareMutation = useMutation({
    mutationFn: ({ versionA, versionB }: { versionA: number; versionB: number }) =>
      modelsApi.compare({
        model_id: modelId!,
        version_a: versionA,
        version_b: versionB,
      }),
    onSuccess: (response) => setComparison(response),
  })

  const toggleVersion = (version: number) => {
    setComparison(null)
    setSelectedVersions((current) => {
      if (current.includes(version)) {
        return current.filter((item) => item !== version)
      }
      if (current.length === 2) {
        return [current[1], version]
      }
      return [...current, version]
    })
  }

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError(null)

    if (!form.name.trim() || !form.framework.trim()) {
      setFormError('Model name and framework are required.')
      return
    }

    try {
      await createMutation.mutateAsync()
    } catch {
      setFormError('Unable to register model.')
    }
  }

  if (isNew) {
    return (
      <div className="space-y-6 max-w-3xl">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/models')}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold">Register Model</h1>
            <p className="text-muted-foreground">Create a stable model registry entry before publishing versions.</p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Model Metadata</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleCreate}>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="text-sm font-medium">Name</label>
                  <input
                    value={form.name}
                    onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    placeholder="customer-churn-model"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Framework</label>
                  <input
                    value={form.framework}
                    onChange={(event) => setForm((current) => ({ ...current, framework: event.target.value }))}
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    placeholder="xgboost"
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="text-sm font-medium">Task Type</label>
                  <input
                    value={form.taskType}
                    onChange={(event) => setForm((current) => ({ ...current, taskType: event.target.value }))}
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    placeholder="classification"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Tags</label>
                  <input
                    value={form.tags}
                    onChange={(event) => setForm((current) => ({ ...current, tags: event.target.value }))}
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    placeholder="production, baseline"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm font-medium">Description</label>
                <textarea
                  value={form.description}
                  onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                  className="mt-1 min-h-24 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  placeholder="What does this model do and where is it used?"
                />
              </div>

              {formError && <p className="text-sm text-destructive">{formError}</p>}

              <div className="flex justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => navigate('/models')}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  Register Model
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoadingModel) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-40" />
        <Skeleton className="h-96" />
      </div>
    )
  }

  if (!model) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Model not found</p>
        <Button variant="ghost" onClick={() => navigate('/models')} className="mt-4">
          Back to Models
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
            <h1 className="text-2xl font-bold">{model.name}</h1>
            <Badge className={STAGE_COLORS[model.current_stage || 'pending']}>
              {model.current_stage}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">{model.description}</p>
          <div className="flex gap-2 mt-2">
            <Badge variant="outline">{model.framework}</Badge>
            {model.task_type ? <Badge variant="outline">{model.task_type}</Badge> : null}
            {model.tags?.map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}
          </div>
        </div>
      </div>

      {bestVersion?.metrics && Object.keys(bestVersion.metrics).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>
              {bestVersion.stage === 'production' ? 'Production Version' : 'Latest Version'} (v{bestVersion.version})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(bestVersion.metrics).map(([key, value]) => (
                <div key={key} className="text-center">
                  <p className="text-2xl font-bold text-primary">
                    {typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : String(value)}
                  </p>
                  <p className="text-xs text-muted-foreground uppercase">{key}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Version History</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {versions.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No versions registered for this model yet.
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Version</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Stage</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Metrics</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Created</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {versions.map((version) => {
                  const promoteTarget = nextStageForVersion(version)
                  return (
                    <tr key={version.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={selectedVersions.includes(version.version)}
                            onChange={() => toggleVersion(version.version)}
                            className="rounded"
                          />
                          <span className="font-mono font-medium">v{version.version}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge className={STAGE_COLORS[version.stage]}>{version.stage}</Badge>
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {version.metrics && Object.keys(version.metrics).length > 0
                          ? Object.entries(version.metrics).slice(0, 3).map(([key, value]) => `${key}: ${value}`).join(' • ')
                          : 'No metrics'}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {formatRelativeTime(version.created_at)}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex gap-2">
                          {promoteTarget ? (
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={promoteMutation.isPending}
                              onClick={() => promoteMutation.mutate({ version: version.version, stage: promoteTarget })}
                            >
                              <TrendingUp className="w-4 h-4 mr-1" />
                              {promoteTarget === 'production' ? 'Promote' : 'Stage'}
                            </Button>
                          ) : null}
                          <Button variant="ghost" size="sm" onClick={() => window.open(`/api/v1/models/${model.id}/download/${version.version}`, '_blank')}>
                            <Download className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {selectedVersions.length === 2 && (
        <div className="space-y-4 rounded-lg bg-muted p-4">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm">
              Selected v{selectedVersions[0]} and v{selectedVersions[1]}
            </span>
            <Button
              size="sm"
              disabled={compareMutation.isPending}
              onClick={() => compareMutation.mutate({
                versionA: selectedVersions[0],
                versionB: selectedVersions[1],
              })}
            >
              {compareMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Compare Versions
            </Button>
          </div>

          {comparison && (
            <Card>
              <CardHeader>
                <CardTitle>Comparison Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p>{comparison.report}</p>
                <div className="grid gap-2 md:grid-cols-2">
                  {Object.entries(comparison.metric_differences).map(([metric, difference]) => (
                    <div key={metric} className="rounded-lg border border-border px-3 py-2">
                      <span className="text-muted-foreground">{metric}</span>
                      <p className={`font-medium ${difference >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {difference >= 0 ? '+' : ''}
                        {difference.toFixed(4)}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
