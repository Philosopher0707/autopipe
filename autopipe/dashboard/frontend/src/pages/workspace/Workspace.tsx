import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  LayoutGrid,
  Plus,
  RotateCcw,
  Check,
  ChevronDown,
  Activity,
  LineChart,
  BarChart3,
  ScatterChart,
  Table2,
  Trophy,
  GitCompare,
  GitBranch,
  Image,
  Table,
  FileText,
} from 'lucide-react'
import { CardTitle, Skeleton, StatusPill } from '@/components/ui'
import { useQuery } from '@tanstack/react-query'
import { runsApi, projectsApi } from '@/api/endpoints'
import { WorkspaceProvider, useWorkspace, type PanelType } from './WorkspaceContext'
import { PanelWrapper } from './PanelWrapper'
import {
  LinePlotPanel,
  BarChartPanel,
  ScatterPlotPanel,
  MetricSummaryPanel,
  ParamImportancePanel,
  RunTablePanel,
  RunComparisonPanel,
  HistogramPanel,
  ConfusionMatrixPanel,
  ParallelCoordsPanel,
  MediaViewer,
  DataframeTable,
  TextLogPanel,
} from './panels'
import type { PanelLayout } from './WorkspaceContext'

const PANEL_ICONS: Record<PanelType, React.ReactNode> = {
  'line-plot': <LineChart className="w-4 h-4" />,
  'scatter-plot': <ScatterChart className="w-4 h-4" />,
  'bar-chart': <BarChart3 className="w-4 h-4" />,
  'param-importance': <Table2 className="w-4 h-4" />,
  'metric-summary': <Trophy className="w-4 h-4" />,
  'confusion-matrix': <Activity className="w-4 h-4" />,
  'run-table': <Table2 className="w-4 h-4" />,
  'run-comparison': <GitCompare className="w-4 h-4" />,
  'histogram': <BarChart3 className="w-4 h-4" />,
  'parallel-coords': <GitBranch className="w-4 h-4" />,
  'media-viewer': <Image className="w-4 h-4" />,
  'dataframe-table': <Table className="w-4 h-4" />,
  'text-log': <FileText className="w-4 h-4" />,
}

const PANEL_LABELS: Record<PanelType, string> = {
  'line-plot': 'Line Plot',
  'scatter-plot': 'Scatter Plot',
  'bar-chart': 'Bar Chart',
  'param-importance': 'Parameters',
  'metric-summary': 'Metric Cards',
  'confusion-matrix': 'Confusion Matrix',
  'run-table': 'Runs Table',
  'run-comparison': 'Run Comparison',
  'histogram': 'Histogram',
  'parallel-coords': 'Parallel Coords',
  'media-viewer': 'Media Viewer',
  'dataframe-table': 'Dataframe Table',
  'text-log': 'Text Log',
}

function PanelRenderer({ panel }: { panel: PanelLayout }) {
  switch (panel.type) {
    case 'line-plot':
      return <LinePlotPanel panel={panel} />
    case 'bar-chart':
      return <BarChartPanel panel={panel} />
    case 'scatter-plot':
      return <ScatterPlotPanel panel={panel} />
    case 'metric-summary':
      return <MetricSummaryPanel panel={panel} />
    case 'param-importance':
      return <ParamImportancePanel panel={panel} />
    case 'run-table':
      return <RunTablePanel panel={panel} />
    case 'run-comparison':
      return <RunComparisonPanel panel={panel} />
    case 'histogram':
      return <HistogramPanel panel={panel} />
    case 'parallel-coords':
      return <ParallelCoordsPanel panel={panel} />
    case 'confusion-matrix':
      return <ConfusionMatrixPanel panel={panel} />
    case 'media-viewer':
      return <MediaViewer panel={panel} />
    case 'dataframe-table':
      return <DataframeTable panel={panel} />
    case 'text-log':
      return <TextLogPanel panel={panel} />
    default:
      return (
        <PanelWrapper panel={panel}>
          <div className="flex items-center justify-center text-sm text-muted-foreground">
            Panel type "{panel.type}" not yet implemented.
          </div>
        </PanelWrapper>
      )
  }
}

