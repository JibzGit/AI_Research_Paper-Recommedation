import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

type Accent = 'purple' | 'blue' | 'green' | 'orange'

interface StatCardProps {
  label: string
  value: string | number
  icon?: LucideIcon
  accent?: Accent
  hint?: string
}

const ACCENT_CLASSES: Record<Accent, string> = {
  purple: 'bg-accent-purple/10 text-accent-purple',
  blue: 'bg-accent-blue/10 text-accent-blue',
  green: 'bg-accent-green/10 text-accent-green',
  orange: 'bg-accent-orange/10 text-accent-orange',
}

export function StatCard({ label, value, icon: Icon, accent = 'purple', hint }: StatCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
        {Icon && (
          <div className={cn('flex size-7 shrink-0 items-center justify-center rounded-lg', ACCENT_CLASSES[accent])}>
            <Icon className="size-4" aria-hidden="true" />
          </div>
        )}
      </div>
      <p className="mt-2 text-2xl font-semibold text-foreground tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}
