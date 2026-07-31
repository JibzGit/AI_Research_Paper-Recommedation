import { SlidersHorizontal } from 'lucide-react'
import type { SubmitEvent } from 'react'

import { CategorySelect } from '@/components/papers/CategorySelect'
import { ClearFiltersButton } from '@/components/papers/ClearFiltersButton'
import { FilterChip } from '@/components/papers/FilterChip'
import { ResultLimitSelect } from '@/components/papers/ResultLimitSelect'
import { Button } from '@/components/ui/button'
import { hasActiveNoisePaperFilters, type NoisePaperFilterErrors, type NoisePaperFilterValues } from '@/lib/noisePaperParams'

interface NoisePaperFiltersProps {
  values: NoisePaperFilterValues
  errors: NoisePaperFilterErrors
  onFieldChange: <K extends keyof NoisePaperFilterValues>(key: K, value: NoisePaperFilterValues[K]) => void
  onSubmit: (event: SubmitEvent<HTMLFormElement>) => void
  onClearFilters: () => void
  isFetching: boolean
}

/** No membership threshold, similarity threshold, year range, or text
 * search -- GET /clusters/noise supports only limit/offset/category.
 * CategorySelect, ClearFiltersButton, FilterChip, and ResultLimitSelect
 * are reused unchanged from Paper Search / Cluster Detail. */
export function NoisePaperFilters({ values, errors, onFieldChange, onSubmit, onClearFilters, isFetching }: NoisePaperFiltersProps) {
  const filtersActive = hasActiveNoisePaperFilters(values)

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <CategorySelect value={values.category} onChange={(next) => onFieldChange('category', next)} />
        <ResultLimitSelect value={values.limit} onChange={(next) => onFieldChange('limit', next)} />
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button type="submit" size="sm" disabled={Boolean(errors.limit) || isFetching} className="gap-1.5">
          <SlidersHorizontal className="size-3.5" aria-hidden="true" />
          Apply filters
        </Button>
        {values.category && <FilterChip label={values.category} onRemove={() => onFieldChange('category', null)} />}
        {errors.limit && <p className="text-[11px] text-accent-error">{errors.limit}</p>}
        {filtersActive && <ClearFiltersButton onClear={onClearFilters} />}
      </div>
    </form>
  )
}
