import { AlertTriangle, Ban, ChevronRight, FileX, Loader2, Sparkles } from 'lucide-react'
import { type SubmitEvent, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'

import type { ApiError } from '@/api/client'
import type { PaperDetail, PaperResult } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton } from '@/components/common/LoadingSkeleton'
import { PaperSearchResultCard } from '@/components/papers/PaperSearchResultCard'
import { SelectedPaperSummary } from '@/components/papers/SelectedPaperSummary'
import { SimilarPaperFilters } from '@/components/papers/SimilarPaperFilters'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { usePaperDetail } from '@/hooks/usePaperDetail'
import { useSimilarPapers } from '@/hooks/useSimilarPapers'
import {
  DEFAULT_FILTER_VALUES,
  filterValuesFromUrl,
  hasActiveFilters,
  toApiFilterParams,
  urlParamsFromFilterValues,
  validateFilterValues,
  type FilterValues,
} from '@/lib/searchParams'
import { isValidUuid } from '@/lib/uuid'

const SKELETON_COUNT = 4

function getSourcePaperFromState(state: unknown): PaperResult | undefined {
  if (state && typeof state === 'object' && 'sourcePaper' in state) {
    const candidate = (state as { sourcePaper?: unknown }).sourcePaper
    if (candidate && typeof candidate === 'object' && 'paper_id' in candidate && 'title' in candidate) {
      return candidate as PaperResult
    }
  }
  return undefined
}

export function SimilarPapersPage() {
  const { paperId } = useParams<{ paperId: string }>()
  const location = useLocation()
  const sourcePaperPreview = getSourcePaperFromState(location.state)

  const [searchParams, setSearchParams] = useSearchParams()
  const committedFilters = filterValuesFromUrl(searchParams)
  const filterKey = searchParams.toString()

  const [draftFilters, setDraftFilters] = useState<FilterValues>(committedFilters)
  const [syncedFilterKey, setSyncedFilterKey] = useState(filterKey)
  if (filterKey !== syncedFilterKey) {
    setSyncedFilterKey(filterKey)
    setDraftFilters(committedFilters)
  }

  const isValidId = isValidUuid(paperId)
  const paperDetailQuery = usePaperDetail(paperId, { enabled: isValidId })

  const errors = validateFilterValues(draftFilters)
  const canFetchSimilar = paperDetailQuery.data?.embedding_available === true
  const similarQuery = useSimilarPapers(paperId, toApiFilterParams(committedFilters), { enabled: canFetchSimilar })

  function handleFieldChange<K extends keyof FilterValues>(key: K, value: FilterValues[K]) {
    setDraftFilters((prev) => ({ ...prev, [key]: value }))
  }

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const formErrors = validateFilterValues(draftFilters)
    if (formErrors.yearRange || formErrors.minSimilarity || formErrors.topK) return
    setSearchParams(urlParamsFromFilterValues(draftFilters))
  }

  function handleClearFilters() {
    setDraftFilters(DEFAULT_FILTER_VALUES)
    setSearchParams(urlParamsFromFilterValues(DEFAULT_FILTER_VALUES))
  }

  // 1. Malformed route param -- never even attempted against the backend.
  if (!isValidId) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="This paper link is invalid."
        description="The link you followed doesn't contain a valid paper identifier."
        action={
          <Button asChild variant="outline" size="sm">
            <Link to="/search">Back to search</Link>
          </Button>
        }
      />
    )
  }

  // 2. Source paper loading -- the nav-state preview (if any) shows the
  // real title immediately as a performance convenience; every other field
  // stays a skeleton rather than guessing values PaperDetail alone
  // provides (current_version_number, embedding_available).
  if (paperDetailQuery.isLoading) {
    return <SourcePaperLoadingCard previewTitle={sourcePaperPreview?.title} />
  }

  // 3. Source paper failed to resolve -- recommendations are impossible
  // without it, so this replaces the whole page rather than just a section.
  if (paperDetailQuery.isError) {
    return <PaperDetailErrorState error={paperDetailQuery.error} onRetry={() => void paperDetailQuery.refetch()} />
  }

  const paper = paperDetailQuery.data
  if (!paper) return null

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs paperTitle={paper.title} />
      <SelectedPaperSummary paper={paper} />

      {paper.embedding_available ? (
        <>
          <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <Sparkles className="size-4 text-accent-purple" aria-hidden="true" />
            Similar papers
          </h3>
          <SimilarPaperFilters
            values={draftFilters}
            errors={errors}
            onFieldChange={handleFieldChange}
            onSubmit={handleSubmit}
            onClearFilters={handleClearFilters}
            isFetching={similarQuery.isFetching}
          />
          <SimilarResults paper={paper} committedFilters={committedFilters} similarQuery={similarQuery} filterQueryString={filterKey} />
        </>
      ) : (
        <EmptyState
          icon={Ban}
          title="Similar-paper recommendations are unavailable"
          description="Similar-paper recommendations are unavailable because this paper does not currently have an active embedding."
        />
      )}
    </div>
  )
}

