import { ChevronRight, Loader2 } from 'lucide-react'
import { type SubmitEvent, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import type { TrendListResponse, TrendResult } from '@/api/types'
import { CardSkeleton, ChartSkeleton } from '@/components/common/LoadingSkeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { PaperPagination } from '@/components/common/PaperPagination'
import { CohortComparisonChart } from '@/components/trends/CohortComparisonChart'
import { FreshnessStatusBadge } from '@/components/trends/FreshnessStatusBadge'
import { HistoricalCohortWarning } from '@/components/trends/HistoricalCohortWarning'
import { TrendClassificationDistributionChart } from '@/components/trends/TrendClassificationDistributionChart'
import { TrendFilters } from '@/components/trends/TrendFilters'
import { TrendResultCard } from '@/components/trends/TrendResultCard'
import { useCategoryTrends } from '@/hooks/useCategoryTrends'
import { useClusterTrends } from '@/hooks/useClusterTrends'
import { useTrendsOverview } from '@/hooks/useTrendsOverview'
import {
  DEFAULT_TREND_FILTER_VALUES,
  hasActiveTrendFilters,
  toApiTrendParams,
  trendFilterValuesFromUrl,
  type TrendEntityTab,
  type TrendFilterValues,
  urlParamsFromTrendFilters,
  validateTrendFilters,
} from '@/lib/trendParams'

const TOP_MOVERS_CHART_COUNT = 8

export function TrendsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const committedFilters = trendFilterValuesFromUrl(searchParams)
  const filterKey = searchParams.toString()

  const [draftFilters, setDraftFilters] = useState<TrendFilterValues>(committedFilters)
  const [syncedFilterKey, setSyncedFilterKey] = useState(filterKey)
  if (filterKey !== syncedFilterKey) {
    setSyncedFilterKey(filterKey)
    setDraftFilters(committedFilters)
  }

  const errors = validateTrendFilters(draftFilters)
  const headingRef = useRef<HTMLHeadingElement>(null)

  const overviewQuery = useTrendsOverview()
  const runId = overviewQuery.data?.trend_context.run_id

  const listParams = toApiTrendParams(committedFilters, runId)
  const clusterQuery = useClusterTrends(listParams, { enabled: committedFilters.entityTab === 'cluster' })
  const categoryQuery = useCategoryTrends(listParams, { enabled: committedFilters.entityTab === 'category' })
  const activeListQuery = committedFilters.entityTab === 'cluster' ? clusterQuery : categoryQuery

  function handleFieldChange<K extends keyof TrendFilterValues>(key: K, value: TrendFilterValues[K]) {
    setDraftFilters((prev) => ({ ...prev, [key]: value }))
  }

  function handleSortChange(sortBy: TrendFilterValues['sortBy'], sortOrder: TrendFilterValues['sortOrder']) {
    setDraftFilters((prev) => ({ ...prev, sortBy, sortOrder }))
  }

  function handleFilterSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const formErrors = validateTrendFilters(draftFilters)
    if (formErrors.minScore || formErrors.limit) return
    setSearchParams(urlParamsFromTrendFilters({ ...draftFilters, offset: 0 }))
  }

  function handleClearFilters() {
    const cleared: TrendFilterValues = { ...DEFAULT_TREND_FILTER_VALUES, entityTab: committedFilters.entityTab }
    setDraftFilters(cleared)
    setSearchParams(urlParamsFromTrendFilters(cleared))
  }

  function handleTabChange(entityTab: TrendEntityTab) {
    setSearchParams(urlParamsFromTrendFilters({ ...committedFilters, entityTab, offset: 0 }))
  }

  function handlePageChange(newOffset: number) {
    setSearchParams(urlParamsFromTrendFilters({ ...committedFilters, offset: newOffset }))
    headingRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    headingRef.current?.focus()
  }

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs />
      <PageHeader query={overviewQuery} headingRef={headingRef} />

      {overviewQuery.data && (
        <>
          <MoversSection title="Emerging" results={overviewQuery.data.top_emerging} />
          <MoversSection title="Stable" results={overviewQuery.data.top_stable} />
          <MoversSection title="Cooling" results={overviewQuery.data.top_cooling} />

          <section className="rounded-2xl border border-border bg-card p-4 shadow-panel" aria-label="Classification distribution">
            <h3 className="mb-3 text-sm font-medium text-foreground">
              {committedFilters.entityTab === 'cluster' ? 'Cluster' : 'Category'} classification distribution
            </h3>
            <TrendClassificationDistributionChart
              classificationCounts={
                (committedFilters.entityTab === 'cluster'
                  ? overviewQuery.data.cluster_summary
                  : overviewQuery.data.category_summary
                ).classification_counts
              }
            />
          </section>
        </>
      )}

      <EntityTabs activeTab={committedFilters.entityTab} onChange={handleTabChange} />

      <TrendFilters
        values={draftFilters}
        errors={errors}
        onFieldChange={handleFieldChange}
        onSortChange={handleSortChange}
        onSubmit={handleFilterSubmit}
        onClearFilters={handleClearFilters}
        isFetching={activeListQuery.isFetching}
      />

      <ResultsSection query={activeListQuery} committedFilters={committedFilters} onPageChange={handlePageChange} />
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
      <span className="truncate text-foreground" aria-current="page">
        Research Trends
      </span>
    </nav>
  )
}

