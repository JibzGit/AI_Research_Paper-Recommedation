import { Link } from 'react-router-dom'

import type { ClusterSummary } from '@/api/types'
import { ConfidenceBadge } from '@/components/clusters/ConfidenceBadge'
import { MembershipProbabilityBadge } from '@/components/clusters/MembershipProbabilityBadge'
import { Badge } from '@/components/ui/badge'

interface ClusterCardProps {
  cluster: ClusterSummary
}

const MAX_VISIBLE_KEYWORDS = 4

export function ClusterCard({ cluster }: ClusterCardProps) {
  const keywords = cluster.top_keywords.slice(0, MAX_VISIBLE_KEYWORDS)

  return (
    <Link
      to={`/clusters/${cluster.cluster_id}`}
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel transition-colors hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground">{cluster.cluster_name}</h4>
        <span className="shrink-0 text-xs font-medium text-muted-foreground tabular-nums">
          {cluster.paper_count} papers
        </span>
      </div>

      <p className="line-clamp-2 text-xs text-muted-foreground">{cluster.short_description}</p>

      {cluster.dominant_category && (
        <Badge variant="secondary" className="w-fit text-[11px]">
          {cluster.dominant_category}
        </Badge>
      )}

      {keywords.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {keywords.map((keyword) => (
            <span key={keyword} className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
              {keyword}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto flex flex-wrap gap-1.5 pt-1">
        <ConfidenceBadge value={cluster.label_confidence} />
        <MembershipProbabilityBadge value={cluster.average_membership_probability} />
      </div>
    </Link>
  )
}
