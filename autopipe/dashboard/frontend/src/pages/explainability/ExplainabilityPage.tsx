import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  Cell,
  Legend,
  ReferenceLine,
} from 'recharts'
import { Brain } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, Skeleton, Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'
import { runsApi, chartsApi } from '@/api/endpoints'

const SHAP_COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6']
const LIME_POS = '#22c55e'
const LIME_NEG = '#ef4444'

export function ExplainabilityPage() {
  const [selectedRunId, setSelectedRunId] = useState('')
  const [activeTab, setActiveTab] = useState('shap')

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['runs'],
    queryFn: () => runsApi.list({ page_size: 50 }),
  })

  const runs = runsData?.items ?? []
  const runId = selectedRunId || runs[0]?.id

  const { data: explData, isLoading: explLoading } = useQuery({
    queryKey: ['charts', 'explainability', runId],
    queryFn: () => chartsApi.getExplainability(runId!),
    enabled: !!runId,
  })

  const shap = explData?.shap_values ?? []
  const lime = explData?.lime_explanation ?? []
  const perm = explData?.permutation_importance ?? []

  const shapChartData = useMemo(() => {
    return shap.map((s, i) => ({
      x: s.value,
      y: i,
      z: Math.abs(s.impact) * 300 + 50,
      feature: s.feature,
      impact: s.impact,
      color: SHAP_COLORS[i % SHAP_COLORS.length],
    }))
  }, [shap])

  const limeChartData = useMemo(() => {
    return [...lime].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))
  }, [lime])

  const permChartData = useMemo(() => {
    return [...perm].sort((a, b) => b.importance - a.importance)
  }, [perm])

  const isLoading = runsLoading || explLoading

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="w-6 h-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Explainability</h1>
            <p className="text-sm text-muted-foreground">SHAP, LIME, and permutation importance.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Run</label>
          <select
            className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
            value={selectedRunId}
            onChange={(e) => setSelectedRunId(e.target.value)}
          >
            <option value="">Latest</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                #{r.run_number} {r.pipeline_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="shap">SHAP</TabsTrigger>
          <TabsTrigger value="lime">LIME</TabsTrigger>
          <TabsTrigger value="permutation">Permutation</TabsTrigger>
        </TabsList>

        <TabsContent value="shap" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>SHAP Summary (Beeswarm)</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-80 w-full" />
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" dataKey="x" name="Value" />
                    <YAxis type="number" dataKey="y" name="Feature" tick={false} />
                    <ZAxis type="number" dataKey="z" range={[60, 400]} />
                    <Tooltip
                      cursor={{ strokeDasharray: '3 3' }}
                      formatter={(value: number, name: string, props: any) => {
                        if (name === 'x') return [value.toFixed(3), 'Value']
                        if (name === 'z') return [props.payload.impact.toFixed(3), 'Impact']
                        return [value, name]
                      }}
                      labelFormatter={(_: any, payload: any[]) => payload?.[0]?.payload?.feature ?? ''}
                    />
                    <ReferenceLine x={shap[0]?.base_value ?? 0} stroke="#888" strokeDasharray="4 4" />
                    <Scatter name="SHAP" data={shapChartData}>
                      {shapChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              )}
              <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                {SHAP_COLORS.map((c, i) => (
                  <span key={c} className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded-full inline-block" style={{ background: c }} />
                    {shap[i]?.feature ?? `F${i}`}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="lime" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>LIME Force Plot</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-80 w-full" />
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={limeChartData} layout="vertical" margin={{ left: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="feature" width={100} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="weight" name="Weight" radius={[4, 4, 4, 4]}>
                      {limeChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.weight >= 0 ? LIME_POS : LIME_NEG} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="permutation" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Permutation Importance</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-80 w-full" />
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={permChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="feature" tick={{ fontSize: 12 }} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="importance" name="Importance" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="std" name="Std" fill="#94a3b8" radius={[4, 4, 0, 0]} />
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
