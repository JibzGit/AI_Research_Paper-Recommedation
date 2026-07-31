import { SlidersHorizontal } from 'lucide-react'
import type { SubmitEvent } from 'react'

import { ClearFiltersButton } from '@/components/papers/ClearFiltersButton'
import { FilterChip } from '@/components/papers/FilterChip'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  hasActiveTrendFilters,
  TREND_CLASSIFICATIONS,
  TREND_DATA_QUALITIES,
  type TrendFilterErrors,
  type TrendFilterValues,
} from '@/lib/trendParams'

const ALL_VALUE = '__all__'

const SORT_OPTIONS = [
  { value: 'trend_score:desc', label: 'Trend score (high to low)' },
  { value: 'trend_score:asc', label: 'Trend score (low to high)' },
  { value: 'growth_rate:desc', label: 'Growth rate (high to low)' },
  { value: 'growth_rate:asc', label: 'Growth rate (low to high)' },
  { value: 'recent_paper_count:desc', label: 'Recent paper count (high to low)' },
  { value: 'entity_name:asc', label: 'Name (A to Z)' },
] as const

interface TrendFiltersProps {
  values: TrendFilterValues
  errors: TrendFilterErrors
  onFieldChange: <K extends keyof TrendFilterValues>(key: K, value: TrendFilterValues[K]) => void
  onSortChange: (sortBy: TrendFilterValues['sortBy'], sortOrder: TrendFilterValues['sortOrder']) => void
  onSubmit: (event: SubmitEvent<HTMLFormElement>) => void
  onClearFilters: () => void
  isFetching: boolean
}

export function TrendFilters({ values, errors, onFieldChange, onSortChange, onSubmit, onClearFilters, isFetching }: TrendFiltersProps) {
  const filtersActive = hasActiveTrendFilters(values)
  const sortValue = `${values.sortBy}:${values.sortOrder}`
  const hasErrors = Boolean(errors.minScore || errors.limit)

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="trend-classification-select" className="text-xs text-muted-foreground">
            Classification
          </Label>
          <Select
            value={values.classification ?? ALL_VALUE}
            onValueChange={(next) => onFieldChange('classification', next === ALL_VALUE ? null : (next as TrendFilterValues['classification']))}
          >
            <SelectTrigger id="trend-classification-select" className="h-9 w-full text-xs">
              <SelectValue placeholder="All classifications" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All classifications</SelectItem>
              {TREND_CLASSIFICATIONS.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="trend-data-quality-select" className="text-xs text-muted-foreground">
            Data quality
          </Label>
          <Select
            value={values.dataQuality ?? ALL_VALUE}
            onValueChange={(next) => onFieldChange('dataQuality', next === ALL_VALUE ? null : (next as TrendFilterValues['dataQuality']))}
          >
            <SelectTrigger id="trend-data-quality-select" className="h-9 w-full text-xs">
              <SelectValue placeholder="All levels" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All levels</SelectItem>
              {TREND_DATA_QUALITIES.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="trend-min-score-input" className="text-xs text-muted-foreground">
            Minimum score
          </Label>
          <Input
            id="trend-min-score-input"
            type="number"
            inputMode="numeric"
            min={0}
            max={100}
            placeholder="0-100"
            className="h-9 text-xs"
            value={values.minScore ?? ''}
            onChange={(event) => onFieldChange('minScore', event.target.value === '' ? null : Number(event.target.value))}
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="trend-sort-select" className="text-xs text-muted-foreground">
            Sort by
          </Label>
          <Select
            value={sortValue}
            onValueChange={(next) => {
              const [sortBy, sortOrder] = next.split(':') as [TrendFilterValues['sortBy'], TrendFilterValues['sortOrder']]
              onSortChange(sortBy, sortOrder)
            }}
          >
            <SelectTrigger id="trend-sort-select" className="h-9 w-full text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button type="submit" size="sm" disabled={hasErrors || isFetching} className="gap-1.5">
          <SlidersHorizontal className="size-3.5" aria-hidden="true" />
          Apply filters
        </Button>
        {values.classification && (
          <FilterChip label={values.classification} onRemove={() => onFieldChange('classification', null)} />
        )}
        {values.dataQuality && <FilterChip label={`Quality: ${values.dataQuality}`} onRemove={() => onFieldChange('dataQuality', null)} />}
        {values.minScore !== null && (
          <FilterChip label={`Score ≥ ${values.minScore}`} onRemove={() => onFieldChange('minScore', null)} />
        )}
        {errors.minScore && <p className="text-[11px] text-accent-error">{errors.minScore}</p>}
        {errors.limit && <p className="text-[11px] text-accent-error">{errors.limit}</p>}
        {filtersActive && <ClearFiltersButton onClear={onClearFilters} />}
      </div>
    </form>
  )
}