function PageHeader({
  query,
  headingRef,
}: {
  query: ReturnType<typeof useTrendsOverview>
  headingRef: React.RefObject<HTMLHeadingElement | null>
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
          Research Trends
        </h2>
        {query.data && <FreshnessStatusBadge status={query.data.trend_context.freshness_status} />}
      </div>

      <p className="text-sm text-muted-foreground">
        Publication-based trend signals for research clusters and arXiv categories, calculated from persisted trend
        analysis results.
      </p>

      {query.isLoading && (
        <div aria-busy="true" aria-live="polite">
          <ChartSkeleton />
        </div>
      )}
      {query.isError && <ErrorState error={query.error ?? new Error('Failed to load trend overview')} onRetry={() => void query.refetch()} />}
      {query.data && <HistoricalCohortWarning trendContext={query.data.trend_context} message={query.data.message} />}
    </div>
  )
}

function MoversSection({ title, results }: { title: string; results: TrendResult[] }) {
  if (results.length === 0) return null
  return (
    <section aria-label={`Top ${title.toLowerCase()} entities`}>
      <h3 className="mb-2 text-sm font-medium text-foreground">{title}</h3>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {results.map((result) => (
          <TrendResultCard key={`${result.entity_type}-${result.entity_id}`} result={result} />
        ))}
      </div>
    </section>
  )
}

function EntityTabs({ activeTab, onChange }: { activeTab: TrendEntityTab; onChange: (tab: TrendEntityTab) => void }) {
  return (
    <div className="flex w-fit gap-1 rounded-lg bg-muted p-[3px]" role="tablist" aria-label="Trend entity type">
      {(['cluster', 'category'] as const).map((tab) => (
        <button
          key={tab}
          type="button"
          role="tab"
          aria-selected={activeTab === tab}
          onClick={() => onChange(tab)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
            activeTab === tab ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {tab === 'cluster' ? 'Clusters' : 'Categories'}
        </button>
      ))}
    </div>
  )
}

function ResultsSection({
  query,
  committedFilters,
  onPageChange,
}: {
  query: ReturnType<typeof useClusterTrends> | ReturnType<typeof useCategoryTrends>
  committedFilters: TrendFilterValues
  onPageChange: (offset: number) => void
}) {
  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-live="polite">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    )
  }

  if (query.isError) {
    return <ErrorState error={query.error ?? new Error('Failed to load trend results')} onRetry={() => void query.refetch()} />
  }

  const data: TrendListResponse | undefined = query.data
  if (!data) return null

  if (data.results.length === 0) {
    const filtersActive = hasActiveTrendFilters(committedFilters)
    return (
      <EmptyState
        title={filtersActive ? 'No trend results matched these filters.' : 'No trend results are available yet.'}
        description={filtersActive ? 'Clear the filters to see all results for this entity type.' : undefined}
      />
    )
  }

  const topMovers = [...data.results].sort((a, b) => b.score.trend_score - a.score.trend_score).slice(0, TOP_MOVERS_CHART_COUNT)

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-2xl border border-border bg-card p-4 shadow-panel" aria-label="Cohort comparison">
        <h3 className="mb-3 text-sm font-medium text-foreground">
          Comparison vs. recent cohort &mdash; top {topMovers.length} by trend score (this page)
        </h3>
        <CohortComparisonChart results={topMovers} />
      </section>

      <div className="flex flex-col gap-3">
        {query.isFetching && (
          <span className="inline-flex w-fit items-center gap-1.5 text-xs text-muted-foreground" aria-live="polite">
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            Updating&hellip;
          </span>
        )}
        <h3 className="sr-only">Trend results</h3>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {data.results.map((result) => (
            <TrendResultCard key={`${result.entity_type}-${result.entity_id}`} result={result} />
          ))}
        </div>
        <PaperPagination total={data.total} limit={data.limit} offset={data.offset} onPageChange={onPageChange} itemLabel="trend results" />
      </div>
    </div>
  )
}
