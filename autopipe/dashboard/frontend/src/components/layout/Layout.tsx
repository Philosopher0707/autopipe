import React from 'react'
import {
  LayoutDashboard,
  GitBranch,
  Play,
  FlaskConical,
  Box,
  BarChart3,
  AlertTriangle,
  Users,
  LogOut,
  Menu,
  X,
  Brain,
  Sparkles,
  Wrench,
  ChevronLeft,
  ChevronRight,
  FolderKanban,
} from 'lucide-react'
import { cn } from '@/utils/helpers'
import { useUIStore, useAuthStore } from '@/stores'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/api/endpoints'
import { NavLink, useLocation } from 'react-router-dom'
import { ThemeToggle } from '@/components/ThemeToggle'

interface SidebarItemProps {
  to: string
  icon: React.ReactNode
  label: string
  badge?: number
  collapsed?: boolean
}

function SidebarItem({ to, icon, label, badge, collapsed }: SidebarItemProps) {
  return (
    <NavLink
      to={to}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
          isActive
            ? 'border-l-2 border-primary bg-primary/10 text-primary'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          collapsed && 'justify-center px-2'
        )
      }
    >
      {icon}
      {!collapsed && (
        <>
          <span className="flex-1">{label}</span>
          {badge && badge > 0 && (
            <span className="bg-primary/10 text-primary text-xs px-2 py-0.5 rounded-full">
              {badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { sidebarOpen, toggleSidebar, collapsed, toggleCollapsed } = useUIStore()
  const { logout, user } = useAuthStore()
  const location = useLocation()

  const { data: counts } = useQuery({
    queryKey: ['dashboard', 'counts'],
    queryFn: () => dashboardApi.getCounts(),
    refetchInterval: 60000,
  })

  const segments = location.pathname
    .split('/')
    .filter(Boolean)
    .map((seg, i, arr) => ({
      label: seg.charAt(0).toUpperCase() + seg.slice(1).replace(/-/g, ' '),
      href: '/' + arr.slice(0, i + 1).join('/'),
    }))

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 bg-card border-r border-border transition-all duration-200 lg:static',
          collapsed ? 'w-14' : 'w-64',
          !sidebarOpen && '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className={cn('p-4 border-b border-border flex items-center', collapsed ? 'justify-center' : 'justify-between')}>
          {!collapsed && (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                <GitBranch className="w-5 h-5 text-primary-foreground" />
              </div>
              <h1 className="font-bold text-lg text-foreground">AutoPipe</h1>
            </div>
          )}
          {collapsed && (
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <GitBranch className="w-5 h-5 text-primary-foreground" />
            </div>
          )}
          <button
            onClick={toggleCollapsed}
            className="hidden lg:flex p-1 text-muted-foreground hover:text-foreground rounded hover:bg-muted"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation */}
        <nav className={cn('space-y-1 overflow-y-auto h-[calc(100vh-140px)]', collapsed ? 'p-1' : 'p-4')}>
          {!collapsed && (
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-3">
              Overview
            </div>
          )}
          <SidebarItem to="/" icon={<LayoutDashboard className="w-5 h-5" />} label="Dashboard" collapsed={collapsed} />
          <SidebarItem to="/workspace" icon={<BarChart3 className="w-5 h-5" />} label="Workspace" collapsed={collapsed} />
          <SidebarItem to="/pipelines" icon={<GitBranch className="w-5 h-5" />} label="Pipelines" badge={counts?.pipelines_active ?? 0} collapsed={collapsed} />
          <SidebarItem to="/runs" icon={<Play className="w-5 h-5" />} label="Runs" collapsed={collapsed} />

          {!collapsed && (
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 mt-6 px-3">
              ML Lifecycle
            </div>
          )}
          <SidebarItem to="/experiments" icon={<FlaskConical className="w-5 h-5" />} label="Experiments" badge={counts?.experiments_total ?? 0} collapsed={collapsed} />
          <SidebarItem to="/models" icon={<Box className="w-5 h-5" />} label="Model Registry" badge={counts?.models_total ?? 0} collapsed={collapsed} />
          <SidebarItem to="/drift" icon={<AlertTriangle className="w-5 h-5" />} label="Drift Monitor" badge={counts?.drift_features_drifted ?? 0} collapsed={collapsed} />
          <SidebarItem to="/explainability" icon={<Brain className="w-5 h-5" />} label="Explainability" collapsed={collapsed} />
          <SidebarItem to="/automl" icon={<Sparkles className="w-5 h-5" />} label="AutoML" collapsed={collapsed} />
          <SidebarItem to="/features" icon={<Wrench className="w-5 h-5" />} label="Features" collapsed={collapsed} />

          {!collapsed && (
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 mt-6 px-3">
              System
            </div>
          )}
          <SidebarItem to="/projects" icon={<FolderKanban className="w-5 h-5" />} label="Projects" collapsed={collapsed} />
        </nav>

        {/* User */}
        <div className="absolute bottom-0 left-0 right-0 p-2 border-t border-border bg-card">
          {!collapsed ? (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                <Users className="w-4 h-4 text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{user?.full_name || user?.username || 'User'}</p>
                <p className="text-xs text-muted-foreground truncate">{user?.role || ''}</p>
              </div>
              <button
                onClick={logout}
                className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex justify-center">
              <button
                onClick={logout}
                className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 border-b border-border bg-card flex items-center px-6">
          <button
            onClick={toggleSidebar}
            className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted lg:hidden"
          >
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          {/* Breadcrumb */}
          <div className="hidden lg:flex items-center gap-2 text-sm text-muted-foreground ml-4">
            <NavLink to="/" className="hover:text-foreground">Home</NavLink>
            {segments.map((seg, i) => (
              <React.Fragment key={seg.href}>
                <span>/</span>
                {i === segments.length - 1 ? (
                  <span className="text-foreground font-medium">{seg.label}</span>
                ) : (
                  <NavLink to={seg.href} className="hover:text-foreground">{seg.label}</NavLink>
                )}
              </React.Fragment>
            ))}
          </div>

          <div className="flex items-center gap-3 sm:gap-4 ml-auto flex-nowrap">
            <div className="hidden sm:block">
              <ThemeToggle />
            </div>
            <NavLink
              to="/pipelines/new"
              className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-3 sm:px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors whitespace-nowrap"
            >
              <Play className="w-4 h-4" />
              <span className="hidden sm:inline">New Pipeline</span>
            </NavLink>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto p-8">{children}</div>
      </main>
    </div>
  )
}
