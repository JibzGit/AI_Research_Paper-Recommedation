import { ChevronRight, Loader2, Shuffle } from 'lucide-react'
import { type RefObject, type SubmitEvent, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ClusterPaperCard } from '@/components/clusters/ClusterPaperCard'
import { NoisePaperFilters } from '@/components/clusters/NoisePaperFilters'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton } from '@/components/common/LoadingSkeleton'
import { PaperPagination } from '@/components/common/PaperPagination'
import { Button } from '@/components/ui/button'
import { useNoisePapers } from '@/hooks/useNoisePapers'
import {
  DEFAULT_NOISE_PAPER_FILTER_VALUES,
  hasActiveNoisePaperFilters,
  noisePaperFilterValuesFromUrl,
  toApiNoisePaperParams,
  urlParamsFromNoisePaperFilters,
  validateNoisePaperFilters,
  type NoisePaperFilterValues,
} from '@/lib/noisePaperParams'

const PAPER_SKELETON_COUNT = 4

export function NoisePapersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const committedFilters = noisePaperFilterValuesFromUrl(searchParams)
  const filterKey = searchParams.toString()

  const [draftFilters, setDraftFilters] = useState<NoisePaperFilterValues>(committedFilters)
  const [syncedFilterKey, setSyncedFilterKey] = useState(filterKey)
  if (filterKey !== syncedFilterKey) {
    setSyncedFilterKey(filterKey)
    setDraftFilters(committedFilters)
  }

  const errors = validateNoisePaperFilters(draftFilters)
  const noisePapersQuery = useNoisePapers(toApiNoisePaperParams(committedFilters))

  const headingRef = useRef<HTMLHeadingElement>(null)

  function handleFieldChange<K extends keyof NoisePaperFilterValues>(key: K, value: NoisePaperFilterValues[K]) {
    setDraftFilters((prev) => ({ ...prev, [key]: value }))
  }

  function handleFilterSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const formErrors = validateNoisePaperFilters(draftFilters)
    if (formErrors.limit) return
    // The filter form only ever edits category/limit -- any submission of
    // it represents a new filtered view, so it always resets to page 1.
    setSearchParams(urlParamsFromNoisePaperFilters({ ...draftFilters, offset: 0 }))
  }

  function handleClearFilters() {
    setDraftFilters(DEFAULT_NOISE_PAPER_FILTER_VALUES)
    setSearchParams(urlParamsFromNoisePaperFilters(DEFAULT_NOISE_PAPER_FILTER_VALUES))
  }

  function handlePageChange(newOffset: number) {
    setSearchParams(urlParamsFromNoisePaperFilters({ ...committedFilters, offset: newOffset }))
    headingRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    headingRef.current?.focus()
  }

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs />
      <PageHeader query={noisePapersQuery} headingRef={headingRef} />

      <NoisePaperFilters
        values={draftFilters}
        errors={errors}
        onFieldChange={handleFieldChange}
        onSubmit={handleFilterSubmit}
        onClearFilters={handleClearFilters}
        isFetching={noisePapersQuery.isFetching}
      />

      <NoisePapersSection query={noisePapersQuery} committedFilters={committedFilters} onPageChange={handlePageChange} />
    </div>
  )
}

function Breadcrumbs() {
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
        Unclustered Papers
      </span>
    </nav>
  )
}

function PageHeader({
  query,
  headingRef,
}: {
  query: ReturnType<typeof useNoisePapers>
  headingRef: RefObject<HTMLHeadingElement | null>
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-2">
        {/* h2, not h1: TopBar already renders the page's one document h1. */}
        <h2
          ref={headingRef}
          tabIndex={-1}
          className="rounded text-lg font-semibold text-foreground focus-visible:outline-none focus:ring-2 focus:ring-ring"
        >
          Unclustered Papers
        </h2>
        {query.data && (
          <span className="shrink-0 text-xs font-medium text-muted-foreground tabular-nums">{query.data.total} papers</span>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        Unclustered papers are papers that were not assigned confidently to one of the current research clusters.
        This does not indicate low quality or irrelevance; it only reflects the current clustering model and
        dataset.
      </p>
      <p className="text-xs text-muted-foreground/70">Also called noise points in density-based clustering.</p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
        {query.data?.clustering_run_id && (
          <span className="truncate" title={query.data.clustering_run_id}>
            Run {query.data.clustering_run_id.slice(0, 8)}
          </span>
        )}
        <Link to="/clusters" className="rounded hover:text-foreground hover:underline focus-visible:outline-none">
          Research Clusters
        </Link>
        <Link to="/" className="rounded hover:text-foreground hover:underline focus-visible:outline-none">
          Dashboard
        </Link>
      </div>
    </div>
  )
}

function NoisePapersSection({
  query,
  committedFilters,
  onPageChange,
}: {
  query: ReturnType<typeof useNoisePapers>
  committedFilters: NoisePaperFilterValues
  onPageChange: (offset: number) => void
}) {
  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-live="polite">
        {Array.from({ length: PAPER_SKELETON_COUNT }).map((_, index) => (
          <CardSkeleton key={index} />
        ))}
      </div>
    )
  }

  if (query.isError) {
    return <ErrorState error={query.error ?? new Error('Failed to load unclustered papers')} onRetry={() => void query.refetch()} />
  }

  const data = query.data
  if (!data) return null

  if (data.papers.length === 0) {
    const filtersActive = hasActiveNoisePaperFilters(committedFilters)
    return (
      <EmptyState
        icon={Shuffle}
        title={
          filtersActive
            ? 'No unclustered papers matched this category.'
            : 'All papers in the latest clustering run were assigned to research clusters.'
        }
        description={filtersActive ? 'Clear the category filter to see all unclustered papers, or browse research clusters instead.' : undefined}
        action={
          <Button asChild variant="outline" size="sm">
            <Link to="/clusters">Browse research clusters</Link>
          </Button>
        }
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {query.isFetching && (
        <span className="inline-flex w-fit items-center gap-1.5 text-xs text-muted-foreground" aria-live="polite">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          Updating…
        </span>
      )}
      {data.papers.map((paper) => (
        <ClusterPaperCard key={paper.paper_id} paper={paper} mode="noise" />
      ))}
      <PaperPagination total={data.total} limit={data.limit} offset={data.offset} onPageChange={onPageChange} itemLabel="unclustered papers" />
    </div>
  )
}
