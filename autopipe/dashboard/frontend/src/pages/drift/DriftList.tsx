import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, TrendingDown, ArrowRight, Check } from 'lucide-react'
import { Card, CardContent, Badge, Button, Skeleton } from '@/components/ui'
import { driftApi } from '@/api/endpoints'
import { cn, formatRelativeTime } from '@/utils/helpers'

export function DriftList() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'reports' | 'alerts'>('reports')

  const { data: reports, isLoading: reportsLoading } = useQuery({
    queryKey: ['drift', 'reports'],
    queryFn: () => driftApi.listReports(),
  })

  const { data: alerts, isLoading: alertsLoading } = useQuery({
    queryKey: ['drift', 'alerts'],
    queryFn: () => driftApi.listAlerts(),
  })

  const acknowledgeMutation = useMutation({
    mutationFn: (alertId: string) => driftApi.acknowledgeAlert(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drift', 'alerts'] })
    },
  })

  const reports_ = reports?.items || []
  const alerts_ = alerts?.items || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Drift Monitoring</h1>
        <p className="text-muted-foreground mt-1">Monitor data and prediction drift across your models</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-amber-600">{alerts_.filter((alert) => !alert.acknowledged).length}</p>
            <p className="text-xs text-muted-foreground mt-1">Active Alerts</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-red-600">{reports_.filter((report) => report.drift_detected).length}</p>
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
        reportsLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, index) => <Skeleton key={index} className="h-24" />)}
          </div>
        ) : reports_.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              No drift reports have been generated yet.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {reports_.map((report) => (
              <Card key={report.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center',
                        report.drift_detected ? 'bg-red-100' : 'bg-green-100')}
                      >
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
                          {report.features_drifted ?? 0} features drifted · Score: {(report.drift_score * 100).toFixed(1)}%
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
        )
      )}

      {activeTab === 'alerts' && (
        alertsLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, index) => <Skeleton key={index} className="h-24" />)}
          </div>
        ) : alerts_.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              No drift alerts are active.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {alerts_.map((alert) => (
              <Card key={alert.id} className={cn('transition-shadow', !alert.acknowledged && 'border-amber-300')}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center',
                        alert.severity === 'error' ? 'bg-red-100' : 'bg-amber-100')}
                      >
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
                          {alert.drift_type} drift · {alert.drift_metric.toUpperCase()}: {(alert.drift_score * 100).toFixed(1)}% · Threshold {(alert.threshold * 100).toFixed(1)}%
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{formatRelativeTime(alert.created_at)}</span>
                      {!alert.acknowledged && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={acknowledgeMutation.isPending}
                          onClick={() => acknowledgeMutation.mutate(alert.id)}
                        >
                          <Check className="w-3 h-3 mr-1" />
                          Acknowledge
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )
      )}
    </div>
  )
}
