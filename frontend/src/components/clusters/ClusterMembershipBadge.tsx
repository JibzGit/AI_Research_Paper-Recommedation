import { Target } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface ClusterMembershipBadgeProps {
  /** ClusterPaper.membership_probability, 0..1 -- how strongly this one
   * paper belongs to the cluster it's shown under. Same underlying concept
   * as MembershipProbabilityBadge (hence the shared green/Target styling)
   * but per-paper rather than a cluster-wide average -- never "semantic
   * similarity," "label confidence," "search confidence," or
   * "recommendation confidence." */
  value: number
}

export function ClusterMembershipBadge({ value }: ClusterMembershipBadgeProps) {
  const percent = Math.round(value * 100)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className="shrink-0 gap-1 border-accent-green/40 text-accent-green">
          <Target className="size-3" aria-hidden="true" />
          Cluster membership {percent}%
        </Badge>
      </TooltipTrigger>
      <TooltipContent>Cluster membership measures how strongly this paper belongs to the selected research cluster.</TooltipContent>
    </Tooltip>
  )
}
