import { useAuthStore } from '@/stores'
import { Users, Shield, Trash2, UserPlus } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, Badge, Button } from '@/components/ui'

const mockUsers = [
  { id: '1', username: 'admin', email: 'admin@autopipe.io', role: 'admin', is_active: true, last_login: '2026-04-14T08:00:00Z' },
  { id: '2', username: 'jsmith', email: 'jane.smith@autopipe.io', role: 'data_scientist', is_active: true, last_login: '2026-04-13T15:30:00Z' },
  { id: '3', username: 'mjohnson', email: 'mike.johnson@autopipe.io', role: 'data_scientist', is_active: true, last_login: '2026-04-12T09:00:00Z' },
  { id: '4', username: 'eviewer', email: 'emma.viewer@autopipe.io', role: 'viewer', is_active: false, last_login: '2026-04-01T10:00:00Z' },
]

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-red-100 text-red-700',
  data_scientist: 'bg-blue-100 text-blue-700',
  viewer: 'bg-gray-100 text-gray-600',
}

export function TeamPage() {
  const { user } = useAuthStore()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Team</h1>
          <p className="text-muted-foreground mt-1">Manage team members and their roles</p>
        </div>
        <Button className="flex items-center gap-2">
          <UserPlus className="w-4 h-4" />
          Invite Member
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            Members ({mockUsers.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">User</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Role</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Status</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Last Login</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {mockUsers.map((member) => (
                <tr key={member.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="py-3 px-4">
                    <div>
                      <p className="font-medium text-sm">{member.username}</p>
                      <p className="text-xs text-muted-foreground">{member.email}</p>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <Badge className={ROLE_COLORS[member.role]}>
                      <Shield className="w-3 h-3 mr-1" />
                      {member.role.replace('_', ' ')}
                    </Badge>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium ${
                      member.is_active ? 'text-green-600' : 'text-gray-400'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        member.is_active ? 'bg-green-500' : 'bg-gray-400'
                      }`} />
                      {member.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-muted-foreground">
                    {new Date(member.last_login).toLocaleDateString()}
                  </td>
                  <td className="py-3 px-4">
                    {member.id !== user?.id && (
                      <Button variant="ghost" size="sm" className="text-destructive">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
