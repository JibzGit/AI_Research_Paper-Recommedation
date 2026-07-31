import { Sparkles } from 'lucide-react'

import type { ApiError } from '@/api/client'
import type { ClusterSummary } from '@/api/types'
import { CardSkeleton } from '@/components/common/LoadingSkeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { RepresentativePaperCard, type RepresentativePaperCardData } from '@/components/papers/RepresentativePaperCard'
import { useClusterDetail } from '@/hooks/useClusterDetail'

interface RepresentativePapersSectionProps {
  /** Already loaded & paper_count-sorted-descending clusters (from
   * useClusters()) -- only the first two are ever fetched further. */
  clusters: ClusterSummary[] | undefined
  clustersLoading: boolean
}

const NO_PAPERS_MESSAGE = 'No representative papers are available for these clusters.'

/**
 * Fetches cluster detail for at most the top 2 clusters (never one request
 * per cluster) and flattens+dedupes their representative_papers by
 * paper_id. Each of the two detail queries fails independently -- one
 * failing degrades gracefully rather than hiding papers the other one
 * successfully loaded.
 */
export function RepresentativePapersSection({ clusters, clustersLoading }: RepresentativePapersSectionProps) {
  const first = clusters?.[0]
  const second = clusters?.[1]

  const firstDetail = useClusterDetail(first?.cluster_id)
  const secondDetail = useClusterDetail(second?.cluster_id)

  if (clustersLoading) {
    return <SkeletonGrid />
  }

  if (!clusters || clusters.length === 0) {
    return <EmptyState icon={Sparkles} title={NO_PAPERS_MESSAGE} />
  }

  const activeQueries = [
    first ? firstDetail : undefined,
    second ? secondDetail : undefined,
  ].filter((query): query is typeof firstDetail => query !== undefined)

  if (activeQueries.some((query) => query.isLoading)) {
    return <SkeletonGrid />
  }

  const allFailed = activeQueries.length > 0 && activeQueries.every((query) => query.isError)
  if (allFailed) {
    const error: ApiError | null = activeQueries[0]?.error ?? null
    if (error) {
      return (
        <ErrorState
          error={error}
          onRetry={() => {
            for (const query of activeQueries) void query.refetch()
          }}
        />
      )
    }
  }

  const papers: RepresentativePaperCardData[] = []
  const seenPaperIds = new Set<string>()
  for (const [detail, summary] of [
    [firstDetail.data, first] as const,
    [secondDetail.data, second] as const,
  ]) {
    if (!detail || !summary) continue
    for (const paper of detail.representative_papers) {
      if (seenPaperIds.has(paper.paper_id)) continue
      seenPaperIds.add(paper.paper_id)
      papers.push({
        paperId: paper.paper_id,
        arxivId: paper.arxiv_id,
        title: paper.title,
        clusterId: summary.cluster_id,
        clusterName: summary.cluster_name,
      })
    }
  }

  if (papers.length === 0) {
    return <EmptyState icon={Sparkles} title={NO_PAPERS_MESSAGE} />
  }

  const partialFailure = !allFailed && activeQueries.some((query) => query.isError)

  return (
    <div className="flex flex-col gap-2">
      {partialFailure && (
        <p className="text-xs text-muted-foreground">
          One leading cluster's representative papers couldn't be loaded -- showing what's available.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {papers.map((paper) => (
          <RepresentativePaperCard key={paper.paperId} paper={paper} />
        ))}
      </div>
    </div>
  )
}

function SkeletonGrid() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <CardSkeleton />
      <CardSkeleton />
    </div>
  )
}
