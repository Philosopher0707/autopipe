import { createContext, useContext, useReducer, useCallback, useEffect } from 'react'

// ─── Panel Types ───────────────────────────────────────────────

export type PanelType =
  | 'line-plot'
  | 'scatter-plot'
  | 'bar-chart'
  | 'param-importance'
  | 'metric-summary'
  | 'confusion-matrix'
  | 'run-table'
  | 'run-comparison'
  | 'histogram'
  | 'parallel-coords'
  | 'media-viewer'
  | 'dataframe-table'
  | 'text-log'

export interface PanelConfig {
  metricName?: string
  xMetric?: string
  yMetric?: string
  runIds?: string[]
  experimentId?: string
  pipelineId?: string
  smoothing?: boolean
  sortOrder?: 'asc' | 'desc'
  showLegend?: boolean
  [key: string]: unknown
}

export interface PanelLayout {
  id: string
  type: PanelType
  title: string
  colSpan: number // 1–6 (12-column grid)
  rowSpan: number // 1–4
  config: PanelConfig
}

export interface WorkspaceState {
  panels: PanelLayout[]
  isEditing: boolean
  selectedRunIds: string[]
  selectedExperimentId?: string
}

// ─── Default Layout ──────────────────────────────────────────────

export const DEFAULT_PANELS: PanelLayout[] = [
  {
    id: 'panel-001',
    type: 'line-plot',
    title: 'Metric Over Time',
    colSpan: 6,
    rowSpan: 2,
    config: { metricName: 'loss', runIds: [], showLegend: true },
  },
  {
    id: 'panel-002',
    type: 'metric-summary',
    title: 'Key Metrics',
    colSpan: 6,
    rowSpan: 1,
    config: { runIds: [] },
  },
  {
    id: 'panel-003',
    type: 'bar-chart',
    title: 'Final Values',
    colSpan: 6,
    rowSpan: 2,
    config: { metricName: 'accuracy', runIds: [] },
  },
  {
    id: 'panel-004',
    type: 'scatter-plot',
    title: 'Metric Correlation',
    colSpan: 6,
    rowSpan: 2,
    config: { xMetric: 'loss', yMetric: 'accuracy', runIds: [] },
  },
]

// ─── Actions ─────────────────────────────────────────────────────

type WorkspaceAction =
  | { type: 'SET_PANELS'; panels: PanelLayout[] }
  | { type: 'ADD_PANEL'; panel: PanelLayout }
  | { type: 'REMOVE_PANEL'; id: string }
  | { type: 'UPDATE_PANEL'; id: string; partial: Partial<PanelLayout> }
  | { type: 'MOVE_PANEL'; id: string; colSpan?: number; rowSpan?: number }
  | { type: 'RESET_LAYOUT' }
  | { type: 'TOGGLE_EDIT' }
  | { type: 'SET_SELECTED_RUNS'; runIds: string[] }
  | { type: 'LOAD_STATE'; state: WorkspaceState }

// ─── Reducer ─────────────────────────────────────────────────────

function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case 'SET_PANELS':
      return { ...state, panels: action.panels }
    case 'ADD_PANEL':
      return { ...state, panels: [...state.panels, action.panel] }
    case 'REMOVE_PANEL':
      return { ...state, panels: state.panels.filter((p) => p.id !== action.id) }
    case 'UPDATE_PANEL':
      return {
        ...state,
        panels: state.panels.map((p) =>
          p.id === action.id ? { ...p, ...action.partial } : p
        ),
      }
    case 'MOVE_PANEL':
      return {
        ...state,
        panels: state.panels.map((p) =>
          p.id === action.id
            ? { ...p, colSpan: action.colSpan ?? p.colSpan, rowSpan: action.rowSpan ?? p.rowSpan }
            : p
        ),
      }
    case 'RESET_LAYOUT':
      return { ...state, panels: DEFAULT_PANELS }
    case 'TOGGLE_EDIT':
      return { ...state, isEditing: !state.isEditing }
    case 'SET_SELECTED_RUNS':
      return { ...state, selectedRunIds: action.runIds }
    case 'LOAD_STATE':
      return action.state
    default:
      return state
  }
}

// ─── Context ─────────────────────────────────────────────────────

interface WorkspaceContextValue {
  state: WorkspaceState
  dispatch: React.Dispatch<WorkspaceAction>
  addPanel: (type: PanelType, config?: PanelConfig) => void
  removePanel: (id: string) => void
  updatePanel: (id: string, partial: Partial<PanelLayout>) => void
  resetLayout: () => void
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

const STORAGE_KEY = 'autopipe-workspace-layout'

function loadPersistedState(): Partial<WorkspaceState> | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<WorkspaceState>
    return parsed
  } catch {
    return null
  }
}

function savePersistedState(state: WorkspaceState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Silently fail on storage errors
  }
}

function getDefaultTitle(type: PanelType): string {
  switch (type) {
    case 'line-plot': return 'Metric Over Time'
    case 'scatter-plot': return 'Scatter Plot'
    case 'bar-chart': return 'Bar Chart'
    case 'param-importance': return 'Parameter Comparison'
    case 'metric-summary': return 'Metric Summary'
    case 'confusion-matrix': return 'Confusion Matrix'
    case 'run-table': return 'Runs Table'
    case 'run-comparison': return 'Run Comparison'
    case 'histogram': return 'Histogram'
    case 'parallel-coords': return 'Parallel Coordinates'
    case 'media-viewer': return 'Media Viewer'
    case 'dataframe-table': return 'Dataframe Table'
    case 'text-log': return 'Text Log'
    default:
      return 'Panel'
  }
}

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(workspaceReducer, null, () => {
    const persisted = loadPersistedState()
    return {
      panels: persisted?.panels ?? DEFAULT_PANELS,
      isEditing: false,
      selectedRunIds: persisted?.selectedRunIds ?? [],
      selectedExperimentId: persisted?.selectedExperimentId,
    }
  })

  // Persist on every change
  useEffect(() => {
    savePersistedState(state)
  }, [state])

  const addPanel = useCallback((type: PanelType, config?: PanelConfig) => {
    const id = `panel-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
    const panel: PanelLayout = {
      id,
      type,
      title: getDefaultTitle(type),
      colSpan: 6,
      rowSpan: 2,
      config: config ?? {},
    }
    dispatch({ type: 'ADD_PANEL', panel })
  }, [])

  const removePanel = useCallback((id: string) => {
    dispatch({ type: 'REMOVE_PANEL', id })
  }, [])

  const updatePanel = useCallback((id: string, partial: Partial<PanelLayout>) => {
    dispatch({ type: 'UPDATE_PANEL', id, partial })
  }, [])

  const resetLayout = useCallback(() => {
    dispatch({ type: 'RESET_LAYOUT' })
  }, [])

  return (
    <WorkspaceContext.Provider
      value={{ state, dispatch, addPanel, removePanel, updatePanel, resetLayout }}
    >
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used inside WorkspaceProvider')
  return ctx
}
