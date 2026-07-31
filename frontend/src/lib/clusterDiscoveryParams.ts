import type { ClusterSummary } from '@/api/types'

/**
 * Client-side-only discovery controls for the Research Clusters page.
 * GET /api/v1/clusters has no search/filter/sort query parameters at all
 * (confirmed against the live OpenAPI schema) -- q/category/sort live only
 * in the URL for shareability/refresh/back-forward, and are applied to the
 * already-loaded cluster array. They are never sent to the backend.
 */

export type ClusterSortOption = 'paper-count-desc' | 'paper-count-asc' | 'label-confidence-desc' | 'membership-desc' | 'name-asc'

export const DEFAULT_SORT: ClusterSortOption = 'paper-count-desc'

export const CLUSTER_SORT_OPTIONS: Array<{ value: ClusterSortOption; label: string }> = [
  { value: 'paper-count-desc', label: 'Paper count: high to low' },
  { value: 'paper-count-asc', label: 'Paper count: low to high' },
  { value: 'label-confidence-desc', label: 'Label confidence: high to low' },
  { value: 'membership-desc', label: 'Average membership: high to low' },
  { value: 'name-asc', label: 'Cluster name: A–Z' },
]

const VALID_SORT_VALUES = new Set<string>(CLUSTER_SORT_OPTIONS.map((option) => option.value))

function isValidSort(value: string | null): value is ClusterSortOption {
  return value !== null && VALID_SORT_VALUES.has(value)
}

export interface ClusterDiscoveryValues {
  search: string
  category: string | null
  sort: ClusterSortOption
}

export const DEFAULT_CLUSTER_DISCOVERY_VALUES: ClusterDiscoveryValues = {
  search: '',
  category: null,
  sort: DEFAULT_SORT,
}

/** An invalid/unrecognized sort value (e.g. a hand-edited URL) falls back
 * safely to the backend's own default order rather than erroring. */
export function clusterDiscoveryValuesFromUrl(params: URLSearchParams): ClusterDiscoveryValues {
  const sortRaw = params.get('sort')
  return {
    search: params.get('q') ?? '',
    category: params.get('category') || null,
    sort: isValidSort(sortRaw) ? sortRaw : DEFAULT_SORT,
  }
}

export function urlParamsFromClusterDiscovery(values: ClusterDiscoveryValues): URLSearchParams {
  const params = new URLSearchParams()
  const trimmedSearch = values.search.trim()
  if (trimmedSearch) params.set('q', trimmedSearch)
  if (values.category) params.set('category', values.category)
  if (values.sort !== DEFAULT_SORT) params.set('sort', values.sort)
  return params
}

export function hasActiveClusterDiscoveryFilters(values: ClusterDiscoveryValues): boolean {
  return values.search.trim() !== '' || values.category !== null || values.sort !== DEFAULT_SORT
}

function matchesSearch(cluster: ClusterSummary, term: string): boolean {
  const haystack = [cluster.cluster_name, cluster.short_description, cluster.dominant_category ?? '', ...cluster.top_keywords]
    .join(' ')
    .toLowerCase()
  return haystack.includes(term)
}

/**
 * Filters, then sorts. For the default sort ('paper-count-desc', the
 * backend's own order), the filtered array is returned as-is -- no re-sort
 * is ever applied, so filtering alone can never silently change the
 * backend's relative ordering. Every other option re-sorts a shallow copy.
 */
export function filterAndSortClusters(clusters: ClusterSummary[], values: ClusterDiscoveryValues): ClusterSummary[] {
  const term = values.search.trim().toLowerCase()

  let filtered = clusters
  if (term) {
    filtered = filtered.filter((cluster) => matchesSearch(cluster, term))
  }
  if (values.category) {
    filtered = filtered.filter((cluster) => cluster.dominant_category === values.category)
  }

  if (values.sort === DEFAULT_SORT) {
    return filtered
  }

  const sorted = [...filtered]
  switch (values.sort) {
    case 'paper-count-asc':
      sorted.sort((a, b) => a.paper_count - b.paper_count)
      break
    case 'label-confidence-desc':
      sorted.sort((a, b) => b.label_confidence - a.label_confidence)
      break
    case 'membership-desc':
      sorted.sort((a, b) => b.average_membership_probability - a.average_membership_probability)
      break
    case 'name-asc':
      sorted.sort((a, b) => a.cluster_name.localeCompare(b.cluster_name))
      break
  }
  return sorted
}

/** Dominant categories present among the already-loaded clusters --
 * derived client-side, never a separate /api/v1/categories fetch (that
 * endpoint reflects the whole corpus, not just these ~10 clusters). */
export function availableDominantCategories(clusters: ClusterSummary[]): string[] {
  const set = new Set<string>()
  for (const cluster of clusters) {
    if (cluster.dominant_category) set.add(cluster.dominant_category)
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
}
