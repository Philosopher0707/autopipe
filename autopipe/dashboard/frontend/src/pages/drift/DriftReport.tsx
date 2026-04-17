import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts'
import { Card, CardContent, CardHeader, Badge, Button, Skeleton } from '@/components/ui'
import { driftApi, chartsApi } from '@/api/endpoints'
import { cn, formatDate } from '@/utils/helpers'
import type { DriftFeature, DriftReport as DriftReportType } from '@/types'

export function DriftReport() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<'all' | 'drifted'>('all')

  const { data: report, isLoading } = useQuery<DriftReportType>({
    queryKey: ['drift', 'report', reportId],
    queryFn: () => driftApi.getReport(reportId!),
    enabled: !!reportId,
  })

  const { data: featureScores } = useQuery({
    queryKey: ['charts', 'drift-feature-scores', reportId],
    queryFn: () => chartsApi.getDriftFeatureScores(reportId!),
    enabled: !!reportId,
  })

  if (isLoading) {
    return <div className="space-y-6"><Skeleton className="h-32" /><Skeleton className="h-64" /></div>
  }

  if (!report) {
    return <div className="text-center py-12"><p className="text-muted-foreground">Report not found</p><Button variant="ghost" onClick={() => navigate('/drift')} className="mt-4">Back to Drift</Button></div>
  }

  const featureDrifts = report.feature_drifts || {}
  const features = Object.entries(featureDrifts).map(([name, details]) => ({
    name,
    ...(details as DriftFeature),
  }))

  const filtered = filter === 'drifted'
    ? features.filter((feature) => feature.is_drifted)
    : features

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Drift Report</h1>
          <p className="text-muted-foreground">Generated {formatDate(report.created_at)}</p>
        </div>
      </div>

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
            <p className="text-3xl font-bold text-amber-600">{report.features_drifted ?? 0}</p>
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

      {featureScores && featureScores.features.length > 0 && (
        <Card>
          <CardHeader>
            <span className="font-semibold">Feature Drift Scores</span>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={featureScores.features} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" fontSize={12} />
                  <YAxis dataKey="name" type="category" width={150} fontSize={11} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                    formatter={(v: number) => [`${(v * 100).toFixed(1)}%`]}
                  />
                  <ReferenceLine x={featureScores.features[0]?.threshold} stroke="#ef4444" strokeDasharray="3 3" label={{ value: 'Threshold', position: 'top', fill: '#ef4444', fontSize: 11 }} />
                  <Bar dataKey="drift_score" name="Drift Score">
                    {featureScores.features.map((f, i) => (
                      <Cell key={i} fill={f.is_drifted ? '#ef4444' : '#10b981'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <span className="font-semibold">Feature Drift Analysis</span>
            <div className="flex gap-1">
              {(['all', 'drifted'] as const).map((value) => (
                <button
                  key={value}
                  onClick={() => setFilter(value)}
                  className={cn('px-2 py-1 text-xs rounded', filter === value ? 'bg-primary text-primary-foreground' : 'bg-muted')}
                >
                  {value}
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
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Score</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">P-Value</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Test</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-muted-foreground">
                    No feature drift entries match the current filter.
                  </td>
                </tr>
              ) : (
                filtered.map((feature) => (
                  <tr key={feature.name} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="py-3 px-4 font-mono text-sm">{feature.name}</td>
                    <td className="py-3 px-4 font-mono text-sm">{(feature.drift_score * 100).toFixed(1)}%</td>
                    <td className="py-3 px-4 font-mono text-sm">
                      {feature.p_value != null ? feature.p_value.toFixed(4) : '--'}
                    </td>
                    <td className="py-3 px-4 text-sm text-muted-foreground">
                      {feature.test_type.toUpperCase()} · threshold {(feature.threshold * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-4">
                      <Badge className={feature.is_drifted ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}>
                        {feature.is_drifted ? 'Drifted' : 'Stable'}
                      </Badge>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
