import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus, Search, ArrowRight, Clock,
  GitBranch, Play, Trash2, Loader2
} from 'lucide-react'
import {
  Card, CardContent, Badge, Button, Skeleton
} from '@/components/ui'
import { pipelinesApi } from '@/api/endpoints'
import { formatRelativeTime } from '@/utils/helpers'
import { useAuthStore } from '@/stores'

export function PipelineList() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading, error } = useQuery({
    queryKey: ['pipelines', { search, page }],
    queryFn: () => pipelinesApi.list({ search: search || undefined, limit: 20, skip: (page - 1) * 20 }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => pipelinesApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipelines'] }),
  })

  const triggerMutation = useMutation({
    mutationFn: (id: string) => pipelinesApi.triggerRun(id),
    onSuccess: (run) => navigate(`/runs/${run.id}`),
  })

  const pipelines = data?.items || []
  const isAdmin = user?.role === 'admin'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Pipelines</h1>
          <p className="text-muted-foreground mt-1">
            Manage and monitor your ML pipelines
          </p>
        </div>
        <Link to="/pipelines/new">
          <Button className="flex items-center gap-2">
            <Plus className="w-4 h-4" />
            New Pipeline
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search pipelines..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-10 pl-10 pr-4 border border-input rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      {/* Pipeline Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-destructive">Failed to load pipelines. Please try again.</p>
          </CardContent>
        </Card>
      ) : pipelines.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <GitBranch className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold">No pipelines found</h3>
            <p className="text-muted-foreground mt-1">
              {search ? 'Try a different search term' : 'Create your first pipeline to get started'}
            </p>
            {!search && (
              <Link to="/pipelines/new">
                <Button className="mt-4">
                  <Plus className="w-4 h-4 mr-2" />
                  Create Pipeline
                </Button>
              </Link>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {pipelines.map((pipeline) => (
            <Card key={pipeline.id} className="hover:shadow-lg transition-shadow group">
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                      <GitBranch className="w-5 h-5 text-blue-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground line-clamp-1">
                        {pipeline.name}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {pipeline.run_count || 0} runs
                      </p>
                    </div>
                  </div>
                  <Badge variant={pipeline.is_active ? 'default' : 'secondary'}>
                    {pipeline.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>

                {pipeline.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                    {pipeline.description}
                  </p>
                )}

                {/* Tags */}
                {pipeline.tags && pipeline.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-4">
                    {pipeline.tags.slice(0, 3).map((tag: string) => (
                      <Badge key={tag} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                    {pipeline.tags.length > 3 && (
                      <Badge variant="outline" className="text-xs">
                        +{pipeline.tags.length - 3}
                      </Badge>
                    )}
                  </div>
                )}

                {/* Footer */}
                <div className="flex items-center justify-between pt-4 border-t border-border">
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    {formatRelativeTime(pipeline.created_at)}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => triggerMutation.mutate(pipeline.id)}
                      disabled={triggerMutation.isPending}
                      className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      title="Run pipeline"
                    >
                      {triggerMutation.isPending && triggerMutation.variables === pipeline.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Play className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      onClick={() => navigate(`/pipelines/${pipeline.id}`)}
                      className="p-2 text-muted-foreground hover:bg-muted rounded-lg transition-colors"
                    >
                      <ArrowRight className="w-4 h-4" />
                    </button>
                    {isAdmin && (
                      <button
                        onClick={() => {
                          if (confirm('Delete this pipeline?')) {
                            deleteMutation.mutate(pipeline.id)
                          }
                        }}
                        disabled={deleteMutation.isPending}
                        className="p-2 text-destructive hover:bg-destructive/10 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination */}
      {data && data.total > 20 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {Math.ceil(data.total / 20)}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(data.total / 20)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
