import { useState } from 'react'
import { Star, GitBranch } from 'lucide-react'
import { cn, formatRelativeTime } from '@/utils/helpers'
import { Card, StatusPill } from '@/components/ui'
import type { Project } from '@/types'

interface ProjectCardProps {
  project: Project
  className?: string
  onToggleStar?: (project: Project) => void
  onClick?: (project: Project) => void
}

export function ProjectCard({ project, className, onToggleStar, onClick }: ProjectCardProps) {
  const [starred, setStarred] = useState(project.starred ?? false)

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    const next = !starred
    setStarred(next)
    onToggleStar?.(project)
  }

  const sparkline = (
    <svg viewBox="0 0 60 20" className="w-16 h-5" preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        points="0,18 15,14 30,16 45,8 60,4"
        className="text-primary"
      />
    </svg>
  )

  return (
    <Card
      className={cn('p-4 relative group cursor-pointer hover:border-primary/50 transition-colors', className)}
      onClick={() => onClick?.(project)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick?.(project) }}
      aria-label={`Open project ${project.name}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <GitBranch className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-foreground">{project.name}</h3>
            {project.description && (
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{project.description}</p>
            )}
          </div>
        </div>
        <button
          onClick={handleToggle}
          className={cn(
            'p-1.5 rounded-md transition-colors',
            starred ? 'text-amber-400 hover:text-amber-500' : 'text-muted-foreground hover:text-foreground'
          )}
          title={starred ? 'Unstar' : 'Star'}
        >
          <Star className={cn('w-4 h-4', starred && 'fill-current')} />
        </button>
      </div>

      <div className="flex items-center justify-between mt-4">
        <StatusPill status={project.status} />
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {project.last_run_at ? formatRelativeTime(project.last_run_at) : '—'}
          </span>
          {sparkline}
        </div>
      </div>
    </Card>
  )
}
