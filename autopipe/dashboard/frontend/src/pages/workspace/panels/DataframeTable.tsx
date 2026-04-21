import { useMemo, useState } from 'react'
import { ArrowUpDown, ArrowDown, ArrowUp } from 'lucide-react'
import { PanelWrapper } from '../PanelWrapper'
import type { PanelLayout } from '../WorkspaceContext'

interface DataframeTableProps {
  panel: PanelLayout
}

type RowData = Record<string, unknown>

export function DataframeTable({ panel }: DataframeTableProps) {
  // Accept either an array of rows from panel config, or placeholder
  const rows: RowData[] = useMemo(() => {
    const provided = panel.config.data as RowData[] | undefined
    if (provided && Array.isArray(provided)) return provided
    // Default placeholder data
    return [
      { id: 1, name: 'Alice', score: 0.92, approved: true },
      { id: 2, name: 'Bob', score: 0.78, approved: false },
      { id: 3, name: 'Charlie', score: 0.65, approved: false },
      { id: 4, name: 'Diana', score: 0.97, approved: true },
      { id: 5, name: 'Eve', score: 0.83, approved: true },
      { id: 6, name: 'Frank', score: 0.71, approved: false },
      { id: 7, name: 'Grace', score: 0.88, approved: true },
      { id: 8, name: 'Hank', score: 0.54, approved: false },
    ]
  }, [panel.config.data])

  const columns = useMemo(() => {
    if (rows.length === 0) return []
    return Object.keys(rows[0])
  }, [rows])

  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [search, setSearch] = useState('')

  const sorted = useMemo(() => {
    if (!sortKey) return rows
    return [...rows].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'asc' ? av - bv : bv - av
      return sortDir === 'asc'
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av))
    })
  }, [rows, sortKey, sortDir])

  const filtered = useMemo(() => {
    if (!search.trim()) return sorted
    const s = search.toLowerCase()
    return sorted.filter((row) =>
      Object.values(row).some((v) => String(v).toLowerCase().includes(s))
    )
  }, [sorted, search])

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const displayValue = (v: unknown) => {
    if (v == null) return '—'
    if (typeof v === 'boolean') return v ? '✓' : '✗'
    if (typeof v === 'number') return Number.isInteger(v) ? v : v.toFixed(3)
    return String(v).slice(0, 40)
  }

  return (
    <PanelWrapper panel={panel}>
      <div className="flex flex-col h-full gap-2">
        {rows.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">No data loaded.</div>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 text-xs px-2 py-1 rounded border border-border bg-background"
              />
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">{filtered.length} rows</span>
            </div>
            <div className="flex-1 overflow-auto border border-border rounded-md">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-muted z-10">
                  <tr>
                    {columns.map((col) => (
                      <th
                        key={col}
                        className="text-left px-2 py-1.5 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                        onClick={() => handleSort(col)}
                      >
                        <span className="inline-flex items-center gap-1">
                          {col}
                          {sortKey === col ? (
                            sortDir === 'asc' ? <ArrowUp className="w-3 h-3 text-primary" /> : <ArrowDown className="w-3 h-3 text-primary" />
                          ) : (
                            <ArrowUpDown className="w-3 h-3 text-muted-foreground/30" />
                          )}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row, i) => (
                    <tr key={i} className="border-b border-border/50 hover:bg-muted/20">
                      {columns.map((col) => (
                        <td key={col} className="px-2 py-1.5 text-muted-foreground">
                          {displayValue(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </PanelWrapper>
  )
}
