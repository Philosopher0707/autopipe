import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, AlertTriangle, TrendingDown } from 'lucide-react'
import { Card, CardContent, CardHeader, Badge, Button } from '@/components/ui'
import { cn, formatDate } from '@/utils/helpers'

const mockReport = {
  id: '1', model_id: '1', drift_score: 0.28, drift_detected: true,
  features_drifted: { avg_session_duration: 0.28, transaction_count: 0.15, page_views: 0.12 },
  created_at: '2026-04-14T08:00:00Z',
}

export function DriftReport() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<'all' | 'drifted'>('all')

  const report = mockReport
  const features = Object.entries(report.features_drifted as Record<string, number>)

  const filtered = filter === 'drifted'
    ? features.filter(([, score]) => score > 0.1)
    : features

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Back
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Drift Report</h1>
          <p className="text-muted-foreground">Generated {formatDate(report.created_at)}</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className={cn('text-3xl font-bold', report.drift_detected ? 'text-red-600' : 'text-green-600')}>
              {(report.drift_score * 100).toFixed(0)}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">Drift Score</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-amber-600">{filtered.length}</p>
            <p className="text-xs text-muted-foreground mt-1">Features Drifted</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className={cn('text-3xl font-bold', report.drift_detected ? 'text-red-600' : 'text-green-600')}>
              {report.drift_detected ? 'Yes' : 'No'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Drift Detected</p>
          </CardContent>
        </Card>
      </div>

      {/* Feature Drift Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <span className="font-semibold">Feature Drift Analysis</span>
            <div className="flex gap-1">
              {(['all', 'drifted'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={cn('px-2 py-1 text-xs rounded', filter === f ? 'bg-primary text-primary-foreground' : 'bg-muted')}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Feature</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">PSI Score</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Status</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Severity</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(([feature, score]) => {
                const drifted = score > 0.1
                return (
                  <tr key={feature} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="py-3 px-4 font-mono text-sm">{feature}</td>
                    <td className="py-3 px-4 font-mono text-sm">{(score * 100).toFixed(1)}%</td>
                    <td className="py-3 px-4">
                      <Badge className={drifted ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}>
                        {drifted ? 'Drifted' : 'Stable'}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">
                      <div className="w-full bg-muted rounded-full h-2 max-w-32">
                        <div
                          className={cn('h-2 rounded-full', drifted ? 'bg-red-500' : 'bg-green-500')}
                          style={{ width: `${Math.min(100, score * 300)}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
