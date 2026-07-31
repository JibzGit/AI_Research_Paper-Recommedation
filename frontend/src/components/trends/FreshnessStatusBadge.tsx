import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

interface FreshnessStyle {
  label: string
  accentClassName: string
  description: string
}

const STYLES: Record<string, FreshnessStyle> = {
  CURRENT: {
    label: 'Freshness: Current',
    accentClassName: 'border-accent-green/40 text-accent-green',
    description: 'The corpus has enough recent, well-spread publication activity to support a live trend window.',
  },
  PARTIALLY_CURRENT: {
    label: 'Freshness: Partially current',
    accentClassName: 'border-accent-orange/40 text-accent-orange',
    description:
      'Recent papers exist, but there is no reliable comparison-period baseline yet (or recent activity is concentrated on very few days) -- growth cannot be computed against "now".',
  },
  HISTORICAL_ONLY: {
    label: 'Freshness: Historical only',
    accentClassName: 'border-border text-muted-foreground',
    description: 'No papers have been published recently enough for a current-trend window to contain any data.',
  },
  INSUFFICIENT_DATA: {
    label: 'Freshness: Insufficient data',
    accentClassName: 'border-accent-error/40 text-accent-error',
    description: 'The corpus does not contain enough canonical papers to support trend analysis of any kind.',
  },
}

interface FreshnessStatusBadgeProps {
  status: string
}

/** freshness_status describes the whole corpus, not any one entity -- this
 * is why Current Trend Mode is unavailable and every result on this page
 * is a Historical Cohort Comparison instead (see HistoricalCohortWarning).
 * Falls back to a plain neutral badge for any status value this frontend
 * doesn't yet recognize, rather than hiding it. */
export function FreshnessStatusBadge({ status }: FreshnessStatusBadgeProps) {
  const style = STYLES[status] ?? {
    label: `Freshness: ${status}`,
    accentClassName: 'border-border text-muted-foreground',
    description: 'Corpus-wide freshness status for this trend run.',
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge tabIndex={0} variant="outline" className={cn('shrink-0 text-[11px]', style.accentClassName)}>
          {style.label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent>{style.description}</TooltipContent>
    </Tooltip>
  )
}
