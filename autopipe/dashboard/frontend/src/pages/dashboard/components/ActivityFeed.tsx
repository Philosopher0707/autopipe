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
        <div className="space-y-4">
          {activities?.map((activity: ActivityLog, idx: number) => (
            <div key={activity.id || idx} className="flex gap-3">
              <ActivityIcon action={activity.action} />
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">
                  {activity.title || activity.action.replace(/_/g, ' ')}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {activity.description || ''}
                </p>
                <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
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
