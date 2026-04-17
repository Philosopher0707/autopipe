import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Box, ArrowRight, CheckCircle2, Clock, Archive,
  TrendingUp, Trash2, Download, ChevronDown, ChevronUp
} from 'lucide-react'
import {
  Card, CardContent, CardHeader, CardTitle, Badge, Button, Skeleton
} from '@/components/ui'
import { modelsApi } from '@/api/endpoints'
import { cn, formatDate, formatRelativeTime } from '@/utils/helpers'

const mockVersions = [
  { id: 'v5', model_id: '1', version: 5, stage: 'production', metrics: { accuracy: 0.9421, f1: 0.9245, auc: 0.9788 }, created_at: '2026-04-10T10:00:00Z', description: 'Best production version' },
  { id: 'v4', model_id: '1', version: 4, stage: 'staging', metrics: { accuracy: 0.9387, f1: 0.9190, auc: 0.9712 }, created_at: '2026-03-28T10:00:00Z', description: 'A/B testing candidate' },
  { id: 'v3', model_id: '1', version: 3, stage: 'archived', metrics: { accuracy: 0.9312, f1: 0.9105, auc: 0.9650 }, created_at: '2026-03-01T10:00:00Z', description: 'Retired version' },
  { id: 'v2', model_id: '1', version: 2, stage: 'archived', metrics: { accuracy: 0.9250, f1: 0.9020, auc: 0.9580 }, created_at: '2026-02-15T10:00:00Z', description: 'Early staging' },
  { id: 'v1', model_id: '1', version: 1, stage: 'archived', metrics: { accuracy: 0.9100, f1: 0.8900, auc: 0.9400 }, created_at: '2026-01-15T10:00:00Z', description: 'Initial version' },
]

const mockModel = {
  id: '1', name: 'customer_churn_model', description: 'XGBoost churn prediction model',
  framework: 'xgboost', task_type: 'classification', current_stage: 'production',
  created_at: '2026-01-15T10:00:00Z', tags: ['production', 'stable'],
}

const STAGE_COLORS: Record<string, string> = {
  production: 'bg-green-100 text-green-700',
  staging: 'bg-blue-100 text-blue-700',
  pending: 'bg-amber-100 text-amber-700',
  archived: 'bg-gray-100 text-gray-600',
}

export function ModelDetail() {
  const { modelId } = useParams<{ modelId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedVersions, setSelectedVersions] = useState<number[]>([])

  const { data: model } = useQuery({
    queryKey: ['model', modelId],
    queryFn: () => modelsApi.getById(modelId!),
    initialData: mockModel as any,
  })

  const promoteMutation = useMutation({
    mutationFn: ({ version, stage }: { version: number; stage: string }) =>
      modelsApi.updateVersionStage(modelId!, version, { stage }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['model', modelId] }),
  })

  const toggleVersion = (version: number) => {
    setSelectedVersions(prev =>
      prev.includes(version) ? prev.filter(v => v !== version) : [...prev, version]
    )
  }

  const bestVersion = mockVersions[0]

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Back
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{model?.name}</h1>
            <Badge className={STAGE_COLORS[model?.current_stage || 'pending']}>
              {model?.current_stage}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">{model?.description}</p>
          <div className="flex gap-2 mt-2">
            <Badge variant="outline">{model?.framework}</Badge>
            <Badge variant="outline">{model?.task_type}</Badge>
            {model?.tags?.map(tag => <Badge key={tag} variant="secondary">{tag}</Badge>)}
          </div>
        </div>
      </div>

      {/* Best Version Metrics */}
      {bestVersion && (
        <Card>
          <CardHeader>
            <CardTitle>Production Version (v{bestVersion.version})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
              {Object.entries(bestVersion.metrics).map(([key, value]) => (
                <div key={key} className="text-center">
                  <p className="text-2xl font-bold text-primary">
                    {typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : value}
                  </p>
                  <p className="text-xs text-muted-foreground uppercase">{key}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Version History */}
      <Card>
        <CardHeader>
          <CardTitle>Version History</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Version</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Stage</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Accuracy</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">F1</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">AUC</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Created</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {mockVersions.map((v) => (
                <tr key={v.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selectedVersions.includes(v.version)}
                        onChange={() => toggleVersion(v.version)}
                        className="rounded"
                      />
                      <span className="font-mono font-medium">v{v.version}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <Badge className={STAGE_COLORS[v.stage]}>{v.stage}</Badge>
                  </td>
                  <td className="py-3 px-4 font-mono text-sm">{(v.metrics.accuracy * 100).toFixed(1)}%</td>
                  <td className="py-3 px-4 font-mono text-sm">{(v.metrics.f1 * 100).toFixed(1)}%</td>
                  <td className="py-3 px-4 font-mono text-sm">{(v.metrics.auc * 100).toFixed(1)}%</td>
                  <td className="py-3 px-4 text-sm text-muted-foreground">{formatRelativeTime(v.created_at)}</td>
                  <td className="py-3 px-4">
                    <div className="flex gap-1">
                      {v.stage === 'production' && (
                        <Button variant="ghost" size="sm">
                          <TrendingUp className="w-4 h-4" />
                        </Button>
                      )}
                      {v.stage !== 'archived' && (
                        <Button variant="ghost" size="sm" title="Download">
                          <Download className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Compare Button */}
      {selectedVersions.length === 2 && (
        <div className="flex items-center gap-4 p-4 bg-muted rounded-lg">
          <span className="text-sm">
            Selected v{selectedVersions[0]} and v{selectedVersions[1]} — ready to compare
          </span>
          <Button size="sm">Compare Versions</Button>
        </div>
      )}
    </div>
  )
}
