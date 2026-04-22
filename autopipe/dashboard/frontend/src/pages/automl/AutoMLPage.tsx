import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
} from 'recharts'
import { Sparkles } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, Skeleton, Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'
import { automlApi } from '@/api/endpoints'

const STATE_COLORS: Record<string, string> = {
  COMPLETE: '#22c55e',
  PRUNED: '#f59e0b',
  FAIL: '#ef4444',
  RUNNING: '#3b82f6',
  PENDING: '#94a3b8',
}

export function AutoMLPage() {
  const experimentId = 'default'
  const [selectedTrial, setSelectedTrial] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState('trials')

  const { data: trialsData, isLoading: trialsLoading } = useQuery({
    queryKey: ['automl', 'trials', experimentId],
    queryFn: () => automlApi.listTrials({ experiment_id: experimentId }),
  })

  const { data: vizData, isLoading: vizLoading } = useQuery({
    queryKey: ['automl', 'visualizations', experimentId],
    queryFn: () => automlApi.getVisualizations(experimentId),
  })

  const { data: _historyData } = useQuery({
    queryKey: ['automl', 'trial-history', selectedTrial],
    queryFn: () => automlApi.getTrialHistory(selectedTrial!),
    enabled: selectedTrial !== null,
  })

  const trials = trialsData?.trials ?? []
  const paramImportance = vizData?.param_importance ?? []
  const paretoFront = vizData?.pareto_front ?? []
  const pruningHistory = vizData?.pruning_history ?? []

  const sortedParams = useMemo(
    () => [...paramImportance].sort((a, b) => b.importance - a.importance),
    [paramImportance],
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Sparkles className="w-6 h-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">AutoML</h1>
            <p className="text-sm text-muted-foreground">
              Optuna trial history, param importance, and Pareto front.
            </p>
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="trials">Trial History</TabsTrigger>
          <TabsTrigger value="importance">Param Importance</TabsTrigger>
          <TabsTrigger value="pareto">Pareto Front</TabsTrigger>
          <TabsTrigger value="pruning">Pruning</TabsTrigger>
        </TabsList>

        <TabsContent value="trials" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Trial History</CardTitle>
            </CardHeader>
            <CardContent>
              {trialsLoading ? (
                <Skeleton className="h-80 w-full" />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2 pr-4">#</th>
                        <th className="pb-2 pr-4">State</th>
                        <th className="pb-2 pr-4">Value</th>
                        <th className="pb-2 pr-4">Duration (s)</th>
                        <th className="pb-2">Params</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trials.map((t) => (
                        <tr
                          key={t.number}
                          className={`border-b cursor-pointer hover:bg-muted/50 ${
                            selectedTrial === t.number ? 'bg-muted' : ''
                          }`}
                          onClick={() => setSelectedTrial(t.number)}
                        >
                          <td className="py-2 pr-4">{t.number}</td>
                          <td className="py-2 pr-4">
                            <span
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium text-white"
                              style={{ background: STATE_COLORS[t.state] ?? '#94a3b8' }}
                            >
                              {t.state}
                            </span>
                          </td>
                          <td className="py-2 pr-4 font-mono">
                            {t.value?.toFixed(4) ?? '—'}
                          </td>
                          <td className="py-2 pr-4">
                            {t.duration_seconds?.toFixed(1) ?? '—'}
                          </td>
                          <td className="py-2 text-xs text-muted-foreground max-w-[300px] truncate">
                            {Object.entries(t.params)
                              .map(([k, v]) => `${k}=${typeof v === 'number' ? v.toFixed(3) : v}`)
                              .join(', ')}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="importance" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Parameter Importance</CardTitle>
            </CardHeader>
            <CardContent>
              {vizLoading ? (
                <Skeleton className="h-80 w-full" />
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={sortedParams} layout="vertical" margin={{ left: 80 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="param" width={80} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="importance" name="Importance" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pareto" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Pareto Front</CardTitle>
            </CardHeader>
            <CardContent>
              {vizLoading ? (
                <Skeleton className="h-80 w-full" />
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" dataKey="objective_1" name="Obj 1" />
                    <YAxis type="number" dataKey="objective_2" name="Obj 2" />
                    <Tooltip
                      cursor={{ strokeDasharray: '3 3' }}
                      formatter={(value: number, name: string) => [value.toFixed(4), name]}
                    />
                    <Scatter name="Trials" data={paretoFront} fill="#3b82f6">
                      {paretoFront.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={STATE_COLORS[trials[entry.trial_number]?.state ?? 'COMPLETE'] ?? '#3b82f6'}
                        />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pruning" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Pruning History</CardTitle>
            </CardHeader>
            <CardContent>
              {vizLoading ? (
                <Skeleton className="h-80 w-full" />
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={pruningHistory}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="step" />
                    <YAxis dataKey="intermediate_value" />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="intermediate_value"
                      stroke="#3b82f6"
                      dot={(props: any) => {
                        const pruned = props.payload?.pruned as boolean | undefined
                        return (
                          <circle
                            key={`dot-${props.payload?.trial_number}-${props.payload?.step}`}
                            cx={props.cx as number}
                            cy={props.cy as number}
                            r={4}
                            fill={pruned ? '#ef4444' : '#22c55e'}
                          />
                        )
                      }}
                      name="Intermediate Value"
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}