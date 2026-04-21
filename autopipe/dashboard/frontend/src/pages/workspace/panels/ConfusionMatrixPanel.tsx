import { useMemo, useState } from 'react'
import { ToggleLeft, ToggleRight } from 'lucide-react'
import { PanelWrapper } from '../PanelWrapper'
import type { PanelLayout } from '../WorkspaceContext'

interface ConfusionMatrixPanelProps {
  panel: PanelLayout
}

// Demo confusion matrix data (3-class: cat, dog, bird)
const demoMatrix: number[][] = [
  [45, 3, 2],    // cat predicted as cat/dog/bird
  [2, 50, 1],    // dog predicted as cat/dog/bird
  [1, 0, 48],    // bird predicted as cat/dog/bird
]
const demoLabels = ['cat', 'dog', 'bird']

function getColorForValue(val: number, max: number): string {
  if (max === 0) return 'rgb(243, 244, 246)'
  const ratio = val / max
  const r = Math.round(224 - ratio * 180)
  const g = Math.round(242 - ratio * 210)
  const b = Math.round(254 + ratio * 1)
  return `rgb(${r}, ${g}, ${b})`
}

function getTextColor(val: number, max: number): string {
  if (max === 0) return '#6b7280'
  return val / max > 0.5 ? 'white' : '#1f2937'
}

export function ConfusionMatrixPanel({ panel }: ConfusionMatrixPanelProps) {
  const { config = {} } = panel
  const [useDemo] = useState(!config.matrix)

  const matrixData: number[][] = useMemo(() => {
    const custom = config.matrix as number[][] | undefined
    if (custom && custom.length > 0) return custom
    return demoMatrix
  }, [config.matrix])

  const labels: string[] = useMemo(() => {
    const custom = config.labels as string[] | undefined
    if (custom && custom.length > 0) return custom
    const inferred = matrixData.length > 0 ? matrixData.map((_, i) => `Class ${i + 1}`) : demoLabels
    return inferred
  }, [config.labels, matrixData])

  const maxVal = Math.max(...matrixData.flat())
  const total = matrixData.flat().reduce((a, b) => a + b, 0)

  const accuracy = useMemo(() => {
    let correct = 0
    for (let i = 0; i < Math.min(matrixData.length, matrixData[0]?.length ?? 0); i++) {
      correct += matrixData[i]?.[i] ?? 0
    }
    return total > 0 ? (correct / total * 100).toFixed(1) : '0.0'
  }, [matrixData, total])

  return (
    <PanelWrapper panel={panel}>
      <div className="flex flex-col gap-2 h-full">
        <div className="flex items-center justify-between">
          <div className="flex gap-3 text-[10px] text-muted-foreground">
            <span>Total: {total}</span>
            <span>Accuracy: {accuracy}%</span>
            <span>Classes: {matrixData.length}×{matrixData[0]?.length ?? 0}</span>
          </div>
          {!config.matrix && (
            <button
              disabled
              className="text-[10px] text-muted-foreground flex items-center gap-1"
            >
              {useDemo ? <ToggleRight className="w-3 h-3" /> : <ToggleLeft className="w-3 h-3" />}
              {useDemo ? 'Demo' : 'Placeholder'}
            </button>
          )}
        </div>

        <div className="flex-1 flex items-center justify-center overflow-auto">
          <div className="grid gap-0.5" style={{ gridTemplateColumns: `auto repeat(${matrixData[0]?.length ?? 0}, minmax(32px, 1fr))` }}>
            <div className="text-[10px] text-muted-foreground text-right pr-2 self-end pb-0.5">Actual ↓<br />Pred →</div>

            {labels.map((label) => (
              <div key={`col-${label}`} className="text-[10px] text-muted-foreground text-center truncate px-0.5">
                {label}
              </div>
            ))}

            {matrixData.map((row, i) => (
              <>
                <div key={`row-label-${i}`} className="text-[10px] text-muted-foreground text-right pr-2 self-center truncate">
                  {labels[i] ?? `C${i}`}
                </div>

                {row.map((val, j) => {
                  const bg = getColorForValue(val, maxVal)
                  const text = getTextColor(val, maxVal)
                  const isDiag = i === j
                  return (
                    <div
                      key={`cell-${i}-${j}`}
                      className={`relative flex items-center justify-center rounded-sm text-xs font-medium min-h-[32px] transition-colors ${isDiag ? 'ring-1 ring-green-400/30' : ''}`}
                      style={{ backgroundColor: bg, color: text }}
                      title={`${labels[i]} → ${labels[j]}: ${val}`}
                    >
                      {val}
                    </div>
                  )
                })}
              </>
            ))}
          </div>
        </div>
      </div>
    </PanelWrapper>
  )
}
