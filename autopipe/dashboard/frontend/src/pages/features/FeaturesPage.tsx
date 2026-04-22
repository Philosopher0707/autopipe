import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { Plus, Trash2, GripVertical, Wrench } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, Skeleton, Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'
import { featuresApi } from '@/api/endpoints'
import type { TransformStep, FeatureStats } from '@/types'

const STEP_TYPES = ['imputer', 'scaler', 'encoder', 'selector', 'pca', 'custom'] as const

function TransformBuilder({
  steps,
  onAdd,
  onRemove,
  onToggle,
}: {
  steps: TransformStep[]
  onAdd: (type: string) => void
  onRemove: (index: number) => void
  onToggle: (index: number) => void
}) {
  return (
    <div className="space-y-2">
      {steps.map((step, i) => (
        <div
          key={i}
          className={`flex items-center gap-2 p-3 rounded-lg border ${
            step.enabled ? 'bg-background border-border' : 'bg-muted/50 border-muted opacity-60'
          }`}
        >
          <GripVertical className="w-4 h-4 text-muted-foreground" />
          <span className="font-medium text-sm flex-1">{step.name}</span>
          <span className="text-xs text-muted-foreground px-2 py-0.5 bg-muted rounded">
            {step.type}
          </span>
          <button
            onClick={() => onToggle(i)}
            className={`px-2 py-1 rounded text-xs font-medium ${
              step.enabled
                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
            }`}
          >
            {step.enabled ? 'On' : 'Off'}
          </button>
          <button onClick={() => onRemove(i)} className="text-red-500 hover:text-red-700">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      <div className="flex gap-2 pt-2">
        {STEP_TYPES.map((type) => (
          <button
            key={type}
            onClick={() => onAdd(type)}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md border border-dashed border-border hover:bg-muted transition-colors"
          >
            <Plus className="w-3 h-3" />
            {type}
          </button>
        ))}
      </div>
    </div>
  )
}

function StatsTable({ stats, title }: { stats: FeatureStats[]; title: string }) {
  return (
    <div>
      <h3 className="text-sm font-medium mb-2">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 pr-4">Feature</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4">Nulls</th>
              <th className="pb-2 pr-4">Mean</th>
              <th className="pb-2 pr-4">Std</th>
              <th className="pb-2 pr-4">Min</th>
              <th className="pb-2 pr-4">Max</th>
              <th className="pb-2">Unique</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((s) => (
              <tr key={s.name} className="border-b hover:bg-muted/50">
                <td className="py-1.5 pr-4 font-mono text-xs">{s.name}</td>
                <td className="py-1.5 pr-4 text-xs text-muted-foreground">{s.dtype}</td>
                <td className="py-1.5 pr-4">{s.nulls}</td>
                <td className="py-1.5 pr-4">{s.mean?.toFixed(2) ?? '—'}</td>
                <td className="py-1.5 pr-4">{s.std?.toFixed(2) ?? '—'}</td>
                <td className="py-1.5 pr-4">{s.min?.toFixed(2) ?? '—'}</td>
                <td className="py-1.5 pr-4">{s.max?.toFixed(2) ?? '—'}</td>
                <td className="py-1.5">{s.unique ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function FeaturesPage() {
  const pipelineId = 'default-pipeline'
  const [activeTab, setActiveTab] = useState('builder')
  const [steps, setSteps] = useState<TransformStep[]>([
    { name: 'impute_median', type: 'imputer', params: { strategy: 'median' }, enabled: true },
    { name: 'scale_standard', type: 'scaler', params: { method: 'standard' }, enabled: true },
  ])

  const { data: preview, isLoading: previewLoading } = useQuery({
    queryKey: ['features', 'preview', pipelineId],
    queryFn: () => featuresApi.preview(pipelineId),
  })

  const beforeStats = preview?.before ?? []
  const afterStats = preview?.after ?? []

  const histogramData = useMemo(() => {
    return beforeStats.map((s) => ({
      name: s.name,
      mean: s.mean ?? 0,
      std: s.std ?? 0,
    }))
  }, [beforeStats])

  const addStep = (type: string) => {
    setSteps((prev) => [
      ...prev,
      { name: `${type}_${prev.length + 1}`, type, params: {}, enabled: true },
    ])
  }

  const removeStep = (index: number) => {
    setSteps((prev) => prev.filter((_, i) => i !== index))
  }

  const toggleStep = (index: number) => {
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, enabled: !s.enabled } : s)),
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wrench className="w-6 h-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Feature Engineering</h1>
            <p className="text-sm text-muted-foreground">
              Build transform pipelines and inspect feature statistics.
            </p>
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="builder">Pipeline Builder</TabsTrigger>
          <TabsTrigger value="stats">Feature Stats</TabsTrigger>
          <TabsTrigger value="histogram">Distribution</TabsTrigger>
        </TabsList>

        <TabsContent value="builder" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Transform Pipeline</CardTitle>
            </CardHeader>
            <CardContent>
              <TransformBuilder
                steps={steps}
                onAdd={addStep}
                onRemove={removeStep}
                onToggle={toggleStep}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="stats" className="pt-4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Feature Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {previewLoading ? (
                <Skeleton className="h-60 w-full" />
              ) : (
                <>
                  <StatsTable stats={beforeStats} title="Before Transform" />
                  <StatsTable stats={afterStats} title="After Transform" />
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="histogram" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Feature Distribution (Mean ± Std)</CardTitle>
            </CardHeader>
            <CardContent>
              {previewLoading ? (
                <Skeleton className="h-80 w-full" />
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={histogramData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-30} textAnchor="end" height={60} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="mean" name="Mean" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="std" name="Std Dev" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}