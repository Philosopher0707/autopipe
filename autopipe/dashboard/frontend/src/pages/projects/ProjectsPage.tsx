import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Grid3X3, List, Plus, Search } from 'lucide-react'
import { Card, CardContent, Input, Button, Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui'
import { ProjectCard } from '@/components/ProjectCard'
import { DataTable } from '@/components/DataTable'
import { StatusPill } from '@/components/ui'
import { cn, formatRelativeTime } from '@/utils/helpers'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '@/api/endpoints'
import type { Project } from '@/types'

export function ProjectsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [view, setView] = useState<'grid' | 'table'>('grid')
  const [search, setSearch] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', status: 'active' as const })

  const { data, isLoading } = useQuery({
    queryKey: ['projects', 'list', search],
    queryFn: () => projectsApi.list({ search: search || undefined }),
  })

  const createMutation = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setDialogOpen(false)
      setForm({ name: '', description: '', status: 'active' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Project> }) => projectsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const items = data?.items ?? []

  const handleToggleStar = (project: Project) => {
    updateMutation.mutate({ id: project.id, data: { starred: !project.starred } })
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) return
    createMutation.mutate({
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      status: form.status,
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="text-sm text-muted-foreground">Manage your ML pipelines and experiments.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search projects..."
              className="pl-9 w-56"
            />
          </div>
          <div className="flex border rounded-lg overflow-hidden">
            <button
              onClick={() => setView('grid')}
              className={cn(
                'px-3 py-2 text-sm transition-colors',
                view === 'grid' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
              )}
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setView('table')}
              className={cn(
                'px-3 py-2 text-sm transition-colors',
                view === 'table' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
              )}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
          <Button size="sm" onClick={() => setDialogOpen(true)}>
            <Plus className="w-4 h-4 mr-1" />
            New Project
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 bg-muted rounded-lg" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <p className="text-sm font-medium">No projects found.</p>
          <p className="text-xs mt-1">Create your first project to get started.</p>
        </div>
      ) : view === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((p) => (
            <ProjectCard
              key={p.id}
              project={p}
              onToggleStar={() => handleToggleStar(p)}
              onClick={(project) => navigate(`/workspace?projectId=${project.id}`)}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="p-4">
            <DataTable
              columns={[
                { key: 'name', header: 'Name', accessor: (p: Project) => p.name },
                { key: 'status', header: 'Status', accessor: (p: Project) => <StatusPill status={p.status} /> },
                { key: 'updated', header: 'Last Updated', accessor: (p: Project) => (p.updated_at ? formatRelativeTime(p.updated_at) : '—') },
                { key: 'starred', header: 'Starred', accessor: (p: Project) => (p.starred ? '⭐' : ''), align: 'center' },
              ]}
              data={items}
              emptyMessage="No projects match your search."
              onRowClick={(project) => navigate(`/workspace?projectId=${project.id}`)}
            />
          </CardContent>
        </Card>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Project</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Project name"
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Description</label>
              <Input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Optional description"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Status</label>
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value as 'active' })}
                className="w-full h-10 px-3 border border-input rounded-lg bg-background text-sm"
              >
                <option value="active">Active</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
