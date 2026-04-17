import { useNavigate } from 'react-router-dom'
import { ArrowRight, Activity } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge } from '@/components/ui'
import { cn, getStatusBgColor, formatDuration } from '@/utils/helpers'
import type { PipelineRun } from '@/types'

interface ActivePipelinesProps {
  runs: PipelineRun[]
}

export function ActivePipelines({ runs }: ActivePipelinesProps) {
  const navigate = useNavigate()

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Active Pipelines</CardTitle>
          <button
            className="text-sm text-primary hover:underline flex items-center gap-1"
            onClick={() => navigate('/runs')}
          >
            View All
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                  Pipeline
                </th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                  Status
                </th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                  Progress
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
                  className="border-b border-border last:border-0 hover:bg-muted/50"
                >
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          'w-8 h-8 rounded-lg flex items-center justify-center',
                          run.status === 'running'
                            ? 'bg-blue-100'
                            : run.status === 'success'
                            ? 'bg-green-100'
                            : 'bg-amber-100'
                        )}
                      >
                        <Activity
                          className={cn(
                            'w-4 h-4',
                            run.status === 'running'
                              ? 'text-blue-600'
                              : run.status === 'success'
                              ? 'text-green-600'
                              : 'text-amber-600'
                          )}
                        />
                      </div>
                      <div>
                        <p className="font-medium text-foreground">{run.pipeline_name || run.pipeline_id}</p>
                        <p className="text-xs text-muted-foreground">Run #{run.run_number || run.id.slice(0, 8)}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <Badge className={getStatusBgColor(run.status)}>
                      {run.status === 'running' && (
                        <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5 animate-pulse" />
                      )}
                      {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
                    </Badge>
                  </td>
                  <td className="py-3 px-4">
                    {run.status === 'running' && (
                      <>
                        <div className="w-full bg-muted rounded-full h-2 mb-1">
                          <div className="bg-primary h-2 rounded-full w-[65%]" />
                        </div>
                        <span className="text-xs text-muted-foreground">65%</span>
                      </>
                    )}
                    {run.status === 'success' && (
                      <>
                        <div className="w-full bg-muted rounded-full h-2 mb-1">
                          <div className="bg-green-500 h-2 rounded-full w-full" />
                        </div>
                        <span className="text-xs text-muted-foreground">100%</span>
                      </>
                    )}
                    {run.status === 'pending' && (
                      <span className="text-sm text-muted-foreground">Queued</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-sm text-muted-foreground">
                    {run.duration_seconds ? formatDuration(run.duration_seconds) : '--'}
                  </td>
                  <td className="py-3 px-4">
                    <button className="text-sm text-primary hover:underline">
                      {run.status === 'running' ? 'Logs' : 'View'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
