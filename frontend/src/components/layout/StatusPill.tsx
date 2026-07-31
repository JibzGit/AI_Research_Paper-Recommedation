import { useHealth, type HealthStatus } from '@/hooks/useHealth'
import { cn } from '@/lib/utils'

const STATUS_CONFIG: Record<HealthStatus, { label: string; dotClassName: string }> = {
  checking: { label: 'Checking...', dotClassName: 'bg-muted-foreground animate-pulse' },
  connected: { label: 'Connected', dotClassName: 'bg-accent-green' },
  degraded: { label: 'Degraded', dotClassName: 'bg-accent-orange' },
  offline: { label: 'Offline', dotClassName: 'bg-accent-error' },
}

export function StatusPill() {
  const { status } = useHealth()
  const config = STATUS_CONFIG[status]

  return (
    <div
      className="flex items-center gap-2 rounded-lg border border-sidebar-border bg-sidebar-accent/40 px-2.5 py-2 text-xs"
      role="status"
    >
      <span className={cn('size-2 shrink-0 rounded-full', config.dotClassName)} aria-hidden="true" />
      <span className="text-sidebar-foreground">{config.label}</span>
      <span className="ml-auto text-[10px] font-medium tracking-wide text-muted-foreground uppercase">API</span>
    </div>
  )
}
