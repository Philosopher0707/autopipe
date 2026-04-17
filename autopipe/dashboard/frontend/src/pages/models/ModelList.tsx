import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardTitle, Skeleton, Badge } from '@/components/ui'
import { modelsApi } from '@/api/endpoints'
import {
  Search, Plus, Box, ArrowRight, Clock, Layers
} from 'lucide-react'
import { formatRelativeTime } from '@/utils/helpers'
import type { Model } from '@/types'

export function ModelList() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['models', { search }],
    queryFn: () => modelsApi.list({ search: search || undefined }),
  })

  const models: Model[] = data?.items || []

  const getStageColor = (stage: string) => {
    const colors: Record<string, string> = {
      production: 'bg-green-100 text-green-800',
      staging: 'bg-blue-100 text-blue-800',
      pending: 'bg-amber-100 text-amber-800',
      archived: 'bg-gray-100 text-gray-800',
    }
    return colors[stage] || colors.pending
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Model Registry</h1>
          <p className="text-muted-foreground mt-1">
            Manage and version your ML models
          </p>
        </div>
        <button
          onClick={() => navigate('/models/new')}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
        >
          <Plus className="w-4 h-4" />
          Register Model
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search models..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full h-10 pl-10 pr-4 border border-input rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Models Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : models.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Box className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold">No models found</h3>
            <p className="text-muted-foreground mt-1">
              {search ? 'Try a different search term' : 'Register your first model'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {models.map((model: Model) => (
            <Card key={model.id} className="hover:shadow-lg transition-shadow group cursor-pointer">
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                      <Box className="w-5 h-5 text-purple-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">{model.name}</h3>
                      <p className="text-xs text-muted-foreground">
                        {model.framework} • {model.version_count || 0} versions
                      </p>
                    </div>
                  </div>
                </div>

                {model.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                    {model.description}
                  </p>
                )}

                {/* Tags */}
                {model.tags && model.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-4">
                    {model.tags.slice(0, 3).map((tag: string) => (
                      <Badge key={tag} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between pt-4 border-t border-border">
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    {formatRelativeTime(model.updated_at)}
                  </div>
                  <button
                    onClick={() => navigate(`/models/${model.id}`)}
                    className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-colors"
                  >
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
