import { ClusterCategoryFilter } from '@/components/clusters/ClusterCategoryFilter'
import { ClusterSortSelect } from '@/components/clusters/ClusterSortSelect'
import { ClearFiltersButton } from '@/components/papers/ClearFiltersButton'
import { FilterChip } from '@/components/papers/FilterChip'
import { SearchInput } from '@/components/papers/SearchInput'
import {
  CLUSTER_SORT_OPTIONS,
  DEFAULT_SORT,
  hasActiveClusterDiscoveryFilters,
  type ClusterDiscoveryValues,
  type ClusterSortOption,
} from '@/lib/clusterDiscoveryParams'

interface ClusterDiscoveryControlsProps {
  values: ClusterDiscoveryValues
  categories: string[]
  onSearchChange: (value: string) => void
  onCategoryChange: (value: string | null) => void
  onSortChange: (value: ClusterSortOption) => void
  onClear: () => void
  visibleCount: number
  totalCount: number
}

/** Purely client-side controls -- no submit/apply action, every change
 * updates the URL immediately since nothing here triggers a network
 * request (filtering/sorting runs on the already-loaded cluster array). */
export function ClusterDiscoveryControls({
  values,
  categories,
  onSearchChange,
  onCategoryChange,
  onSortChange,
  onClear,
  visibleCount,
  totalCount,
}: ClusterDiscoveryControlsProps) {
  const filtersActive = hasActiveClusterDiscoveryFilters(values)
  const trimmedSearch = values.search.trim()
  const sortLabel = CLUSTER_SORT_OPTIONS.find((option) => option.value === values.sort)?.label

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="grid gap-3 sm:grid-cols-3">
        <SearchInput
          id="cluster-search"
          value={values.search}
          onChange={onSearchChange}
          placeholder="Search clusters by name, description, or keyword..."
          ariaLabel="Search research clusters"
        />
        <ClusterCategoryFilter value={values.category} onChange={onCategoryChange} categories={categories} />
        <ClusterSortSelect value={values.sort} onChange={onSortChange} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <p className="text-xs text-muted-foreground" aria-live="polite">
          Showing <span className="font-medium text-foreground tabular-nums">{visibleCount}</span> of{' '}
          <span className="font-medium text-foreground tabular-nums">{totalCount}</span> research clusters
        </p>
        {filtersActive && (
          <div className="flex flex-wrap items-center gap-2">
            {trimmedSearch && <FilterChip label={`Search: ${trimmedSearch}`} onRemove={() => onSearchChange('')} />}
            {values.category && <FilterChip label={`Category: ${values.category}`} onRemove={() => onCategoryChange(null)} />}
            {values.sort !== DEFAULT_SORT && sortLabel && (
              <FilterChip label={`Sort: ${sortLabel}`} onRemove={() => onSortChange(DEFAULT_SORT)} />
            )}
            <ClearFiltersButton onClear={onClear} />
          </div>
        )}
      </div>
    </div>
  )
}
