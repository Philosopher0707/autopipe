import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  ArrowLeft, Play, Settings, GitBranch, Clock, CheckCircle,
  XCircle, Loader2, Activity, Tag, FileText
} from 'lucide-react'
import {
  Card, CardContent, CardHeader, CardTitle, Badge, Button, Skeleton
} from '@/components/ui'
import { pipelinesApi } from '@/api/endpoints'
import { cn, formatDate, formatDuration, getStatusBgColor } from '@/utils/helpers'

export function PipelineDetail() {
  const { pipelineId } = useParams<{ pipelineId: string }>()
  const navigate = useNavigate()
  const isNew = pipelineId === 'new'
  const [activeTab, setActiveTab] = useState('overview')

  const { data: pipeline, isLoading } = useQuery({
    queryKey: ['pipeline', pipelineId],
    queryFn: () => pipelinesApi.getById(Number(pipelineId)),
    enabled: !!pipelineId && !isNew,
  })

  const { data: runsData } = useQuery({
    queryKey: ['pipeline', pipelineId, 'runs'],
    queryFn: () => pipelinesApi.listRuns(Number(pipelineId), { limit: 20 }),
    enabled: !!pipelineId && !isNew,
  })

  const triggerMutation = useMutation({
    mutationFn: () => pipelinesApi.triggerRun(Number(pipelineId)),
    onSuccess: (run) => navigate(`/runs/${run.id}`),
  })

  const runs = runsData?.items || []

  if (isNew) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/pipelines')}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold">New Pipeline</h1>
            <p className="text-muted-foreground">Create a new ML pipeline</p>
          </div>
        </div>
        <Card>
          <CardContent className="p-8 text-center">
            <GitBranch className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Pipeline Editor</h3>
            <p className="text-muted-foreground text-sm mb-4">
              YAML-based pipeline configuration editor coming soon.
              For now, pipelines can be triggered programmatically.
            </p>
            <Button onClick={() => navigate('/pipelines')}>
              Back to Pipelines
            </Button>
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
      {/* Header */}
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

      {/* Tabs */}
      <div className="border-b border-border">
        <div className="flex gap-6">
          {['overview', 'runs', 'config'].map((tab) => (
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

      {/* Tab Content */}
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
                <span className="text-sm">{runs.length}</span>
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
                    <div
                      key={run.id}
                      className="flex items-center justify-between p-2 rounded-lg hover:bg-muted cursor-pointer"
                      onClick={() => navigate(`/runs/${run.id}`)}
                    >
                      <div className="flex items-center gap-2">
                        <div className={cn('w-2 h-2 rounded-full',
                          run.status === 'success' ? 'bg-green-500' :
                          run.status === 'failed' ? 'bg-red-500' :
                          run.status === 'running' ? 'bg-blue-500 animate-pulse' :
                          'bg-amber-500'
                        )} />
                        <span className="text-sm font-medium">
                          Run #{run.run_number || run.id.slice(0, 8)}
                        </span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {run.duration_seconds ? formatDuration(run.duration_seconds) : '--'}
                      </span>
                    </div>
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
                        <Badge className={getStatusBgColor(run.status as string)}>
                          {run.status}
                        </Badge>
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
              <p className="text-sm text-muted-foreground text-center py-8">
                No configuration saved
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
