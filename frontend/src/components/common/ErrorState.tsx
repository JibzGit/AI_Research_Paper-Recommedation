import { AlertTriangle, WifiOff } from 'lucide-react'

import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'

interface ErrorStateProps {
  error: ApiError | Error
  onRetry?: () => void
}

interface Message {
  title: string
  description: string
}

/** Distinguishes status codes rather than collapsing every failure into one
 * generic message -- the backend deliberately keeps 400 (business-rule
 * violation), 404 (genuinely not found), 422 (malformed parameters), and
 * 5xx (server error) distinct, and this preserves that on the way to the
 * user. Status 0 is this app's sentinel for "never reached the server". */
function describeError(error: ApiError | Error): Message {
  if (!(error instanceof ApiError)) {
    return { title: 'Something went wrong', description: error.message }
  }
  if (error.status === 0) {
    return { title: 'Cannot reach the API', description: 'Check that the backend server is running.' }
  }
  if (error.status === 404) {
    return { title: 'Not found', description: error.detail }
  }
  if (error.status === 400) {
    return { title: 'Invalid request', description: error.detail }
  }
  if (error.status === 422) {
    return { title: 'Validation error', description: error.detail }
  }
  if (error.status >= 500) {
    return { title: 'Server error', description: 'Something went wrong on the server. Try again shortly.' }
  }
  return { title: 'Request failed', description: error.detail }
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const { title, description } = describeError(error)
  const Icon = error instanceof ApiError && error.status === 0 ? WifiOff : AlertTriangle

  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-accent-error/30 bg-accent-error/5 p-8 text-center">
      <Icon className="size-6 text-accent-error" aria-hidden="true" />
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}
