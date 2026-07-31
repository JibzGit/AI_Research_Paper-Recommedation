import { CircleAlert, type LucideIcon } from 'lucide-react'

import type { TrendDataQuality } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

interface QualityStyle {
  label: string
  accentClassName: string
  description: string
}

/** Deliberately quieter than TrendClassificationBadge -- data quality is a
 * meta-signal about how much to trust a score, not the finding itself
 * (see the trend-score-vs-confidence distinction in the backend design).
 * Only LOW/INSUFFICIENT get a visible accent color; HIGH/MEDIUM stay
 * neutral so a "good" quality reading never competes visually with the
 * actual trend classification badge next to it. */
const STYLES: Record<TrendDataQuality, QualityStyle> = {
  HIGH: {
    label: 'Data quality: High',
    accentClassName: 'border-border text-muted-foreground',
    description: 'Both cohorts clear the minimum paper count, and recent activity is spread across many days.',
  },
  MEDIUM: {
    label: 'Data quality: Medium',
    accentClassName: 'border-border text-muted-foreground',
    description: 'Support thresholds are met, but there is not yet a broad, multi-window history to lean on.',
  },
  LOW: {
    label: 'Data quality: Low',
    accentClassName: 'border-accent-orange/40 text-accent-orange',
    description: 'The comparison-period count is thin, or recent activity is concentrated on very few calendar days.',
  },
  INSUFFICIENT: {
    label: 'Data quality: Insufficient',
    accentClassName: 'border-accent-error/40 text-accent-error',
    description: 'This entity falls below the minimum total paper count required for any trend reading.',
  },
}

interface DataQualityBadgeProps {
  level: TrendDataQuality
}

const ICON: LucideIcon = CircleAlert

export function DataQualityBadge({ level }: DataQualityBadgeProps) {
  const style = STYLES[level]

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge tabIndex={0} variant="outline" className={cn('shrink-0 gap-1 text-[11px]', style.accentClassName)}>
          {(level === 'LOW' || level === 'INSUFFICIENT') && <ICON className="size-3" aria-hidden="true" />}
          {style.label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent>{style.description}</TooltipContent>
    </Tooltip>
  )
}
