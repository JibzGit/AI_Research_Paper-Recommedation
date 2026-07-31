import { AlertTriangle, ChevronRight, FileSearch, FileX, Layers, Loader2, Sparkles } from 'lucide-react'
import { type SubmitEvent, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { CategoryDistributionChart } from '@/components/charts/CategoryDistributionChart'
import { ClusterEvidenceList } from '@/components/clusters/ClusterEvidenceList'
import { ClusterHeader } from '@/components/clusters/ClusterHeader'
import { ClusterKeywordsPanel } from '@/components/clusters/ClusterKeywordsPanel'
import { ClusterPaperCard } from '@/components/clusters/ClusterPaperCard'
import { ClusterPaperFilters } from '@/components/clusters/ClusterPaperFilters'
import { ClusterRepresentativePapers } from '@/components/clusters/ClusterRepresentativePapers'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton, ChartSkeleton, StatCardSkeleton } from '@/components/common/LoadingSkeleton'
import { PaperPagination } from '@/components/common/PaperPagination'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useClusterDetail } from '@/hooks/useClusterDetail'
import { useClusterPapers } from '@/hooks/useClusterPapers'
import { parseClusterIdParam } from '@/lib/clusterId'
import {
  DEFAULT_CLUSTER_PAPER_FILTER_VALUES,
  clusterPaperFilterValuesFromUrl,
  hasActiveClusterPaperFilters,
  toApiClusterPaperParams,
  urlParamsFromClusterPaperFilters,
  validateClusterPaperFilters,
  type ClusterPaperFilterValues,
} from '@/lib/clusterPaperParams'

const PAPER_SKELETON_COUNT = 4

export function ClusterDetailPage() {
  const { clusterId: clusterIdParam } = useParams<{ clusterId: string }>()
  const clusterId = parseClusterIdParam(clusterIdParam)
  const isValidId = clusterId !== null

  const [searchParams, setSearchParams] = useSearchParams()
  const committedFilters = clusterPaperFilterValuesFromUrl(searchParams)
  const filterKey = searchParams.toString()

  const [draftFilters, setDraftFilters] = useState<ClusterPaperFilterValues>(committedFilters)
  const [syncedFilterKey, setSyncedFilterKey] = useState(filterKey)
  if (filterKey !== syncedFilterKey) {
    setSyncedFilterKey(filterKey)
    setDraftFilters(committedFilters)
  }

  const clusterDetailQuery = useClusterDetail(clusterId ?? undefined, { enabled: isValidId })
  const errors = validateClusterPaperFilters(draftFilters)
  // Sequenced behind cluster-detail succeeding: both endpoints apply the
  // identical existence/approval/latest-run check server-side, so if
  // cluster-detail 404s, cluster-papers would too -- no reason to fire a
  // second guaranteed-redundant request while the page can't render its
  // result anyway (a cluster-detail failure blocks the whole page).
  const clusterPapersQuery = useClusterPapers(clusterId ?? undefined, toApiClusterPaperParams(committedFilters), {
    enabled: isValidId && clusterDetailQuery.isSuccess,
  })

  const papersHeadingRef = useRef<HTMLHeadingElement>(null)

  function handleFieldChange<K extends keyof ClusterPaperFilterValues>(key: K, value: ClusterPaperFilterValues[K]) {
    setDraftFilters((prev) => ({ ...prev, [key]: value }))
  }

  function handleFilterSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const formErrors = validateClusterPaperFilters(draftFilters)
    if (formErrors.minMembershipProbability || formErrors.limit) return
    // The filter form only ever edits category/membership/limit -- any
    // submission of it represents a new filtered view, so it always resets
    // back to the first page.
    setSearchParams(urlParamsFromClusterPaperFilters({ ...draftFilters, offset: 0 }))
  }

  function handleClearFilters() {
    setDraftFilters(DEFAULT_CLUSTER_PAPER_FILTER_VALUES)
    setSearchParams(urlParamsFromClusterPaperFilters(DEFAULT_CLUSTER_PAPER_FILTER_VALUES))
  }

  function handlePageChange(newOffset: number) {
    setSearchParams(urlParamsFromClusterPaperFilters({ ...committedFilters, offset: newOffset }))
    papersHeadingRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    papersHeadingRef.current?.focus()
  }

  // 1. Malformed or negative cluster ID -- never sent to the backend.
  if (!isValidId) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="This cluster link is invalid."
        description="The link you followed doesn't contain a valid cluster identifier."
        action={
          <Button asChild variant="outline" size="sm">
            <Link to="/clusters">Back to Clusters</Link>
          </Button>
        }
      />
    )
  }

  // 2. Cluster detail loading -- blocks the whole page; nothing below it
  // can render meaningfully without the cluster resolving first.
  if (clusterDetailQuery.isLoading) {
    return <ClusterDetailLoadingSkeleton />
  }

  // 3. Cluster detail failed -- also blocks the whole page.
  if (clusterDetailQuery.isError) {
    const error = clusterDetailQuery.error
    if (error?.status === 404) {
      return (
        <EmptyState
          icon={FileX}
          title="This research cluster could not be found."
          description="It may not exist, may not be part of the latest clustering run, or may not have an approved label yet."
          action={
            <Button asChild variant="outline" size="sm">
              <Link to="/clusters">Back to Clusters</Link>
            </Button>
          }
        />
      )
    }
    return <ErrorState error={error ?? new Error('Failed to load cluster')} onRetry={() => void clusterDetailQuery.refetch()} />
  }

  const cluster = clusterDetailQuery.data
  if (!cluster) return null

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs clusterName={cluster.cluster_name} />
      <ClusterHeader cluster={cluster} />

      <div className="grid gap-4 lg:grid-cols-3">
        <section aria-label="Category distribution" className="rounded-2xl border border-border bg-card p-4 shadow-panel lg:col-span-2">
          <h3 className="mb-3 text-sm font-medium text-foreground">Category distribution</h3>
          <p className="sr-only">How this cluster's papers are distributed across arXiv categories.</p>
          <CategoryDistributionChart distribution={cluster.category_distribution} />
        </section>
        <ClusterKeywordsPanel keywords={cluster.keywords} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-label="Representative papers">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
            <Sparkles className="size-4 text-accent-purple" aria-hidden="true" />
            Representative papers
          </h3>
          <ClusterRepresentativePapers papers={cluster.representative_papers} />
        </section>
        <section aria-label="Label evidence">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
            <FileSearch className="size-4 text-accent-blue" aria-hidden="true" />
            Label evidence
          </h3>
          <ClusterEvidenceList evidence={cluster.evidence} representativePapers={cluster.representative_papers} />
        </section>
      </div>

      <section aria-label="Cluster papers">
        <h3
          ref={papersHeadingRef}
          tabIndex={-1}
          className="mb-3 flex items-center gap-2 rounded text-sm font-medium text-foreground focus-visible:outline-none focus:ring-2 focus:ring-ring"
        >
          <Layers className="size-4 text-accent-green" aria-hidden="true" />
          Papers in this cluster
        </h3>
        <div className="flex flex-col gap-3">
          <ClusterPaperFilters
            values={draftFilters}
            errors={errors}
            onFieldChange={handleFieldChange}
            onSubmit={handleFilterSubmit}
            onClearFilters={handleClearFilters}
            isFetching={clusterPapersQuery.isFetching}
          />
          <ClusterPapersSection clusterPapersQuery={clusterPapersQuery} committedFilters={committedFilters} onPageChange={handlePageChange} />
        </div>
      </section>
    </div>
  )
}

