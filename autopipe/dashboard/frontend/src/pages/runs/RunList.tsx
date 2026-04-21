import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardTitle, Skeleton, Button } from '@/components/ui'
import { runsApi } from '@/api/endpoints'
import {
  Search, Clock, MoreHorizontal, GitCompare, X
} from 'lucide-react'
import { formatDate, formatDuration, getStatusBgColor } from '@/utils/helpers'
import type { PipelineRun } from '@/types'

export function RunList() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set())

  const { data, isLoading } = useQuery({
    queryKey: ['runs', { search, status: statusFilter }],
    queryFn: () => runsApi.list({
      search: search || undefined,
      status: statusFilter !== 'all' ? statusFilter : undefined,
    }),
  })

  const runs: PipelineRun[] = data?.items || []

  const handleToggleSelect = (runId: string) => {
    const newSelected = new Set(selectedRuns)
    if (newSelected.has(runId)) {
      newSelected.delete(runId)
    } else {
      newSelected.add(runId)
    }
    setSelectedRuns(newSelected)
  }

  const handleSelectAll = () => {
    if (selectedRuns.size === runs.length) {
      setSelectedRuns(new Set())
    } else {
      setSelectedRuns(new Set(runs.map(r => r.id)))
    }
  }

  const handleClearSelection = () => setSelectedRuns(new Set())

  const handleCompare = () => {
    if (selectedRuns.size >= 2) {
      navigate(`/runs/compare?ids=${Array.from(selectedRuns).join(',')}`)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Runs</h1>
          <p className="text-muted-foreground mt-1">
            Monitor and manage your pipeline executions
          </p>
        </div>
      </div>

      {/* Selection Bar */}
      {selectedRuns.size >= 2 && (
        <div className="flex items-center justify-between p-3 bg-primary/10 rounded-lg border border-primary/20">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{selectedRuns.size} runs selected</span>
          </div>
          <div className="flex items-center gap-2">
            <Button 
              size="sm" 
              variant="outline" 
              onClick={handleClearSelection}
              className="h-8"
            >
              <X className="w-4 h-4 mr-1" />
              Clear
            </Button>
            <Button 
              size="sm" 
              onClick={handleCompare}
              className="h-8"
            >
              <GitCompare className="w-4 h-4 mr-1" />
              Compare
            </Button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search runs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-10 pl-10 pr-4 border border-input rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 px-3 border border-input rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All Status</option>
          <option value="running">Running</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      {/* Runs Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 space-y-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
          ) : runs.length === 0 ? (
            <div className="p-12 text-center">
              <Clock className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold">No runs found</h3>
              <p className="text-muted-foreground mt-1">
                {search ? 'Try a different search term' : 'Runs will appear here'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-3 px-4 text-left w-10">
                      <input
                        type="checkbox"
                        checked={runs.length > 0 && selectedRuns.size === runs.length}
                        onChange={handleSelectAll}
                        className="rounded border-border"
                      />
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Run ID
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Pipeline
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Status
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Started
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Duration
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr
                      key={run.id}
                      className="border-b border-border last:border-0 hover:bg-muted/50 cursor-pointer"
                      onClick={() => navigate(`/runs/${run.id}`)}
                    >
                      <td className="py-3 px-4" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedRuns.has(run.id)}
                          onChange={() => handleToggleSelect(run.id)}
                          className="rounded border-border"
                        />
                      </td>
                      <td className="py-3 px-4">
                        <div>
                          <CardTitle className="text-sm font-medium text-foreground">
                            Run #{run.id.slice(-8)}
                          </CardTitle>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-foreground">
                          {run.pipeline_name || run.pipeline_id}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusBgColor(run.status)}`}>
                          {run.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {run.started_at ? formatDate(run.started_at) : '--'}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {run.duration_seconds ? formatDuration(run.duration_seconds) : '--'}
                      </td>
                      <td className="py-3 px-4">
                        <button 
                          className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreHorizontal className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
