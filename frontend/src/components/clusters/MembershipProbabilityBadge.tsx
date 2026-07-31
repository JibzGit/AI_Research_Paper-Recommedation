import { Target } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface MembershipProbabilityBadgeProps {
  /** 0..1 -- average, across this cluster's papers, of how strongly each
   * paper belongs to it (a per-paper fit score). Never the same thing as
   * label accuracy -- see ConfidenceBadge for that. */
  value: number
}

export function MembershipProbabilityBadge({ value }: MembershipProbabilityBadgeProps) {
  const percent = Math.round(value * 100)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className="gap-1 border-accent-green/40 text-accent-green">
          <Target className="size-3" aria-hidden="true" />
          Avg. membership {percent}%
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        How strongly, on average, this cluster's papers belong to it -- a per-paper fit score, not a
        label-accuracy score.
      </TooltipContent>
    </Tooltip>
  )
}
