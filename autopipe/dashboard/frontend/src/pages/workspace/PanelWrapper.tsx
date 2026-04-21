import { Settings, X, GripVertical, Maximize, Minimize } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui'
import { useWorkspace, type PanelLayout } from './WorkspaceContext'

interface PanelWrapperProps {
  panel: PanelLayout
  children: React.ReactNode
  onConfigure?: () => void
  isLoading?: boolean
  error?: string | null
}

export function PanelWrapper({
  panel,
  children,
  onConfigure,
  isLoading,
  error,
}: PanelWrapperProps) {
  const { state, removePanel, updatePanel } = useWorkspace()
  const isEditing = state.isEditing

  const handleResize = () => {
    let nextCol = 6
    let nextRow = 2
    if (panel.colSpan === 6 && panel.rowSpan === 2) {
      nextCol = 12
      nextRow = 3
    } else if (panel.colSpan === 12) {
      nextCol = 6
      nextRow = 1
    }
    updatePanel(panel.id, { colSpan: nextCol, rowSpan: nextRow })
  }

  return (
    <Card
      className="relative h-full flex flex-col overflow-hidden transition-shadow hover:shadow-md"
      style={{
        gridColumn: `span ${panel.colSpan}`,
        gridRow: `span ${panel.rowSpan}`,
        minHeight: panel.rowSpan * 160,
      }}
    >
      {/* Panel header */}
      <CardHeader className="py-2 px-3 flex flex-row items-center justify-between border-b border-border/50 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          {isEditing && (
            <GripVertical className="w-4 h-4 text-muted-foreground cursor-grab shrink-0" />
          )}
          <CardTitle className="text-sm font-medium truncate">{panel.title}</CardTitle>
        </div>

        <div className="flex items-center gap-0.5 shrink-0">
          {isEditing ? (
            <>
              <button
                onClick={handleResize}
                className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                title="Resize"
              >
                {panel.colSpan === 12 ? (
                  <Minimize className="w-3.5 h-3.5" />
                ) : (
                  <Maximize className="w-3.5 h-3.5" />
                )}
              </button>
              {onConfigure && (
                <button
                  onClick={onConfigure}
                  className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                  title="Configure"
                >
                  <Settings className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={() => removePanel(panel.id)}
                className="p-1.5 rounded hover:bg-destructive/10 transition-colors text-muted-foreground hover:text-destructive"
                title="Remove"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </>
          ) : (
            onConfigure && (
              <button
                onClick={onConfigure}
                className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100"
                title="Configure"
              >
                <Settings className="w-3.5 h-3.5" />
              </button>
            )
          )}
        </div>
      </CardHeader>

      {/* Panel body */}
      <CardContent className="flex-1 p-3 min-h-0 flex flex-col relative group">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="animate-pulse space-y-2 w-full">
              <div className="h-3 bg-muted rounded w-3/4" />
              <div className="h-3 bg-muted rounded w-1/2" />
              <div className="h-3 bg-muted rounded w-5/6" />
            </div>
          </div>
        ) : error ? (
          <div className="flex-1 flex items-center justify-center text-sm text-destructive">
            {error}
          </div>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  )
}
