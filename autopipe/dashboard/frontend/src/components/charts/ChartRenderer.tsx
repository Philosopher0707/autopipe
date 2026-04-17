import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import type { ChartArtifact } from '@/api/endpoints/charts'

const PALETTE = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#84cc16']

const tooltipStyle = { backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }

interface ChartProps {
  artifact: ChartArtifact
}

function getPoints(a: ChartArtifact) {
  return (a.data.points ?? []) as Record<string, unknown>[]
}

function getXKey(a: ChartArtifact) {
  return (a.data.x_key ?? 'name') as string
}

function getSeries(a: ChartArtifact) {
  return (a.data.series ?? []) as string[]
}

function getColors(a: ChartArtifact) {
  return (a.config?.colors ?? {}) as Record<string, string>
}

function getColor(series: string, idx: number, artifact: ChartArtifact) {
  const custom = getColors(artifact)
  return custom[series] ?? PALETTE[idx % PALETTE.length]
}

function RenderLine({ artifact }: ChartProps) {
  const points = getPoints(artifact)
  const xKey = getXKey(artifact)
  const series = getSeries(artifact)
  const domain = artifact.config?.domain as number[] | undefined

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={points}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey={xKey} fontSize={12} />
        <YAxis fontSize={12} domain={domain ?? ['auto', 'auto']} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend />
        {series.map((s, i) => (
          <Line key={s} type="monotone" dataKey={s} stroke={getColor(s, i, artifact)} strokeWidth={2} dot={{ r: 3 }} name={s} />
        ))}
        {artifact.config?.threshold && (
          <ReferenceLine
            y={(artifact.config.threshold as Record<string, unknown>).value as number}
            stroke="#ef4444" strokeDasharray="3 3"
            label={{ value: (artifact.config.threshold as Record<string, unknown>).label as string || 'Threshold', fill: '#ef4444', fontSize: 11 }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  )
}

function RenderBar({ artifact }: ChartProps) {
  const points = getPoints(artifact)
  const xKey = getXKey(artifact)
  const series = getSeries(artifact)
  const layout = (artifact.config?.layout as string) || 'horizontal'

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={points} layout={layout === 'vertical' ? 'vertical' : undefined}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        {layout === 'vertical' ? (
          <>
            <XAxis type="number" fontSize={12} />
            <YAxis dataKey={xKey} type="category" width={120} fontSize={12} />
          </>
        ) : (
          <>
            <XAxis dataKey={xKey} fontSize={12} />
            <YAxis fontSize={12} />
          </>
        )}
        <Tooltip contentStyle={tooltipStyle} />
        <Legend />
        {series.map((s, i) => (
          <Bar key={s} dataKey={s} fill={getColor(s, i, artifact)} name={s} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

function RenderScatter({ artifact }: ChartProps) {
  const points = getPoints(artifact)
  const xKey = getXKey(artifact)
  const series = getSeries(artifact)

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey={xKey} type="number" fontSize={12} name={artifact.config?.x_label as string || xKey} />
        <YAxis type="number" fontSize={12} name={artifact.config?.y_label as string || series[0]} />
        <Tooltip contentStyle={tooltipStyle} />
        {series.map((s, i) => (
          <Scatter key={s} name={s} data={points} fill={getColor(s, i, artifact)} />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  )
}

function RenderArea({ artifact }: ChartProps) {
  const points = getPoints(artifact)
  const xKey = getXKey(artifact)
  const series = getSeries(artifact)

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={points}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey={xKey} fontSize={12} />
        <YAxis fontSize={12} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend />
        {series.map((s, i) => (
          <Area key={s} type="monotone" dataKey={s} stroke={getColor(s, i, artifact)} fill={getColor(s, i, artifact)} fillOpacity={0.3} name={s} />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}

function RenderPie({ artifact }: ChartProps) {
  const points = getPoints(artifact)
  const xKey = getXKey(artifact)
  const series = getSeries(artifact)

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={points} dataKey={series[0]} nameKey={xKey} cx="50%" cy="50%" outerRadius="80%">
          {points.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  )
}

function RenderHeatmap({ artifact }: ChartProps) {
  const rows = (artifact.data.rows ?? []) as string[]
  const columns = (artifact.data.columns ?? []) as string[]
  const values = (artifact.data.values ?? []) as number[][]

  return (
    <div className="overflow-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="p-2" />
            {columns.map((c) => <th key={c} className="p-2 text-center">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={row}>
              <td className="p-2 font-medium">{row}</td>
              {columns.map((col, ci) => {
                const val = values[ri]?.[ci] ?? 0
                const max = Math.max(...values.flat(), 1)
                const intensity = val / max
                return (
                  <td key={col} className="p-2 text-center" style={{ backgroundColor: `rgba(59, 130, 246, ${intensity * 0.7 + 0.05})`, color: intensity > 0.5 ? '#fff' : '#000' }}>
                    {val}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const RENDERERS: Record<string, React.FC<ChartProps>> = {
  line: RenderLine,
  bar: RenderBar,
  scatter: RenderScatter,
  area: RenderArea,
  pie: RenderPie,
  heatmap: RenderHeatmap,
}

export function ChartRenderer({ artifact }: ChartProps) {
  const Renderer = RENDERERS[artifact.chart_type]
  if (!Renderer) {
    return <div className="text-sm text-muted-foreground">Unsupported chart type: {artifact.chart_type}</div>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{artifact.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={artifact.chart_type === 'heatmap' ? undefined : 'h-64'}>
          <Renderer artifact={artifact} />
        </div>
      </CardContent>
    </Card>
  )
}

export function ChartArtifactList({ artifacts }: { artifacts: ChartArtifact[] }) {
  if (artifacts.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No charts generated for this run yet.
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {artifacts.map((a) => (
        <ChartRenderer key={a.id} artifact={a} />
      ))}
    </div>
  )
}