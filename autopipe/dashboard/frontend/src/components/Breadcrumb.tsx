import { NavLink } from 'react-router-dom'
import { cn } from '@/utils/helpers'

interface BreadcrumbSegment {
  label: string
  href?: string
}

interface BreadcrumbProps {
  segments: BreadcrumbSegment[]
  className?: string
}

export function Breadcrumb({ segments, className }: BreadcrumbProps) {
  return (
    <nav aria-label="breadcrumb" className={cn('flex items-center gap-2 text-sm text-muted-foreground', className)}>
      <NavLink to="/" className="hover:text-foreground">Home</NavLink>
      {segments.map((seg, i) => (
        <span key={seg.label + i} className="flex items-center gap-2">
          <span className="text-muted-foreground/50">/</span>
          {seg.href ? (
            <NavLink to={seg.href} className="hover:text-foreground">{seg.label}</NavLink>
          ) : (
            <span className="text-foreground font-medium">{seg.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}
