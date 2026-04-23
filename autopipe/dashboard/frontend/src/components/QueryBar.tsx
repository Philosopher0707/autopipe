import { Search, X } from 'lucide-react'
import { cn } from '@/utils/helpers'
import { Input, Button } from '@/components/ui'

export interface FilterConfig {
  key: string
  label: string
  type: 'text' | 'select'
  options?: string[]
}

export interface FilterValue {
  key: string
  value: string
}

interface QueryBarProps {
  filters: FilterConfig[]
  values: FilterValue[]
  onChange: (values: FilterValue[]) => void
  className?: string
}

export function QueryBar({ filters, values, onChange, className }: QueryBarProps) {
  const getValue = (key: string) => values.find((v) => v.key === key)?.value ?? ''

  const setValue = (key: string, value: string) => {
    const next = values.filter((v) => v.key !== key)
    if (value.trim()) {
      next.push({ key, value })
    }
    onChange(next)
  }

  const clearAll = () => onChange([])

  const hasFilters = values.some((v) => v.value.trim())

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      {filters.map((f) => (
        <div key={f.key} className="flex items-center gap-1">
          {f.type === 'select' && f.options ? (
            <select
              value={getValue(f.key)}
              onChange={(e) => setValue(f.key, e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            >
              <option value="">{f.label}</option>
              {f.options.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          ) : (
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <Input
                value={getValue(f.key)}
                onChange={(e) => setValue(f.key, e.target.value)}
                placeholder={f.label}
                className="pl-8 h-8 text-xs w-40"
              />
            </div>
          )}
        </div>
      ))}
      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={clearAll}>
          <X className="w-3.5 h-3.5 mr-1" />
          Clear
        </Button>
      )}
    </div>
  )
}
