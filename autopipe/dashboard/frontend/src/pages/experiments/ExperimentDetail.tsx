import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, FlaskConical, TrendingUp, Clock, CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, Badge, Button, Skeleton } from '@/components/ui'
import { experimentsApi } from '@/api/endpoints'
import { cn, formatDate, formatRelativeTime } from '@/utils/helpers'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

const mockTrials = [
  { id: '1', experiment_id: '1', trial_number: 1, params: { lr: 0.01, max_depth: 6, n_estimators: 100 }, value: 0.9210, status: 'completed' },
  { id: '2', experiment_id: '1', trial_number: 2, params: { lr: 0.005, max_depth: 8, n_estimators: 200 }, value: 0.9345, status: 'completed' },
  { id: '3', experiment_id: '1', trial_number: 3, params: { lr: 0.001, max_depth: 10, n_estimators: 300 }, value: 0.9387, status: 'completed' },
  { id: '4', experiment_id: '1', trial_number: 4, params: { lr: 0.003, max_depth: 7, n_estimators: 150 }, value: 0.9298, status: 'completed' },
  { id: '5', experiment_id: '1', trial_number: 5, params: { lr: 0.02, max_depth: 5, n_estimators: 50 }, value: 0.9050, status: 'failed' },
  { id: '6', experiment_id: '1', trial_number: 6, params: { lr: 0.008, max_depth: 9, n_estimators: 250 }, value: 0.9421, status: 'running' },
]

const mockExperiment = {
  id: '1', name: 'hyperparam_search_xgb', description: 'Bayesian optimization for XGBoost',
  status: 'running', created_at: '2026-04-14T08:00:00Z', best_metric: 0.9421,
  metric_name: 'accuracy', best_trial_id: '6',
}

const chartData = mockTrials.filter(t => t.value).map(t => ({
  trial: `Trial ${t.trial_number}`,
  value: t.value ? (t.value * 100).toFixed(1) : 0,
}))

export function ExperimentDetail() {
  const { experimentId } = useParams<{ experimentId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'overview' | 'trials' | 'visualize'>('overview')

  const { data: experiment } = useQuery({
    queryKey: ['experiment', experimentId],
    queryFn: () => experimentsApi.getById(experimentId!),
    initialData: mockExperiment as any,
  })

  const { data: trialsData } = useQuery({
    queryKey: ['experiment', experimentId, 'trials'],
    fn: () => experimentsApi.listTrials(experimentId!),
    initialData: { items: mockTrials } as any,
  })

  const trials = trialsData?.items || mockTrials
  const bestTrial = trials.find(t => t.id === experiment?.best_trial_id)

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Back
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{experiment?.name}</h1>
            <Badge className={experiment?.status === 'running' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}>
              {experiment?.status}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">{experiment?.description}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-primary">{trials.length}</p>
            <p className="text-xs text-muted-foreground">Total Trials</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-green-600">
              {trials.filter(t => t.status === 'completed').length}
            </p>
            <p className="text-xs text-muted-foreground">Completed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-purple-600">
              {bestTrial ? `${(bestTrial.value * 100).toFixed(1)}%` : '--'}
            </p>
            <p className="text-xs text-muted-foreground">Best {experiment?.metric_name}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-amber-600">
              {trials.filter(t => t.status === 'running').length}
            </p>
            <p className="text-xs text-muted-foreground">Running</p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="border-b">
        <div className="flex gap-1">
          {(['overview', 'trials', 'visualize'] as const).map((tab) => (
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

      {activeTab === 'overview' && (
        <Card>
          <CardContent className="p-6">
            <h3 className="font-semibold mb-4">Trial Performance</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="trial" fontSize={12} />
                  <YAxis domain={[85, 100]} fontSize={12} tickFormatter={(v) => `${v}%`} />
                  <Tooltip formatter={(v: number) => [`${v}%`, 'Accuracy']} />
                  <Bar dataKey="value" fill="#8b5cf6" name="Accuracy" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'trials' && (
        <Card>
          <CardContent className="p-0">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Trial</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Status</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Accuracy</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">LR</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Max Depth</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Estimators</th>
                </tr>
              </thead>
              <tbody>
                {trials.map((trial) => (
                  <tr key={trial.id} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="py-3 px-4 font-mono text-sm">#{trial.trial_number}</td>
                    <td className="py-3 px-4">
                      <Badge className={
                        trial.status === 'completed' ? 'bg-green-100 text-green-700' :
                        trial.status === 'running' ? 'bg-blue-100 text-blue-700' :
                        'bg-red-100 text-red-700'
                      }>{trial.status}</Badge>
                    </td>
                    <td className="py-3 px-4 font-mono text-sm">
                      {trial.value ? `${(trial.value * 100).toFixed(1)}%` : '--'}
                    </td>
                    <td className="py-3 px-4 font-mono text-sm">{trial.params?.lr}</td>
                    <td className="py-3 px-4 font-mono text-sm">{trial.params?.max_depth}</td>
                    <td className="py-3 px-4 font-mono text-sm">{trial.params?.n_estimators}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {activeTab === 'visualize' && (
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-muted-foreground">Advanced visualizations (parallel coordinates, importance plots) coming soon.</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
