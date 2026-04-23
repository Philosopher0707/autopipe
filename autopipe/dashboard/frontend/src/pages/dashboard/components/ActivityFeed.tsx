import { Clock } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui'
import { formatRelativeTime } from '@/utils/helpers'
import { ActivityIcon } from './ActivityIcon'
import type { ActivityLog } from '@/types'

interface ActivityFeedProps {
  activities: ActivityLog[]
}

export function ActivityFeed({ activities }: ActivityFeedProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {activities?.map((activity: ActivityLog, idx: number) => (
            <div key={activity.id || idx} className="flex gap-2 items-start py-1.5">
              <div className="mt-0.5">
                <ActivityIcon action={activity.action} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">
                  {activity.title || activity.action.replace(/_/g, ' ')}
                </p>
                {activity.description && (
                  <p className="text-xs text-muted-foreground truncate">
                    {activity.description}
                  </p>
                )}
                <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatRelativeTime(activity.created_at)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
