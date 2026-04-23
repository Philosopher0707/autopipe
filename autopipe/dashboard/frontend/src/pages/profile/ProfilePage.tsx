import { useState } from 'react'
import { User, Key, Settings, Copy, RefreshCw } from 'lucide-react'
import { Card, CardContent, Tabs, TabsList, TabsTrigger, TabsContent, Input, Button } from '@/components/ui'
import { ActivityHeatmap } from '@/components/ActivityHeatmap'
import { DataTable } from '@/components/DataTable'

interface ApiKey {
  id: string
  name: string
  key: string
  created_at: string
  last_used?: string
}

const MOCK_HEATMAP = Array.from({ length: 70 }, (_, i) => {
  const date = new Date()
  date.setDate(date.getDate() - i)
  return {
    date: date.toISOString().split('T')[0],
    count: Math.floor(Math.random() * 12),
  }
}).reverse()

const MOCK_KEYS: ApiKey[] = [
  { id: '1', name: 'Production', key: 'ak_prod_••••••••••••••••', created_at: '2026-04-01T00:00:00Z', last_used: '2026-04-22T10:00:00Z' },
  { id: '2', name: 'Staging', key: 'ak_stag_••••••••••••••••', created_at: '2026-03-15T00:00:00Z', last_used: '2026-04-21T14:30:00Z' },
]

export function ProfilePage() {
  const [activeTab, setActiveTab] = useState('overview')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Profile</h1>
        <p className="text-sm text-muted-foreground">Manage your account and preferences.</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">
            <User className="w-4 h-4 mr-1.5" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="settings">
            <Settings className="w-4 h-4 mr-1.5" />
            Settings
          </TabsTrigger>
          <TabsTrigger value="keys">
            <Key className="w-4 h-4 mr-1.5" />
            API Keys
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="pt-4 space-y-6">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                  <User className="w-8 h-8 text-primary" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold">Admin User</h2>
                  <p className="text-sm text-muted-foreground">admin@autopipe.local</p>
                  <p className="text-xs text-muted-foreground mt-0.5">Role: Administrator</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <h3 className="text-sm font-semibold mb-4">Activity (Last 10 Weeks)</h3>
              <ActivityHeatmap data={MOCK_HEATMAP} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings" className="pt-4">
          <Card>
            <CardContent className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Full Name</label>
                  <Input value="Admin User" readOnly />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Email</label>
                  <Input value="admin@autopipe.local" readOnly />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Organization</label>
                  <Input value="AutoPipe" readOnly />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Timezone</label>
                  <Input value="UTC" readOnly />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="keys" className="pt-4">
          <Card>
            <CardContent className="p-4">
              <DataTable
                columns={[
                  { key: 'name', header: 'Name', accessor: (k) => k.name },
                  { key: 'key', header: 'Key', accessor: (k) => <span className="font-mono text-xs">{k.key}</span> },
                  { key: 'created', header: 'Created', accessor: (k) => k.created_at.split('T')[0] },
                  { key: 'last_used', header: 'Last Used', accessor: (k) => (k.last_used ? k.last_used.split('T')[0] : '—') },
                  {
                    key: 'actions',
                    header: 'Actions',
                    accessor: () => (
                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="icon" title="Copy">
                          <Copy className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" title="Regenerate">
                          <RefreshCw className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    ),
                  },
                ]}
                data={MOCK_KEYS}
                emptyMessage="No API keys."
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
