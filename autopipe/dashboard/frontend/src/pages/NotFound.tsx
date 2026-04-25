import { Link } from 'react-router-dom'
import { Home, AlertTriangle } from 'lucide-react'
import { Button, Card, CardContent } from '@/components/ui'

export function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardContent className="py-12 text-center">
          <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-amber-500" />
          <h1 className="text-4xl font-bold text-foreground mb-2">404</h1>
          <p className="text-muted-foreground mb-6">
            Page not found. The URL may be misspelled or the page no longer exists.
          </p>
          <Link to="/">
            <Button className="inline-flex items-center gap-2">
              <Home className="w-4 h-4" />
              Back to Dashboard
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}
