import { SlidersHorizontal } from 'lucide-react'
import type { SubmitEvent } from 'react'

import { CategorySelect } from '@/components/papers/CategorySelect'
import { ClearFiltersButton } from '@/components/papers/ClearFiltersButton'
import { FilterChip } from '@/components/papers/FilterChip'
import { ResultLimitSelect } from '@/components/papers/ResultLimitSelect'
import { SimilarityThresholdFilter } from '@/components/papers/SimilarityThresholdFilter'
import { YearRangeFilter } from '@/components/papers/YearRangeFilter'
import { Button } from '@/components/ui/button'
import { hasActiveFilters, type FilterErrors, type FilterValues } from '@/lib/searchParams'

interface SimilarPaperFiltersProps {
  values: FilterValues
  errors: FilterErrors
  onFieldChange: <K extends keyof FilterValues>(key: K, value: FilterValues[K]) => void
  onSubmit: (event: SubmitEvent<HTMLFormElement>) => void
  onClearFilters: () => void
  isFetching: boolean
}

/** Same filter fields and draft/submit-to-URL convention as
 * PaperSearchFilters, minus the free-text query input -- similarity here
 * comes from the selected paper's stored embedding, not a typed query. */
export function SimilarPaperFilters({ values, errors, onFieldChange, onSubmit, onClearFilters, isFetching }: SimilarPaperFiltersProps) {
  const hasBlockingErrors = Boolean(errors.yearRange || errors.minSimilarity || errors.topK)
  const filtersActive = hasActiveFilters(values)

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
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

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button type="submit" size="sm" disabled={hasBlockingErrors || isFetching} className="gap-1.5">
          <SlidersHorizontal className="size-3.5" aria-hidden="true" />
          Apply filters
        </Button>
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
    </form>
  )
}
