import { useState, useCallback, useRef, useEffect } from 'react'
import { Search, FileText, GitBranch, Play, Box } from 'lucide-react'
import { cn } from '@/utils/helpers'
import { Input } from '@/components/ui'

interface SearchResult {
  id: string
  label: string
  type: 'pipeline' | 'run' | 'model' | 'experiment'
}

interface GlobalSearchProps {
  placeholder?: string
  onResultSelect?: (id: string) => void
  className?: string
}

const ICON_MAP: Record<string, React.ReactNode> = {
  pipeline: <GitBranch className="w-4 h-4" />,
  run: <Play className="w-4 h-4" />,
  model: <Box className="w-4 h-4" />,
  experiment: <FileText className="w-4 h-4" />,
}

export function GlobalSearch({ placeholder = 'Search...', onResultSelect, className }: GlobalSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const debouncedSearch = useCallback((value: string) => {
    if (!value.trim()) {
      setResults([])
      return
    }
    // Mock search results
    setResults([
      { id: '1', label: `${value} pipeline`, type: 'pipeline' },
      { id: '2', label: `${value} run #42`, type: 'run' },
      { id: '3', label: `${value} model v3`, type: 'model' },
    ])
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => debouncedSearch(query), 200)
    return () => clearTimeout(timer)
  }, [query, debouncedSearch])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (id: string) => {
    onResultSelect?.(id)
    setOpen(false)
    setQuery('')
    setResults([])
  }

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="pl-9 w-64"
        />
      </div>
      {open && results.length > 0 && (
        <div className="absolute top-full mt-1 left-0 right-0 bg-popover border border-border rounded-md shadow-md z-50 overflow-hidden">
          {results.map((r) => (
            <button
              key={r.id}
              onClick={() => handleSelect(r.id)}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              <span className="text-muted-foreground">{ICON_MAP[r.type]}</span>
              <span>{r.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
