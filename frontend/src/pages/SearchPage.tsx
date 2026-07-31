import { Loader2, Search, Sparkles } from 'lucide-react'
import { type SubmitEvent, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton } from '@/components/common/LoadingSkeleton'
import { PaperSearchFilters } from '@/components/papers/PaperSearchFilters'
import { PaperSearchResultCard } from '@/components/papers/PaperSearchResultCard'
import { Button } from '@/components/ui/button'
import { usePaperSearch } from '@/hooks/usePaperSearch'
import {
  DEFAULT_SEARCH_FORM_VALUES,
  searchFormValuesFromUrl,
  toApiSearchParams,
  urlParamsFromSearchForm,
  validateSearchForm,
  type SearchFormValues,
} from '@/lib/searchParams'

const EXAMPLE_QUERIES = [
  'retrieval-augmented generation',
  'medical image segmentation',
  'graph representation learning',
  'event detection from social media',
]

const SKELETON_COUNT = 5

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const committedValues = searchFormValuesFromUrl(searchParams)
  const searchKey = searchParams.toString()

  const [draftValues, setDraftValues] = useState<SearchFormValues>(committedValues)
  const [syncedSearchKey, setSyncedSearchKey] = useState(searchKey)

  // Resync the draft form whenever the URL itself changes (submit, clear,
  // example query, browser back/forward): "adjusting state when a prop
  // changes" during render (React's recommended pattern), not an effect --
  // avoids an extra render pass and the cascading-render lint warning.
  // Free typing never touches searchParams, so this never fights an
  // in-progress edit.
  if (searchKey !== syncedSearchKey) {
    setSyncedSearchKey(searchKey)
    setDraftValues(committedValues)
  }

  const errors = validateSearchForm(draftValues)
  const hasSubmittedQuery = committedValues.query.trim() !== ''
  const searchQuery = usePaperSearch(toApiSearchParams(committedValues))

  function handleFieldChange<K extends keyof SearchFormValues>(key: K, value: SearchFormValues[K]) {
    setDraftValues((prev) => ({ ...prev, [key]: value }))
  }

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draftValues.query.trim()) return
    const formErrors = validateSearchForm(draftValues)
    if (formErrors.yearRange || formErrors.minSimilarity || formErrors.topK) return
    setSearchParams(urlParamsFromSearchForm(draftValues))
  }

  function handleClearFilters() {
    const next: SearchFormValues = {
      ...draftValues,
      category: null,
      yearFrom: null,
      yearTo: null,
      minSimilarity: null,
      topK: DEFAULT_SEARCH_FORM_VALUES.topK,
    }
    setDraftValues(next)
    if (hasSubmittedQuery) setSearchParams(urlParamsFromSearchForm(next))
  }

  function handleExampleQuery(example: string) {
    const next: SearchFormValues = { ...DEFAULT_SEARCH_FORM_VALUES, query: example }
    setDraftValues(next)
    setSearchParams(urlParamsFromSearchForm(next))
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Paper Search</h2>
        <p className="text-sm text-muted-foreground">Semantic search across the canonical paper corpus.</p>
      </div>

      <PaperSearchFilters
        values={draftValues}
        errors={errors}
        onFieldChange={handleFieldChange}
        onSubmit={handleSubmit}
        onClearFilters={handleClearFilters}
        isSearching={searchQuery.isFetching}
      />

      <SearchResults
        hasSubmittedQuery={hasSubmittedQuery}
        committedValues={committedValues}
        searchQuery={searchQuery}
        onExampleQuery={handleExampleQuery}
      />
    </div>
  )
}

function SearchResults({
  hasSubmittedQuery,
  committedValues,
  searchQuery,
  onExampleQuery,
}: {
  hasSubmittedQuery: boolean
  committedValues: SearchFormValues
  searchQuery: ReturnType<typeof usePaperSearch>
  onExampleQuery: (example: string) => void
}) {
  if (!hasSubmittedQuery) {
    return <InitialState onExampleQuery={onExampleQuery} />
  }

  if (searchQuery.isLoading) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-live="polite">
        <p className="text-xs text-muted-foreground">Searching…</p>
        {Array.from({ length: SKELETON_COUNT }).map((_, index) => (
          <CardSkeleton key={index} />
        ))}
      </div>
    )
  }

  if (searchQuery.isError) {
    return <ErrorState error={searchQuery.error ?? new Error('Search failed')} onRetry={() => void searchQuery.refetch()} />
  }

  const data = searchQuery.data
  if (!data) return null

  if (data.count === 0) {
    return (
      <EmptyState
        icon={Search}
        title="No papers matched this search."
        description="Try removing the category filter, widening the year range, lowering the minimum similarity, or using broader wording."
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm text-foreground">
            <span className="font-medium tabular-nums">{data.count}</span> {data.count === 1 ? 'paper' : 'papers'} matching &ldquo;
            {data.query}&rdquo;
          </p>
          <p className="text-xs text-muted-foreground">
            Ranked by semantic similarity
            {committedValues.category && ` · Category: ${committedValues.category}`}
            {(committedValues.yearFrom !== null || committedValues.yearTo !== null) &&
              ` · Years: ${committedValues.yearFrom ?? '…'}–${committedValues.yearTo ?? '…'}`}
          </p>
        </div>
        {searchQuery.isFetching && (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            Searching…
          </span>
        )}
      </div>
      <div className="flex flex-col gap-3">
        {data.results.map((paper) => (
          <PaperSearchResultCard key={paper.paper_id} paper={paper} />
        ))}
      </div>
    </div>
  )
}

function InitialState({ onExampleQuery }: { onExampleQuery: (example: string) => void }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-2xl border border-dashed border-border bg-card/40 p-10 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-accent-purple/10 text-accent-purple">
        <Sparkles className="size-6" aria-hidden="true" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-foreground">Search the research corpus</h3>
        <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
          Describe a topic, method, application, or research problem. Results are ranked using semantic similarity
          across paper titles, abstracts, and categories.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {EXAMPLE_QUERIES.map((example) => (
          <Button key={example} type="button" variant="outline" size="sm" onClick={() => onExampleQuery(example)}>
            {example}
          </Button>
        ))}
      </div>
    </div>
  )
}
