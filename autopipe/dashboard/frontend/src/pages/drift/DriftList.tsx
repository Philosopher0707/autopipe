import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, TrendingDown, ArrowRight, Bell, BellOff, Check } from 'lucide-react'
import { Card, CardContent, Badge, Button, Skeleton } from '@/components/ui'
import { driftApi } from '@/api/endpoints'
import { cn, formatRelativeTime } from '@/utils/helpers'

const mockDriftReports = [
  { id: '1', model_id: '1', drift_score: 0.28, drift_detected: true, features_drifted: 3, created_at: '2026-04-14T08:00:00Z' },
  { id: '2', model_id: '2', drift_score: 0.05, drift_detected: false, features_drifted: 0, created_at: '2026-04-13T10:00:00Z' },
  { id: '3', model_id: '1', drift_score: 0.35, drift_detected: true, features_drifted: 7, created_at: '2026-04-12T14:00:00Z' },
  { id: '4', model_id: '3', drift_score: 0.02, drift_detected: false, features_drifted: 0, created_at: '2026-04-11T09:00:00Z' },
]

const mockAlerts = [
  { id: '1', feature_name: 'avg_session_duration', severity: 'error', drift_score: 0.28, drift_type: 'feature', acknowledged: false, created_at: '2026-04-14T08:00:00Z' },
  { id: '2', feature_name: 'transaction_count', severity: 'warning', drift_score: 0.15, drift_type: 'feature', acknowledged: true, created_at: '2026-04-13T14:00:00Z' },
  { id: '3', feature_name: 'page_views', severity: 'warning', drift_score: 0.12, drift_type: 'feature', acknowledged: false, created_at: '2026-04-14T09:30:00Z' },
]

export function DriftList() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'reports' | 'alerts'>('reports')

  const { data: reports } = useQuery({
    queryKey: ['drift', 'reports'],
    queryFn: () => driftApi.listReports(),
    initialData: mockDriftReports as any,
  })

  const { data: alerts } = useQuery({
    queryKey: ['drift', 'alerts'],
    queryFn: () => driftApi.listAlerts(),
    initialData: mockAlerts as any,
  })

  const reports_ = reports || mockDriftReports
  const alerts_ = alerts || mockAlerts

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Drift Monitoring</h1>
        <p className="text-muted-foreground mt-1">Monitor data and prediction drift across your models</p>
      </div>

      {/* Drift Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-amber-600">{alerts_.filter(a => !a.acknowledged).length}</p>
            <p className="text-xs text-muted-foreground mt-1">Active Alerts</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-red-600">{reports_.filter(r => r.drift_detected).length}</p>
            <p className="text-xs text-muted-foreground mt-1">Drift Detections</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-primary">
              {reports_.length > 0 ? `${(reports_[0].drift_score * 100).toFixed(0)}%` : '0%'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Latest Drift Score</p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="border-b">
        <div className="flex gap-1">
          {(['reports', 'alerts'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize',
                activeTab === tab ? 'border-primary text-primary' : 'border-transparent text-muted-foreground'
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'reports' && (
        <div className="space-y-3">
          {reports_.map((report) => (
            <Card key={report.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center',
                      report.drift_detected ? 'bg-red-100' : 'bg-green-100')}>
                      <TrendingDown className={cn('w-5 h-5', report.drift_detected ? 'text-red-600' : 'text-green-600')} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium">Drift Report</p>
                        <Badge className={report.drift_detected ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}>
                          {report.drift_detected ? 'Drift Detected' : 'No Drift'}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {report.features_drifted} features drifted · Score: {(report.drift_score * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">{formatRelativeTime(report.created_at)}</span>
                    <Button variant="ghost" size="sm" onClick={() => navigate(`/drift/${report.id}`)}>
                      View <ArrowRight className="w-3 h-3 ml-1" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {activeTab === 'alerts' && (
        <div className="space-y-3">
          {alerts_.map((alert) => (
            <Card key={alert.id} className={cn('transition-shadow', !alert.acknowledged && 'border-amber-300')}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center',
                      alert.severity === 'error' ? 'bg-red-100' : 'bg-amber-100')}>
                      <AlertTriangle className={cn('w-5 h-5', alert.severity === 'error' ? 'text-red-600' : 'text-amber-600')} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{alert.feature_name}</p>
                        <Badge className={alert.severity === 'error' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}>
                          {alert.severity}
                        </Badge>
                        {!alert.acknowledged && <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {alert.drift_type} drift · PSI: {(alert.drift_score * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">{formatRelativeTime(alert.created_at)}</span>
                    {!alert.acknowledged && (
                      <Button variant="outline" size="sm">
                        <Check className="w-3 h-3 mr-1" /> Acknowledge
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
