import type { PaperSearchParams, SimilarPapersParams } from '@/api/queryKeys'

// Mirrors the backend's actual FastAPI Query() constraints, confirmed
// against the live OpenAPI schema for both GET /api/v1/papers/search and
// GET /api/v1/papers/{paper_id}/similar (research_platform/api/routes/
// papers.py): top_k ge=1 le=100 default 10, min_similarity ge=-1 le=1.
// year_from/year_to have no range constraint of their own -- year_from >
// year_to is a business-rule 400, not a 422, on both endpoints.
export const TOP_K_MIN = 1
export const TOP_K_MAX = 100
export const TOP_K_DEFAULT = 10
export const TOP_K_OPTIONS = [10, 20, 50] as const

export const MIN_SIMILARITY_MIN = -1
export const MIN_SIMILARITY_MAX = 1

/** The filter shape shared by Paper Search and Similar Papers -- everything
 * except the free-text query, which only Search has (similarity on the
 * Similar Papers page comes from the selected paper's stored embedding,
 * never a typed query). */
export interface FilterValues {
  topK: number
  category: string | null
  yearFrom: number | null
  yearTo: number | null
  minSimilarity: number | null
}

export const DEFAULT_FILTER_VALUES: FilterValues = {
  topK: TOP_K_DEFAULT,
  category: null,
  yearFrom: null,
  yearTo: null,
  minSimilarity: null,
}

export interface SearchFormValues extends FilterValues {
  query: string
}

export const DEFAULT_SEARCH_FORM_VALUES: SearchFormValues = {
  ...DEFAULT_FILTER_VALUES,
  query: '',
}

/** Never returns NaN -- an empty or unparseable value becomes null. */
export function parseOptionalInt(raw: string): number | null {
  if (raw.trim() === '') return null
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) ? parsed : null
}

export function parseOptionalFloat(raw: string): number | null {
  if (raw.trim() === '') return null
  const parsed = Number.parseFloat(raw)
  return Number.isFinite(parsed) ? parsed : null
}

/** The URL is the source of truth for the *committed* filters -- this is
 * the only place URL query strings are parsed into typed values. */
export function filterValuesFromUrl(params: URLSearchParams): FilterValues {
  const topKRaw = parseOptionalInt(params.get('top_k') ?? '')
  const topK = topKRaw !== null && topKRaw >= TOP_K_MIN && topKRaw <= TOP_K_MAX ? topKRaw : TOP_K_DEFAULT

  return {
    topK,
    category: params.get('category') || null,
    yearFrom: parseOptionalInt(params.get('year_from') ?? ''),
    yearTo: parseOptionalInt(params.get('year_to') ?? ''),
    minSimilarity: parseOptionalFloat(params.get('min_similarity') ?? ''),
  }
}

/** top_k is always written (it always has a value); the truly-optional
 * filters are omitted entirely when unset. */
export function urlParamsFromFilterValues(values: FilterValues): URLSearchParams {
  const params = new URLSearchParams()
  params.set('top_k', String(values.topK))
  if (values.category) params.set('category', values.category)
  if (values.yearFrom !== null) params.set('year_from', String(values.yearFrom))
  if (values.yearTo !== null) params.set('year_to', String(values.yearTo))
  if (values.minSimilarity !== null) params.set('min_similarity', String(values.minSimilarity))
  return params
}

export function toApiFilterParams(values: FilterValues): SimilarPapersParams {
  return {
    topK: values.topK,
    ...(values.category ? { category: values.category } : {}),
    ...(values.yearFrom !== null ? { yearFrom: values.yearFrom } : {}),
    ...(values.yearTo !== null ? { yearTo: values.yearTo } : {}),
    ...(values.minSimilarity !== null ? { minSimilarity: values.minSimilarity } : {}),
  }
}

export interface FilterErrors {
  yearRange?: string
  minSimilarity?: string
  topK?: string
}

/** Usability-only validation -- the backend remains the source of truth
 * and still enforces these same rules server-side (year_from > year_to as
 * a 400, out-of-range top_k/min_similarity as a 422). This never
 * suppresses or reinterprets a real backend error; it only stops obviously
 * invalid submissions before they reach the network. */
export function validateFilterValues(values: FilterValues): FilterErrors {
  const errors: FilterErrors = {}

  if (values.yearFrom !== null && values.yearTo !== null && values.yearFrom > values.yearTo) {
    errors.yearRange = 'Start year cannot be after end year.'
  }

  if (values.minSimilarity !== null && (values.minSimilarity < MIN_SIMILARITY_MIN || values.minSimilarity > MIN_SIMILARITY_MAX)) {
    errors.minSimilarity = `Minimum similarity must be between ${MIN_SIMILARITY_MIN} and ${MIN_SIMILARITY_MAX}.`
  }

  if (values.topK < TOP_K_MIN || values.topK > TOP_K_MAX) {
    errors.topK = `Result limit must be between ${TOP_K_MIN} and ${TOP_K_MAX}.`
  }

  return errors
}

export function hasActiveFilters(values: FilterValues): boolean {
  return values.category !== null || values.yearFrom !== null || values.yearTo !== null || values.minSimilarity !== null
}

// --- Paper Search only (adds the free-text query on top of FilterValues) ---

export type SearchFormErrors = FilterErrors

export function searchFormValuesFromUrl(params: URLSearchParams): SearchFormValues {
  return { ...filterValuesFromUrl(params), query: params.get('query') ?? '' }
}

/** query is written first (when present) so shared links read naturally:
 * /search?query=...&top_k=...&category=... */
export function urlParamsFromSearchForm(values: SearchFormValues): URLSearchParams {
  const params = new URLSearchParams()
  const trimmedQuery = values.query.trim()
  if (trimmedQuery) params.set('query', trimmedQuery)
  params.set('top_k', String(values.topK))
  if (values.category) params.set('category', values.category)
  if (values.yearFrom !== null) params.set('year_from', String(values.yearFrom))
  if (values.yearTo !== null) params.set('year_to', String(values.yearTo))
  if (values.minSimilarity !== null) params.set('min_similarity', String(values.minSimilarity))
  return params
}

export function toApiSearchParams(values: SearchFormValues): PaperSearchParams {
  return { query: values.query.trim(), ...toApiFilterParams(values) }
}

export function validateSearchForm(values: SearchFormValues): SearchFormErrors {
  return validateFilterValues(values)
}
