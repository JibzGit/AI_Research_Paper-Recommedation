import { useEffect, useRef } from 'react'

import type { ClusterDetail } from '@/api/types'
import { ConfidenceBadge } from '@/components/clusters/ConfidenceBadge'
import { MembershipProbabilityBadge } from '@/components/clusters/MembershipProbabilityBadge'
import { CategoryBadge } from '@/components/papers/CategoryBadge'

interface ClusterHeaderProps {
  cluster: ClusterDetail
}

/** ClusterDetail (unlike ClusterSummary) has no dominant_category field --
 * category_distribution is already sorted by count descending server-side
 * (research_platform/clustering/queries.py: _category_distribution orders
 * by count desc), so its first entry is the real dominant category, not a
 * guess or an invented field. */
export function ClusterHeader({ cluster }: ClusterHeaderProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [cluster.cluster_id])

  const dominantCategory = cluster.category_distribution[0]?.category

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-2">
        {/* h2, not h1: TopBar already renders the page's one document h1. */}
        <h2
          ref={headingRef}
          tabIndex={-1}
          className="rounded text-lg font-semibold text-foreground focus-visible:outline-none focus:ring-2 focus:ring-ring"
        >
          {cluster.cluster_name}
        </h2>
        <span className="shrink-0 text-xs font-medium text-muted-foreground tabular-nums">{cluster.paper_count} papers</span>
      </div>

      <p className="text-sm text-muted-foreground">{cluster.short_description}</p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
        {dominantCategory && <CategoryBadge category={dominantCategory} />}
        <span className="truncate" title={cluster.clustering_run_id}>
          Run {cluster.clustering_run_id.slice(0, 8)}
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5 pt-1">
        <ConfidenceBadge value={cluster.label_confidence} />
        <MembershipProbabilityBadge value={cluster.average_membership_probability} />
      </div>
    </div>
  )
}
