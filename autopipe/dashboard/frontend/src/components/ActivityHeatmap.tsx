import { cn } from '@/utils/helpers'

interface HeatmapPoint {
  date: string
  count: number
}

interface ActivityHeatmapProps {
  data: HeatmapPoint[]
  className?: string
}

function getIntensityClass(count: number): string {
  if (count === 0) return 'bg-muted'
  if (count <= 2) return 'bg-primary/20'
  if (count <= 5) return 'bg-primary/40'
  if (count <= 8) return 'bg-primary/60'
  return 'bg-primary'
}

function getWeeks(data: HeatmapPoint[]): HeatmapPoint[][] {
  // Sort by date and bucket into weeks (7 days per column)
  const sorted = [...data].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  const weeks: HeatmapPoint[][] = []
  for (let i = 0; i < sorted.length; i += 7) {
    weeks.push(sorted.slice(i, i + 7))
  }
  return weeks
}

export function ActivityHeatmap({ data, className }: ActivityHeatmapProps) {
  const weeks = getWeeks(data)

  return (
    <div className={cn('overflow-x-auto', className)}>
      <div className="inline-flex gap-1">
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-1">
            {week.map((day, di) => (
              <div
                key={di}
                title={`${day.date}: ${day.count} events`}
                className={cn(
                  'w-3 h-3 rounded-sm',
                  getIntensityClass(day.count)
                )}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
