import { Search } from 'lucide-react'
import type { SubmitEvent } from 'react'

import { CategorySelect } from '@/components/papers/CategorySelect'
import { ClearFiltersButton } from '@/components/papers/ClearFiltersButton'
import { FilterChip } from '@/components/papers/FilterChip'
import { ResultLimitSelect } from '@/components/papers/ResultLimitSelect'
import { SearchInput } from '@/components/papers/SearchInput'
import { SimilarityThresholdFilter } from '@/components/papers/SimilarityThresholdFilter'
import { YearRangeFilter } from '@/components/papers/YearRangeFilter'
import { Button } from '@/components/ui/button'
import { hasActiveFilters, type SearchFormErrors, type SearchFormValues } from '@/lib/searchParams'

interface PaperSearchFiltersProps {
  values: SearchFormValues
  errors: SearchFormErrors
  onFieldChange: <K extends keyof SearchFormValues>(key: K, value: SearchFormValues[K]) => void
  onSubmit: (event: SubmitEvent<HTMLFormElement>) => void
  onClearFilters: () => void
  isSearching: boolean
}

/** Draft-bound: every control here edits local draft state (passed down
 * from SearchPage), and nothing is sent to the backend or written to the
 * URL until the form is submitted. */
export function PaperSearchFilters({ values, errors, onFieldChange, onSubmit, onClearFilters, isSearching }: PaperSearchFiltersProps) {
  const trimmedQuery = values.query.trim()
  const hasBlockingErrors = Boolean(errors.yearRange || errors.minSimilarity || errors.topK)
  const filtersActive = hasActiveFilters(values)

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel" role="search">
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="flex-1">
          <SearchInput value={values.query} onChange={(next) => onFieldChange('query', next)} />
        </div>
        <Button type="submit" disabled={!trimmedQuery || hasBlockingErrors || isSearching} className="h-11 gap-1.5 sm:w-auto">
          <Search className="size-4" aria-hidden="true" />
          Search
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <CategorySelect value={values.category} onChange={(next) => onFieldChange('category', next)} />
        <YearRangeFilter
          yearFrom={values.yearFrom}
          yearTo={values.yearTo}
          onYearFromChange={(next) => onFieldChange('yearFrom', next)}
          onYearToChange={(next) => onFieldChange('yearTo', next)}
          error={errors.yearRange}
        />
        <SimilarityThresholdFilter
          value={values.minSimilarity}
          onChange={(next) => onFieldChange('minSimilarity', next)}
          error={errors.minSimilarity}
        />
        <ResultLimitSelect value={values.topK} onChange={(next) => onFieldChange('topK', next)} />
      </div>

      {(filtersActive || errors.topK) && (
        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
          {values.category && <FilterChip label={values.category} onRemove={() => onFieldChange('category', null)} />}
          {(values.yearFrom !== null || values.yearTo !== null) && (
            <FilterChip
              label={`${values.yearFrom ?? '…'}–${values.yearTo ?? '…'}`}
              onRemove={() => {
                onFieldChange('yearFrom', null)
                onFieldChange('yearTo', null)
              }}
            />
          )}
          {values.minSimilarity !== null && (
            <FilterChip label={`≥ ${values.minSimilarity.toFixed(2)} similarity`} onRemove={() => onFieldChange('minSimilarity', null)} />
          )}
          {errors.topK && <p className="text-[11px] text-accent-error">{errors.topK}</p>}
          {filtersActive && <ClearFiltersButton onClear={onClearFilters} />}
        </div>
      )}
    </form>
  )
}
