import { SlidersHorizontal } from 'lucide-react'
import type { SubmitEvent } from 'react'

import { MembershipThresholdFilter } from '@/components/clusters/MembershipThresholdFilter'
import { CategorySelect } from '@/components/papers/CategorySelect'
import { ClearFiltersButton } from '@/components/papers/ClearFiltersButton'
import { FilterChip } from '@/components/papers/FilterChip'
import { ResultLimitSelect } from '@/components/papers/ResultLimitSelect'
import { Button } from '@/components/ui/button'
import { hasActiveClusterPaperFilters, type ClusterPaperFilterErrors, type ClusterPaperFilterValues } from '@/lib/clusterPaperParams'

interface ClusterPaperFiltersProps {
  values: ClusterPaperFilterValues
  errors: ClusterPaperFilterErrors
  onFieldChange: <K extends keyof ClusterPaperFilterValues>(key: K, value: ClusterPaperFilterValues[K]) => void
  onSubmit: (event: SubmitEvent<HTMLFormElement>) => void
  onClearFilters: () => void
  isFetching: boolean
}

/** No text-search box: GET /clusters/{id}/papers has no text-query
 * parameter, only category/membership/pagination. CategorySelect,
 * ClearFiltersButton, FilterChip, and ResultLimitSelect are reused
 * unchanged from Paper Search. */
export function ClusterPaperFilters({ values, errors, onFieldChange, onSubmit, onClearFilters, isFetching }: ClusterPaperFiltersProps) {
  const hasBlockingErrors = Boolean(errors.minMembershipProbability || errors.limit)
  const filtersActive = hasActiveClusterPaperFilters(values)

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <CategorySelect value={values.category} onChange={(next) => onFieldChange('category', next)} />
        <MembershipThresholdFilter
          value={values.minMembershipProbability}
          onChange={(next) => onFieldChange('minMembershipProbability', next)}
          error={errors.minMembershipProbability}
        />
        <ResultLimitSelect value={values.limit} onChange={(next) => onFieldChange('limit', next)} />
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button type="submit" size="sm" disabled={hasBlockingErrors || isFetching} className="gap-1.5">
          <SlidersHorizontal className="size-3.5" aria-hidden="true" />
          Apply filters
        </Button>
        {values.category && <FilterChip label={values.category} onRemove={() => onFieldChange('category', null)} />}
        {values.minMembershipProbability !== null && (
          <FilterChip
            label={`≥ ${values.minMembershipProbability.toFixed(2)} membership`}
            onRemove={() => onFieldChange('minMembershipProbability', null)}
          />
        )}
        {errors.limit && <p className="text-[11px] text-accent-error">{errors.limit}</p>}
        {filtersActive && <ClearFiltersButton onClear={onClearFilters} />}
      </div>
    </form>
  )
}
