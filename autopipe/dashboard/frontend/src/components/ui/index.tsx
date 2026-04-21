import React, { useState, type ReactNode } from 'react'
import { cn } from '@/utils/helpers'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'outline' | 'ghost' | 'destructive'
  size?: 'sm' | 'md' | 'lg' | 'icon'
}

export function Button({
  className,
  variant = 'default',
  size = 'md',
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-lg font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50',
        {
          'bg-primary text-primary-foreground hover:bg-primary/90': variant === 'default',
          'border border-input bg-background hover:bg-accent hover:text-accent-foreground': variant === 'outline',
          'hover:bg-accent hover:text-accent-foreground': variant === 'ghost',
          'bg-destructive text-destructive-foreground hover:bg-destructive/90': variant === 'destructive',
        },
        {
          'h-8 px-3 text-xs': size === 'sm',
          'h-9 px-4 py-2': size === 'md',
          'h-10 px-6': size === 'lg',
          'h-9 w-9': size === 'icon',
        },
        className
      )}
      {...props}
    />
  )
}

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Card({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border bg-card text-card-foreground shadow',
        className
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex flex-col space-y-1.5 p-6', className)}
      {...props}
    />
  )
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn('font-semibold leading-none tracking-tight', className)}
      {...props}
    />
  )
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-6 pt-0', className)} {...props} />
}

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline'
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors',
        {
          'border-transparent bg-primary text-primary-foreground': variant === 'default',
          'border-transparent bg-secondary text-secondary-foreground': variant === 'secondary',
          'border-transparent bg-destructive text-destructive-foreground': variant === 'destructive',
          'text-foreground': variant === 'outline',
        },
        className
      )}
      {...props}
    />
  )
}

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        'flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors',
        'file:border-0 file:bg-transparent file:text-sm file:font-medium',
        'placeholder:text-muted-foreground',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      {...props}
    />
  )
}

export function Skeleton({ className }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted', className)}
    />
  )
}

// Tabs Components
interface TabsContextValue {
  value: string
  onValueChange: (value: string) => void
}

const TabsContext = React.createContext<TabsContextValue | null>(null)

export function Tabs({ children, value, onValueChange, className }: {
  children: ReactNode
  value: string
  onValueChange: (value: string) => void
  className?: string
}) {
  return (
    <TabsContext.Provider value={{ value, onValueChange }}>
      <div className={cn('w-full', className)}>{children}</div>
    </TabsContext.Provider>
  )
}

export function TabsList({ children, className }: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-center gap-1 border-b border-border bg-muted/50 rounded-lg p-1 w-fit', className)}>
      {children}
    </div>
  )
}

export function TabsTrigger({ children, value, className }: {
  children: ReactNode
  value: string
  className?: string
}) {
  const ctx = React.useContext(TabsContext)
  const isActive = ctx?.value === value

  return (
    <button
      onClick={() => ctx?.onValueChange(value)}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-all',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        isActive 
          ? 'bg-background text-foreground shadow-sm' 
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        className
      )}
    >
      {children}
    </button>
  )
}

export function TabsContent({ children, value, className }: {
  children: ReactNode
  value: string
  className?: string
}) {
  const ctx = React.useContext(TabsContext)
  const isActive = ctx?.value === value

  if (!isActive) return null

  return (
    <div className={cn('focus-visible:outline-none', className)}>
      {children}
    </div>
  )
}
const DropdownMenuContext = React.createContext<{
  open: boolean
  onOpenChange: (open: boolean) => void
} | null>(null)

export function DropdownMenu({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenuContext.Provider value={{ open, onOpenChange: setOpen }}>
      <div className="relative inline-block">
        {children}
      </div>
    </DropdownMenuContext.Provider>
  )
}

export function DropdownMenuTrigger({ children, asChild }: {
  children: ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
  asChild?: boolean
}) {
  const ctx = React.useContext(DropdownMenuContext)!

  const handleClick = () => {
    ctx.onOpenChange(!ctx.open)
  }

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<{ onClick?: () => void }>, {
      onClick: () => {
        ctx.onOpenChange(!ctx.open)
        ;(children as React.ReactElement<{ onClick?: () => void }>).props?.onClick?.()
      },
    })
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="inline-flex"
      aria-expanded={ctx.open}
    >
      {children}
    </button>
  )
}

export function DropdownMenuContent({ children, align = 'end' }: {
  children: ReactNode
  align?: 'start' | 'center' | 'end'
  open?: boolean
  onOpenChange?: (open: boolean) => void
}) {
  const ctx = React.useContext(DropdownMenuContext)

  if (!ctx?.open) return null

  return (
    <>
      <div
        className="fixed inset-0 z-40"
        onClick={() => ctx.onOpenChange(false)}
      />
      <div
        className={cn(
          'absolute z-50 mt-2 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md',
          'animate-in fade-in-0 zoom-in-95',
          align === 'end' ? 'right-0' : align === 'start' ? 'left-0' : 'left-1/2 -translate-x-1/2'
        )}
      >
        {children}
      </div>
    </>
  )
}

export function DropdownMenuItem({ children, onClick, className }: {
  children: ReactNode
  onClick?: () => void
  className?: string
}) {
  const ctx = React.useContext(DropdownMenuContext)!

  const handleClick = () => {
    onClick?.()
    ctx.onOpenChange(false)
  }

  return (
    <button
      className={cn(
        'relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none',
        'transition-colors hover:bg-accent hover:text-accent-foreground',
        'focus:bg-accent focus:text-accent-foreground',
        'w-full text-left',
        className
      )}
      onClick={handleClick}
    >
      {children}
    </button>
  )
}