function WorkspaceToolbar() {
  const { state, dispatch, addPanel, resetLayout } = useWorkspace()
  const [showAddMenu, setShowAddMenu] = useState(false)
  const [showRunPicker, setShowRunPicker] = useState(false)
  const [showProjectPicker, setShowProjectPicker] = useState(false)

  const { data: projectsData } = useQuery({
    queryKey: ['projects', 'list'],
    queryFn: () => projectsApi.list({ limit: 100 }),
  })

  const { data: runsData, isLoading } = useQuery({
    queryKey: ['runs', 'list', { page_size: 50, project_id: state.selectedProjectId }],
    queryFn: () => runsApi.list({ page_size: 50, project_id: state.selectedProjectId }),
  })

  const runs = runsData?.items ?? []

  // Auto-select all runs when project changes and runs load
  useEffect(() => {
    if (state.selectedProjectId && runs.length > 0 && state.selectedRunIds.length === 0) {
      const all = runs.map((r) => r.id)
      dispatch({ type: 'SET_SELECTED_RUNS', runIds: all })
      state.panels.forEach((p) => {
        dispatch({
          type: 'UPDATE_PANEL',
          id: p.id,
          partial: { config: { ...p.config, runIds: all } },
        })
      })
    }
  }, [state.selectedProjectId, runs])

  const toggleRun = (runId: string) => {
    const current = new Set(state.selectedRunIds)
    if (current.has(runId)) {
      current.delete(runId)
    } else {
      current.add(runId)
    }
    dispatch({ type: 'SET_SELECTED_RUNS', runIds: Array.from(current) })

    // Also update all panels with the new runIds
    state.panels.forEach((p) => {
      dispatch({
        type: 'UPDATE_PANEL',
        id: p.id,
        partial: { config: { ...p.config, runIds: Array.from(current) } },
      })
    })
  }

  const selectAllRuns = () => {
    const all = runs.map((r) => r.id)
    dispatch({ type: 'SET_SELECTED_RUNS', runIds: all })
    state.panels.forEach((p) => {
      dispatch({
        type: 'UPDATE_PANEL',
        id: p.id,
        partial: { config: { ...p.config, runIds: all } },
      })
    })
  }

  const clearRuns = () => {
    dispatch({ type: 'SET_SELECTED_RUNS', runIds: [] })
    state.panels.forEach((p) => {
      dispatch({
        type: 'UPDATE_PANEL',
        id: p.id,
        partial: { config: { ...p.config, runIds: [] } },
      })
    })
  }

  const panelTypes: PanelType[] = [
    'line-plot',
    'bar-chart',
    'scatter-plot',
    'metric-summary',
    'param-importance',
    'confusion-matrix',
    'run-table',
    'run-comparison',
    'histogram',
    'parallel-coords',
    'media-viewer',
    'dataframe-table',
    'text-log',
  ]

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div className="flex items-center gap-3">
        <LayoutGrid className="w-5 h-5 text-primary" />
        <div>
          <CardTitle className="text-lg">Workspace</CardTitle>
          <p className="text-xs text-muted-foreground">
            {state.selectedRunIds.length > 0
              ? `${state.selectedRunIds.length} run${state.selectedRunIds.length > 1 ? 's' : ''} selected`
              : 'Select runs to visualize'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {/* Project Picker */}
        <div className="relative">
          <button
            onClick={() => setShowProjectPicker(!showProjectPicker)}
            className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border transition-colors ${
              state.selectedProjectId
                ? 'bg-primary/10 text-primary border-primary/20'
                : 'border-border hover:bg-muted'
            }`}
          >
            <GitBranch className="w-3.5 h-3.5" />
            {state.selectedProjectId
              ? projectsData?.items?.find((p) => p.id === state.selectedProjectId)?.name ?? 'Project'
              : 'All Projects'}
            <ChevronDown className="w-3 h-3" />
          </button>

          {showProjectPicker && (
            <div className="absolute top-full left-0 mt-1 z-50 w-64 bg-popover border border-border rounded-lg shadow-lg p-2 space-y-1">
              <div className="flex items-center justify-between px-2">
                <span className="text-xs font-medium">Select Project</span>
                {state.selectedProjectId && (
                  <button
                    onClick={() => {
                      dispatch({ type: 'SET_SELECTED_PROJECT', projectId: undefined })
                      setShowProjectPicker(false)
                    }}
                    className="text-[10px] text-muted-foreground hover:text-foreground hover:underline"
                  >
                    Clear
                  </button>
                )}
              </div>
              <div className="max-h-48 overflow-y-auto space-y-0.5">
                <button
                  onClick={() => {
                    dispatch({ type: 'SET_SELECTED_PROJECT', projectId: undefined })
                    setShowProjectPicker(false)
                  }}
                  className={`flex items-center gap-2 w-full text-left text-xs px-2 py-1.5 rounded transition-colors ${
                    !state.selectedProjectId ? 'bg-primary/10 text-primary font-medium' : 'hover:bg-muted'
                  }`}
                >
                  <span className="flex-1">All Projects</span>
                </button>
                {projectsData?.items?.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => {
                      dispatch({ type: 'SET_SELECTED_PROJECT', projectId: project.id })
                      setShowProjectPicker(false)
                    }}
                    className={`flex items-center gap-2 w-full text-left text-xs px-2 py-1.5 rounded transition-colors ${
                      state.selectedProjectId === project.id
                        ? 'bg-primary/10 text-primary font-medium'
                        : 'hover:bg-muted'
                    }`}
                  >
                    <span className="flex-1 truncate">{project.name}</span>
                    <StatusPill status={project.status} />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Run Picker */}
        <div className="relative">
          <button
            onClick={() => setShowRunPicker(!showRunPicker)}
            className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border transition-colors ${
              state.selectedRunIds.length > 0
                ? 'bg-primary/10 text-primary border-primary/20'
                : 'border-border hover:bg-muted'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            Runs {state.selectedRunIds.length > 0 && `(${state.selectedRunIds.length})`}
            <ChevronDown className="w-3 h-3" />
          </button>

          {showRunPicker && (
            <div className="absolute top-full left-0 mt-1 z-50 w-72 bg-popover border border-border rounded-lg shadow-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium">Select Runs</span>
                <div className="flex gap-1">
                  <button onClick={selectAllRuns} className="text-[10px] text-primary hover:underline">
                    All
                  </button>
                  <span className="text-[10px] text-muted-foreground">|</span>
                  <button onClick={clearRuns} className="text-[10px] text-muted-foreground hover:underline">
                    Clear
                  </button>
                </div>
              </div>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {isLoading ? (
                  <div className="py-2 space-y-1">
                    {[1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-6 w-full" />
                    ))}
                  </div>
                ) : runs.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-2">No runs found.</p>
                ) : (
                  runs.map((run) => (
                    <label
                      key={run.id}
                      className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer text-xs"
                    >
                      <input
                        type="checkbox"
                        checked={state.selectedRunIds.includes(run.id)}
                        onChange={() => {
                          toggleRun(run.id)
                        }}
                        className="rounded border-border"
                      />
                      <span className="flex-1 truncate">Run #{run.run_number} — {run.status}</span>
                      {run.metrics && Object.keys(run.metrics).length > 0 && (
                        <span className="text-[10px] text-muted-foreground">
                          {Object.keys(run.metrics).length} metrics
                        </span>
                      )}
                    </label>
                  ))
                )}
              </div>
              <button
                onClick={() => setShowRunPicker(false)}
                className="w-full text-center text-xs text-primary hover:underline py-1"
              >
                Done
              </button>
            </div>
          )}
        </div>

        {/* Edit/View Toggle */}
        <button
          onClick={() => dispatch({ type: 'TOGGLE_EDIT' })}
          className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border transition-colors ${
            state.isEditing
              ? 'bg-primary text-primary-foreground border-primary'
              : 'border-border hover:bg-muted'
          }`}
        >
          <Check className="w-3.5 h-3.5" />
          {state.isEditing ? 'Done' : 'Edit'}
        </button>

        {/* Add Panel */}
        <div className="relative">
          <button
            onClick={() => setShowAddMenu(!showAddMenu)}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Panel
          </button>

          {showAddMenu && (
            <div className="absolute top-full right-0 mt-1 z-50 w-52 bg-popover border border-border rounded-lg shadow-lg p-2 space-y-0.5">
              {panelTypes.map((type) => (
                <button
                  key={type}
                  onClick={() => {
                    addPanel(type, { runIds: state.selectedRunIds })
                    setShowAddMenu(false)
                  }}
                  className="flex items-center gap-2 w-full text-left text-xs px-2 py-1.5 rounded hover:bg-muted transition-colors"
                >
                  {PANEL_ICONS[type]}
                  {PANEL_LABELS[type]}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* New Pipeline */}
        <a
          href={`/pipelines/new${state.selectedProjectId ? `?projectId=${state.selectedProjectId}` : ''}`}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border border-border hover:bg-muted text-muted-foreground transition-colors"
          title="Create Pipeline"
        >
          <GitBranch className="w-3.5 h-3.5" />
          New Pipeline
        </a>

        {/* Reset */}
        <button
          onClick={resetLayout}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border border-border hover:bg-muted text-muted-foreground"
          title="Reset to Default"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

function WorkspaceGrid() {
  const { state } = useWorkspace()

  return (
    <div
      className="grid gap-4"
      style={{
        gridTemplateColumns: 'repeat(12, 1fr)',
        gridAutoRows: 'minmax(160px, auto)',
        alignItems: 'stretch',
      }}
    >
      {state.panels.map((panel) => (
        <div key={panel.id} style={{ gridColumn: `span ${panel.colSpan}`, gridRow: `span ${panel.rowSpan}` }}>
          <PanelRenderer panel={panel} />
        </div>
      ))}
    </div>
  )
}

function WorkspaceContent() {
  const { state, dispatch } = useWorkspace()
  const [searchParams, setSearchParams] = useSearchParams()

  // Handle ?projectId=xxx navigation from Projects page
  useEffect(() => {
    const projectId = searchParams.get('projectId')
    if (projectId && projectId !== state.selectedProjectId) {
      dispatch({ type: 'SET_SELECTED_PROJECT', projectId })
      const next = new URLSearchParams(searchParams)
      next.delete('projectId')
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, state.selectedProjectId, dispatch, setSearchParams])

  return (
    <div className="p-6 space-y-4">
      <WorkspaceToolbar />
      <WorkspaceGrid />

      {state.panels.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <LayoutGrid className="w-12 h-12 mb-4 opacity-30" />
          <p className="text-sm">No panels in your workspace.</p>
          <p className="text-xs mt-1">Click "Add Panel" to start building your dashboard.</p>
        </div>
      )}
    </div>
  )
}

export function Workspace() {
  return (
    <WorkspaceProvider>
      <WorkspaceContent />
    </WorkspaceProvider>
  )
}
