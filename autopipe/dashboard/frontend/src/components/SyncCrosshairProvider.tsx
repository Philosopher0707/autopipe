import { createContext, useContext, useState, type ReactNode } from 'react'

interface SyncCrosshairContextValue {
  activeLabel: string | null
  setActiveLabel: (label: string | null) => void
}

const SyncCrosshairContext = createContext<SyncCrosshairContextValue | null>(null)

export function SyncCrosshairProvider({ children }: { children: ReactNode }) {
  const [activeLabel, setActiveLabel] = useState<string | null>(null)

  return (
    <SyncCrosshairContext.Provider value={{ activeLabel, setActiveLabel }}>
      {children}
    </SyncCrosshairContext.Provider>
  )
}

export function useSyncCrosshair() {
  const ctx = useContext(SyncCrosshairContext)
  if (!ctx) {
    throw new Error('useSyncCrosshair must be used within SyncCrosshairProvider')
  }
  return ctx
}