function Breadcrumbs({ clusterName }: { clusterName: string }) {
  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
      <Link to="/" className="shrink-0 rounded hover:text-foreground hover:underline focus-visible:outline-none">
        Dashboard
      </Link>
      <ChevronRight className="size-3 shrink-0" aria-hidden="true" />
      <Link to="/clusters" className="shrink-0 rounded hover:text-foreground hover:underline focus-visible:outline-none">
        Research Clusters
      </Link>
      <ChevronRight className="size-3 shrink-0" aria-hidden="true" />
      <span className="truncate text-foreground" aria-current="page">
        {clusterName}
      </span>
    </nav>
  )
}

function ClusterDetailLoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-live="polite">
      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-panel">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-5/6" />
        <div className="flex gap-2">
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="h-5 w-28 rounded-full" />
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ChartSkeleton />
        </div>
        <StatCardSkeleton />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    </div>
  )
}

function ClusterPapersSection({
  clusterPapersQuery,
  committedFilters,
  onPageChange,
}: {
  clusterPapersQuery: ReturnType<typeof useClusterPapers>
  committedFilters: ClusterPaperFilterValues
  onPageChange: (offset: number) => void
}) {
  if (clusterPapersQuery.isLoading) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-live="polite">
        {Array.from({ length: PAPER_SKELETON_COUNT }).map((_, index) => (
          <CardSkeleton key={index} />
        ))}
      </div>
    )
  }

  if (clusterPapersQuery.isError) {
    return (
      <ErrorState
        error={clusterPapersQuery.error ?? new Error('Failed to load cluster papers')}
        onRetry={() => void clusterPapersQuery.refetch()}
      />
    )
  }

  const data = clusterPapersQuery.data
  if (!data) return null

  if (data.papers.length === 0) {
    const filtersActive = hasActiveClusterPaperFilters(committedFilters)
    return (
      <EmptyState
        icon={Layers}
        title="No papers in this cluster matched the selected filters."
        description={filtersActive ? 'Try removing the category filter or lowering the minimum membership threshold.' : undefined}
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {clusterPapersQuery.isFetching && (
        <span className="inline-flex w-fit items-center gap-1.5 text-xs text-muted-foreground" aria-live="polite">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          Updating…
        </span>
      )}
      {data.papers.map((paper) => (
        <ClusterPaperCard key={paper.paper_id} paper={paper} />
      ))}
      {/* itemLabel="papers" preserves the exact visible text this page
       * already had before PaperPagination was generalized out of the old
       * cluster-only ClusterPaperPagination. */}
      <PaperPagination total={data.total} limit={data.limit} offset={data.offset} onPageChange={onPageChange} itemLabel="papers" />
    </div>
  )
}
