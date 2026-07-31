import { Radar } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

export type SimilarityContext = 'query' | 'paper'

const TOOLTIP_TEXT: Record<SimilarityContext, string> = {
  query: "Semantic similarity measures how closely this paper's embedded content matches the search query.",
  paper: "Semantic similarity measures how closely this paper's embedded content matches the selected paper.",
}

interface SimilarityBadgeProps {
  /** PaperResult.similarity_score, cosine similarity in [-1, 1] (in
   * practice close to [0, 1] for real query/passage pairs). Always labeled
   * "Semantic similarity" -- never "confidence," "relevance certainty,"
   * "model accuracy," or "recommendation confidence." */
  value: number
  /** 'query' (default) for Paper Search results, matched against typed
   * text; 'paper' for Similar Papers results, matched against another
   * paper's embedding. Only changes the tooltip wording. */
  context?: SimilarityContext
}

export function SimilarityBadge({ value, context = 'query' }: SimilarityBadgeProps) {
  const percent = Math.round(value * 100)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge tabIndex={0} variant="outline" className="shrink-0 gap-1 border-accent-purple/40 text-accent-purple">
          <Radar className="size-3" aria-hidden="true" />
          Semantic similarity {percent}%
        </Badge>
      </TooltipTrigger>
      <TooltipContent>{TOOLTIP_TEXT[context]}</TooltipContent>
    </Tooltip>
  )
}
