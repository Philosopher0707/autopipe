import React from 'react'
import {
  GitBranch,
  AlertTriangle,
  TrendingUp,
  Clock,
  Activity,
  FlaskConical,
} from 'lucide-react'
import { cn } from '@/utils/helpers'

interface ActivityIconProps {
  action: string
}

const iconConfig: Record<string, { icon: React.ElementType; color: string }> = {
  run_completed: { icon: Activity, color: 'bg-green-100 text-green-600' },
  run_failed: { icon: AlertTriangle, color: 'bg-red-100 text-red-600' },
  run_started: { icon: Clock, color: 'bg-blue-100 text-blue-600' },
  run_triggered: { icon: GitBranch, color: 'bg-indigo-100 text-indigo-600' },
  model_promoted: { icon: TrendingUp, color: 'bg-blue-100 text-blue-600' },
  drift_alert: { icon: AlertTriangle, color: 'bg-red-100 text-red-600' },
  experiment_started: { icon: FlaskConical, color: 'bg-purple-100 text-purple-600' },
  system_update: { icon: Activity, color: 'bg-gray-100 text-gray-600' },
}

export function ActivityIcon({ action }: ActivityIconProps) {
  const config = iconConfig[action] || iconConfig.system_update
  const Icon = config.icon

  return (
    <div className={cn('w-8 h-8 rounded-full flex items-center justify-center', config.color)}>
      <Icon className="w-4 h-4" />
    </div>
  )
}
