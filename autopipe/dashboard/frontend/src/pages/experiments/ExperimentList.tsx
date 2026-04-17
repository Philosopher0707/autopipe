import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Card, CardContent, Skeleton, Badge } from '@/components/ui'
import { experimentsApi } from '@/api/endpoints'
import {
  Plus, Search, FlaskConical, Activity, Clock, ArrowRight
} from 'lucide-react'
import { formatRelativeTime, getStatusBgColor } from '@/utils/helpers'
import type { Experiment } from '@/types'

export function ExperimentList() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['experiments', { search }],
    queryFn: () => experimentsApi.list({ search: search || undefined }),
  })

  const experiments: Experiment[] = data?.items || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Experiments</h1>
          <p className="text-muted-foreground mt-1">
            Track and compare your ML experiments
          </p>
        </div>
        <Link to="/experiments/new">
          <button className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90">
            <Plus className="w-4 h-4" />
            New Experiment
          </button>
        </Link>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search experiments..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full h-10 pl-10 pr-4 border border-input rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Experiments Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : experiments.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <FlaskConical className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold">No experiments found</h3>
            <p className="text-muted-foreground mt-1">
              {search ? 'Try a different search term' : 'Create your first experiment'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {experiments.map((exp: Experiment) => (
            <Card
              key={exp.id}
              className="hover:shadow-lg transition-shadow group cursor-pointer"
              onClick={() => navigate(`/experiments/${exp.id}`)}
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-pink-100 rounded-lg flex items-center justify-center">
                      <FlaskConical className="w-5 h-5 text-pink-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">{exp.name}</h3>
                      <Badge className={getStatusBgColor(exp.status)}>{exp.status}</Badge>
                    </div>
                  </div>
                </div>

                {exp.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                    {exp.description}
                  </p>
                )}

                {/* Tags */}
                {exp.tags && exp.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-4">
                    {exp.tags.slice(0, 3).map((tag: string) => (
                      <Badge key={tag} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}

                {exp.best_metric && (
                  <div className="mb-4 p-3 bg-muted rounded-lg">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Activity className="w-3 h-3" />
                      <span>Best: {exp.best_metric.toFixed(4)}</span>
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between pt-4 border-t border-border">
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    {formatRelativeTime(exp.updated_at)}
                  </div>
                  <button className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-colors">
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
