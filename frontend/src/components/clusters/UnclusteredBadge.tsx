import { Shuffle } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

/** Shown on noise-mode ClusterPaperCards instead of a membership score --
 * ClusterPaper.membership_probability is uniformly 0.0 for every noise
 * paper (enforced by the backend, not a real per-paper fit value), so it's
 * never rendered as "Cluster membership 0%" here. "Noise" appears only as
 * supporting technical terminology in the tooltip, never as the primary
 * label. */
export function UnclusteredBadge() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className="shrink-0 gap-1 border-accent-orange/40 text-accent-orange">
          <Shuffle className="size-3" aria-hidden="true" />
          Unclustered
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        This paper wasn't confidently assigned to a research cluster by the clustering model. Also called a noise
        point in density-based clustering.
      </TooltipContent>
    </Tooltip>
  )
}
