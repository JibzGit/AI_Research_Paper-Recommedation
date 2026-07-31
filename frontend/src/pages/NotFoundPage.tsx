import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <Compass className="size-8 text-accent-purple" aria-hidden="true" />
      <h2 className="text-lg font-semibold text-foreground">Page not found</h2>
      <p className="max-w-sm text-sm text-muted-foreground">The page you're looking for doesn't exist or has moved.</p>
      <Button asChild size="sm">
        <Link to="/">Back to Dashboard</Link>
      </Button>
    </div>
  )
}