function Breadcrumbs({ paperTitle }: { paperTitle: string }) {
  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
      <Link to="/search" className="shrink-0 rounded hover:text-foreground hover:underline focus-visible:outline-none">
        Paper Search
      </Link>
      <ChevronRight className="size-3 shrink-0" aria-hidden="true" />
      <span className="truncate text-foreground" aria-current="page">
        {paperTitle}
      </span>
    </nav>
  )
}

function SourcePaperLoadingCard({ previewTitle }: { previewTitle?: string }) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-panel" aria-busy="true" aria-live="polite">
      <Skeleton className="h-4 w-28" />
      {previewTitle ? (
        <h2 className="text-lg font-semibold text-foreground">{previewTitle}</h2>
      ) : (
        <Skeleton className="h-6 w-2/3" />
      )}
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-5/6" />
      <div className="flex gap-2">
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-5 w-24 rounded-full" />
      </div>
      <p className="text-xs text-muted-foreground">Loading paper details…</p>
    </div>
  )
}

function PaperDetailErrorState({ error, onRetry }: { error: ApiError | null; onRetry: () => void }) {
  if (error?.status === 404) {
    return (
      <EmptyState
        icon={FileX}
        title="This paper could not be found."
        description="It may have been removed, or the link may be incorrect."
        action={
          <Button asChild variant="outline" size="sm">
            <Link to="/search">Back to search</Link>
          </Button>
        }
      />
    )
  }
  return <ErrorState error={error ?? new Error('Failed to load paper')} onRetry={onRetry} />
}

function SimilarResults({
  paper,
  committedFilters,
  similarQuery,
  filterQueryString,
}: {
  paper: PaperDetail
  committedFilters: FilterValues
  similarQuery: ReturnType<typeof useSimilarPapers>
  filterQueryString: string
}) {
  if (similarQuery.isLoading) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-live="polite">
        <p className="text-xs text-muted-foreground">Finding similar papers…</p>
        {Array.from({ length: SKELETON_COUNT }).map((_, index) => (
          <CardSkeleton key={index} />
        ))}
      </div>
    )
  }

  if (similarQuery.isError) {
    // The one 400 sub-case with a genuinely structured signal
    // (embedding-missing) is already handled above via
    // paper.embedding_available, before this query ever runs. A 400
    // reaching here is the rarer non-canonical/other business-rule case;
    // the backend exposes no structured error code to distinguish it
    // further, so its own detail text is shown as-is rather than guessed
    // at via message matching.
    return <ErrorState error={similarQuery.error ?? new Error('Failed to load similar papers')} onRetry={() => void similarQuery.refetch()} />
  }

  const data = similarQuery.data
  if (!data) return null

  if (data.count === 0) {
    const filtersActive = hasActiveFilters(committedFilters)
    return (
      <EmptyState
        icon={Sparkles}
        title={filtersActive ? 'No similar papers matched these filters.' : 'No similar papers are currently available.'}
        description={
          filtersActive
            ? 'Try removing the category filter, widening the year range, lowering the minimum similarity, or increasing the result limit.'
            : undefined
        }
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm text-foreground">
            <span className="font-medium tabular-nums">{data.count}</span> {data.count === 1 ? 'paper' : 'papers'} similar to &ldquo;
            {paper.title}&rdquo;
          </p>
          <p className="text-xs text-muted-foreground">
            Ranked by semantic similarity to the selected paper
            {committedFilters.category && ` · Category: ${committedFilters.category}`}
            {(committedFilters.yearFrom !== null || committedFilters.yearTo !== null) &&
              ` · Years: ${committedFilters.yearFrom ?? '…'}–${committedFilters.yearTo ?? '…'}`}
          </p>
        </div>
        {similarQuery.isFetching && (
          <span className="inline-flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground" aria-live="polite">
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            Updating…
          </span>
        )}
      </div>
      <div className="flex flex-col gap-3">
        {data.results.map((result) => (
          <PaperSearchResultCard
            key={result.paper_id}
            paper={result}
            mode="similar"
            similarPapersHref={`/papers/${result.paper_id}/similar${filterQueryString ? `?${filterQueryString}` : ''}`}
          />
        ))}
      </div>
    </div>
  )
}
