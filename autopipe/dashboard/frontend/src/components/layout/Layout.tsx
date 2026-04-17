import React from 'react'
import {
  LayoutDashboard,
  GitBranch,
  Play,
  FlaskConical,
  Box,
  AlertTriangle,
  Settings,
  Users,
  LogOut,
  Menu,
  X,
} from 'lucide-react'
import { cn } from '@/utils/helpers'
import { useUIStore, useAuthStore } from '@/stores'
import { NavLink } from 'react-router-dom'
import { ThemeToggle } from '@/components/ThemeToggle'

interface SidebarItemProps {
  to: string
  icon: React.ReactNode
  label: string
  badge?: number
}

function SidebarItem({ to, icon, label, badge }: SidebarItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
          isActive
            ? 'bg-primary text-primary-foreground'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
        )
      }
    >
      {icon}
      <span className="flex-1">{label}</span>
      {badge && badge > 0 && (
        <span className="bg-primary/10 text-primary text-xs px-2 py-0.5 rounded-full">
          {badge}
        </span>
      )}
    </NavLink>
  )
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { sidebarOpen, toggleSidebar } = useUIStore()
  const { logout } = useAuthStore()

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-card border-r border-border transition-transform duration-200 lg:static lg:translate-x-0',
          !sidebarOpen && '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
              <GitBranch className="w-6 h-6 text-primary-foreground" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-foreground">AutoPipe</h1>
              <p className="text-xs text-muted-foreground">ML Dashboard</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1 overflow-y-auto h-[calc(100vh-140px)]">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-3">
            Overview
          </div>
          
          <SidebarItem to="/" icon={<LayoutDashboard className="w-5 h-5" />} label="Dashboard" />
          <SidebarItem to="/pipelines" icon={<GitBranch className="w-5 h-5" />} label="Pipelines" badge={5} />

          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 mt-6 px-3">
            ML Lifecycle
          </div>
          
          <SidebarItem to="/experiments" icon={<FlaskConical className="w-5 h-5" />} label="Experiments" badge={3} />
          <SidebarItem to="/models" icon={<Box className="w-5 h-5" />} label="Model Registry" badge={8} />
          <SidebarItem to="/drift" icon={<AlertTriangle className="w-5 h-5" />} label="Drift Monitor" badge={1} />

          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 mt-6 px-3">
            System
          </div>
          
          <SidebarItem to="/settings" icon={<Settings className="w-5 h-5" />} label="Settings" />
          <SidebarItem to="/team" icon={<Users className="w-5 h-5" />} label="Team" />
        </nav>

        {/* User */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-border bg-card">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
              <Users className="w-5 h-5 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">Data Scientist</p>
              <p className="text-xs text-muted-foreground truncate">Admin</p>
            </div>
            <button
              onClick={logout}
              className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
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
        <header className="h-16 border-b border-border bg-card flex items-center justify-between px-6">
          <button
            onClick={toggleSidebar}
            className="p-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted lg:hidden"
          >
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          <div className="flex items-center gap-4 ml-auto">
            <ThemeToggle />
            <NavLink
              to="/pipelines/new"
              className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <Play className="w-4 h-4" />
              New Pipeline
            </NavLink>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto p-8">{children}</div>
      </main>
    </div>
  )
}
