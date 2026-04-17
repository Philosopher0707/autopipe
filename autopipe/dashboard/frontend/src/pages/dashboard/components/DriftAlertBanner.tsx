import { useNavigate } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'

interface DriftAlertBannerProps {
  featuresDrifted: number
}

export function DriftAlertBanner({ featuresDrifted }: DriftAlertBannerProps) {
  const navigate = useNavigate()

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between dark:bg-amber-950/20 dark:border-amber-900">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
          <AlertTriangle className="w-5 h-5 text-amber-600" />
        </div>
        <div>
          <p className="text-sm font-medium text-amber-900 dark:text-amber-200">Data drift detected in production</p>
          <p className="text-xs text-amber-700 dark:text-amber-300">
            {featuresDrifted} features have drifted above threshold
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => navigate('/drift')}
          className="px-4 py-2 bg-white border border-amber-300 text-amber-700 rounded-lg text-sm font-medium hover:bg-amber-50 dark:bg-transparent dark:text-amber-300 dark:border-amber-700"
        >
          View Details
        </button>
      </div>
    </div>
  )
}
