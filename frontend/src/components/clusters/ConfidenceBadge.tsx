import { Tag } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface ConfidenceBadgeProps {
  /** 0..1 -- how accurately the LLM-generated name/description describes
   * this cluster's contents. Never the same thing as how well individual
   * papers fit the cluster -- see MembershipProbabilityBadge for that. */
  value: number
}

export function ConfidenceBadge({ value }: ConfidenceBadgeProps) {
  const percent = Math.round(value * 100)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className="gap-1 border-accent-blue/40 text-accent-blue">
          <Tag className="size-3" aria-hidden="true" />
          Label confidence {percent}%
        </Badge>
      </TooltipTrigger>
      <TooltipContent>How accurately the generated name describes this cluster's contents.</TooltipContent>
    </Tooltip>
  )
}
