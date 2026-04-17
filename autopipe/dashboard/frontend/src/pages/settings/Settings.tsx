import { useState } from 'react'
import { useAuthStore } from '@/stores'
import {
  Settings as SettingsIcon, Moon, Sun, Bell, Key, Save
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, Button, Badge } from '@/components/ui'

export function SettingsPage() {
  const { user } = useAuthStore()
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage your account and preferences</p>
      </div>

      {/* Profile */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SettingsIcon className="w-5 h-5" />
            Profile
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium">Username</label>
              <input
                type="text"
                defaultValue={user?.username || ''}
                className="w-full h-10 mt-1 px-3 border rounded-lg bg-background text-sm"
                readOnly
              />
            </div>
            <div>
              <label className="text-sm font-medium">Email</label>
              <input
                type="email"
                defaultValue={user?.email || ''}
                className="w-full h-10 mt-1 px-3 border rounded-lg bg-background text-sm"
                readOnly
              />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">Role</label>
            <div className="mt-1">
              <Badge variant="outline">{user?.role || 'viewer'}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {theme === 'dark' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
            Appearance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Theme</p>
              <p className="text-xs text-muted-foreground">Choose your preferred color scheme</p>
            </div>
            <div className="flex gap-2">
              {(['light', 'dark'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTheme(t)}
                  className={`px-4 py-2 text-sm rounded-lg border transition-colors ${
                    theme === t ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'
                  }`}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="w-5 h-5" />
            Notifications
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[
            { label: 'Pipeline failures', desc: 'Get notified when a pipeline run fails' },
            { label: 'Drift alerts', desc: 'Receive alerts when data drift is detected' },
            { label: 'Model promotions', desc: 'Notification when models are promoted' },
            { label: 'Experiment completion', desc: 'Alert when experiments complete' },
          ].map((item, i) => (
            <div key={i} className="flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">{item.label}</p>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
              <input type="checkbox" defaultChecked className="rounded" />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* API Keys */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="w-5 h-5" />
            API Keys
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            API keys allow programmatic access to the AutoPipe Dashboard API.
          </p>
          <Button variant="outline" size="sm">
            <Key className="w-4 h-4 mr-2" />
            Generate New Key
          </Button>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} className="min-w-32">
          {saved ? '✓ Saved!' : <><Save className="w-4 h-4 mr-2" /> Save Changes</>}
        </Button>
      </div>
    </div>
  )
}
