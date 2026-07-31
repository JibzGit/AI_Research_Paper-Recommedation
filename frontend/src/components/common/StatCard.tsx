import type { LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'

type Accent = 'purple' | 'blue' | 'green' | 'orange'

interface StatCardProps {
  label: string
  value: string | number
  icon?: LucideIcon
  accent?: Accent
  hint?: string
  /** When set, the whole card becomes a link (internal route) navigating
   * to the relevant filtered/detail view -- e.g. the Papers count links to
   * Paper Search. Omit for stats with no sensible destination. */
  href?: string
}

const ACCENT_CLASSES: Record<Accent, string> = {
  purple: 'bg-accent-purple/10 text-accent-purple',
  blue: 'bg-accent-blue/10 text-accent-blue',
  green: 'bg-accent-green/10 text-accent-green',
  orange: 'bg-accent-orange/10 text-accent-orange',
}

export function StatCard({ label, value, icon: Icon, accent = 'purple', hint, href }: StatCardProps) {
  const content = (
    <>
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
    </>
  )

  if (href) {
    const cardClassName =
      'rounded-2xl border border-border bg-card p-4 shadow-panel transition-colors hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none'
    const ariaLabel = `${label}: ${value}. View details.`

    // A same-page anchor (e.g. "#corpus-coverage") gets a plain <a> so the
    // browser's native hash-scroll behavior applies -- React Router's
    // <Link> would only update the URL without scrolling anywhere.
    if (href.startsWith('#')) {
      return (
        <a href={href} className={cardClassName} aria-label={ariaLabel}>
          {content}
        </a>
      )
    }

    return (
      <Link to={href} className={cardClassName} aria-label={ariaLabel}>
        {content}
      </Link>
    )
  }

  return <div className="rounded-2xl border border-border bg-card p-4 shadow-panel">{content}</div>
}
