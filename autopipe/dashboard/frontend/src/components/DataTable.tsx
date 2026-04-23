import { useState, useMemo } from 'react'
import { ArrowUpDown, SearchX } from 'lucide-react'
import { cn } from '@/utils/helpers'
import { Button } from '@/components/ui'

export interface Column<T> {
  key: string
  header: string
  accessor: (row: T) => React.ReactNode
  sortable?: boolean
  align?: 'left' | 'right' | 'center'
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  emptyMessage?: string
  emptyAction?: {
    label: string
    onClick: () => void
  }
  onRowClick?: (row: T) => void
  className?: string
}

export function DataTable<T>({
  columns,
  data,
  emptyMessage = 'No data available.',
  emptyAction,
  onRowClick,
  className,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const sorted = useMemo(() => {
    if (!sortKey) return data
    const col = columns.find((c) => c.key === sortKey)
    if (!col || !col.sortable) return data

    return [...data].sort((a, b) => {
      const av = String(col.accessor(a))
      const bv = String(col.accessor(b))
      const cmp = av.localeCompare(bv, undefined, { numeric: true })
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir, columns])

  const toggleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  if (data.length === 0) {
    return (
      <div className={cn('flex flex-col items-center justify-center py-12 text-muted-foreground', className)}>
        <SearchX className="w-8 h-8 mb-3 opacity-50" />
        <p className="text-sm">{emptyMessage}</p>
        {emptyAction && (
          <Button variant="outline" size="sm" className="mt-4" onClick={emptyAction.onClick}>
            {emptyAction.label}
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'pb-2 pr-4 font-medium whitespace-nowrap',
                  col.align === 'right' && 'text-right',
                  col.align === 'center' && 'text-center'
                )}
              >
                {col.sortable ? (
                  <button
                    onClick={() => toggleSort(col.key)}
                    className="flex items-center gap-1 hover:text-foreground transition-colors"
                  >
                    {col.header}
                    <ArrowUpDown className="w-3 h-3" />
                  </button>
                ) : (
                  col.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, ri) => (
            <tr
              key={ri}
              className={cn(
                'border-b transition-colors',
                onRowClick ? 'cursor-pointer hover:bg-muted/50' : 'hover:bg-muted/50'
              )}
              onClick={() => onRowClick?.(row)}
              role={onRowClick ? 'button' : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              onKeyDown={(e) => { if (onRowClick && (e.key === 'Enter' || e.key === ' ')) onRowClick(row) }}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn(
                    'py-2 pr-4',
                    col.align === 'right' && 'text-right tabular-nums',
                    col.align === 'center' && 'text-center'
                  )}
                >
                  {col.accessor(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
