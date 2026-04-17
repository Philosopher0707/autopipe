import React from 'react'
import { Card, CardContent, Badge } from '@/components/ui'
import { cn } from '@/utils/helpers'

interface StatCardProps {
  title: string
  value: string | number
  subtext?: string
  trend?: 'up' | 'down'
  trendValue?: string
  icon: React.ElementType
  color: string
  status?: { running: number }
}

export function StatCard({
  title,
  value,
  subtext,
  trend,
  trendValue,
  icon: Icon,
  color,
  status,
}: StatCardProps) {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className={cn('p-3 rounded-lg', color)}>
            <Icon className="w-5 h-5 text-white" />
          </div>
          {trend && (
            <Badge
              variant={trend === 'up' ? 'default' : 'destructive'}
              className="text-xs"
            >
              {trend === 'up' ? '+' : ''}
              {trendValue}
            </Badge>
          )}
        </div>
        <div className="mt-4">
          <h3 className="text-2xl font-bold text-foreground">{value}</h3>
          <p className="text-sm text-muted-foreground">{title}</p>
          {subtext && <p className="text-xs text-muted-foreground mt-1">{subtext}</p>}
          {status && (
            <div className="flex items-center gap-2 mt-2 text-xs">
              <span className="flex items-center text-blue-600">
                <span className="w-2 h-2 rounded-full bg-blue-500 mr-1 animate-pulse" />
                {status.running} Running
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
