import { Activity, HelpCircle, Minus, TrendingDown, TrendingUp, Zap, type LucideIcon } from 'lucide-react'

import type { TrendClassification } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

interface ClassificationStyle {
  icon: LucideIcon
  accentClassName: string
  description: string
}

/** Emerging/Cooling use the existing green/orange "signal" accents since
 * they represent real growth or decline. Stable and Insufficient Data
 * deliberately use a neutral (muted-foreground) treatment rather than
 * borrowing a signal color -- neither one is a positive or negative
 * finding, and giving them a colored accent would overstate that. */
const STYLES: Record<TrendClassification, ClassificationStyle> = {
  Emerging: {
    icon: TrendingUp,
    accentClassName: 'border-accent-green/40 text-accent-green',
    description: 'New activity with real recent volume and no prior-period baseline to compare against.',
  },
  Accelerating: {
    icon: Zap,
    accentClassName: 'border-accent-purple/40 text-accent-purple',
    description: 'Strong positive growth that is itself speeding up across consecutive comparison windows.',
  },
  'Consistently Active': {
    icon: Activity,
    accentClassName: 'border-accent-blue/40 text-accent-blue',
    description: 'Shows up window after window with flat-to-moderate growth, not just a single spike.',
  },
  Stable: {
    icon: Minus,
    accentClassName: 'border-border text-muted-foreground',
    description: 'Roughly the same publication volume in both cohorts -- neither growing nor shrinking.',
  },
  Cooling: {
    icon: TrendingDown,
    accentClassName: 'border-accent-orange/40 text-accent-orange',
    description: 'Meaningfully less publication volume in the recent cohort than in the comparison cohort.',
  },
  'Insufficient Data': {
    icon: HelpCircle,
    accentClassName: 'border-border text-muted-foreground',
    description: 'Too few papers in this entity, or in one of the two cohorts, to classify a trend reliably.',
  },
}

interface TrendClassificationBadgeProps {
  classification: TrendClassification
}

export function TrendClassificationBadge({ classification }: TrendClassificationBadgeProps) {
  const style = STYLES[classification]
  const Icon = style.icon

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge tabIndex={0} variant="outline" className={cn('shrink-0 gap-1', style.accentClassName)}>
          <Icon className="size-3" aria-hidden="true" />
          {classification}
        </Badge>
      </TooltipTrigger>
      <TooltipContent>{style.description}</TooltipContent>
    </Tooltip>
  )
}
