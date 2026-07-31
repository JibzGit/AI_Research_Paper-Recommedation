import type { ClusterPapersParams } from '@/api/queryKeys'
import { parseOptionalFloat, parseOptionalInt } from '@/lib/searchParams'

// Mirrors the backend's actual FastAPI Query() constraints on
// GET /api/v1/clusters/{cluster_id}/papers, confirmed against the live
// OpenAPI schema: limit ge=1 le=100 default 20, offset ge=0 default 0,
// min_membership_probability ge=0 le=1.
export const LIMIT_MIN = 1
export const LIMIT_MAX = 100
export const LIMIT_DEFAULT = 20
export const LIMIT_OPTIONS = [10, 20, 50] as const

export const MIN_MEMBERSHIP_MIN = 0
export const MIN_MEMBERSHIP_MAX = 1

export interface ClusterPaperFilterValues {
  limit: number
  offset: number
  category: string | null
  minMembershipProbability: number | null
}

export const DEFAULT_CLUSTER_PAPER_FILTER_VALUES: ClusterPaperFilterValues = {
  limit: LIMIT_DEFAULT,
  offset: 0,
  category: null,
  minMembershipProbability: null,
}

export function clusterPaperFilterValuesFromUrl(params: URLSearchParams): ClusterPaperFilterValues {
  const limitRaw = parseOptionalInt(params.get('limit') ?? '')
  const limit = limitRaw !== null && limitRaw >= LIMIT_MIN && limitRaw <= LIMIT_MAX ? limitRaw : LIMIT_DEFAULT

  const offsetRaw = parseOptionalInt(params.get('offset') ?? '')
  const offset = offsetRaw !== null && offsetRaw >= 0 ? offsetRaw : 0

  return {
    limit,
    offset,
    category: params.get('category') || null,
    minMembershipProbability: parseOptionalFloat(params.get('min_membership_probability') ?? ''),
  }
}

/** limit and offset are always written -- offset=0 is a real, meaningful
 * value (the first page) and must round-trip through the URL rather than
 * being treated as "empty" and omitted. category/minMembershipProbability
 * are omitted entirely when unset. */
export function urlParamsFromClusterPaperFilters(values: ClusterPaperFilterValues): URLSearchParams {
  const params = new URLSearchParams()
  params.set('limit', String(values.limit))
  params.set('offset', String(values.offset))
  if (values.category) params.set('category', values.category)
  if (values.minMembershipProbability !== null) params.set('min_membership_probability', String(values.minMembershipProbability))
  return params
}

export function toApiClusterPaperParams(values: ClusterPaperFilterValues): ClusterPapersParams {
  return {
    limit: values.limit,
    offset: values.offset,
    ...(values.category ? { category: values.category } : {}),
    ...(values.minMembershipProbability !== null ? { minMembershipProbability: values.minMembershipProbability } : {}),
  }
}

export interface ClusterPaperFilterErrors {
  minMembershipProbability?: string
  limit?: string
}

/** Usability-only -- the backend still enforces these same bounds itself
 * (a 422) regardless of what passes here. */
export function validateClusterPaperFilters(values: ClusterPaperFilterValues): ClusterPaperFilterErrors {
  const errors: ClusterPaperFilterErrors = {}

  if (
    values.minMembershipProbability !== null &&
    (values.minMembershipProbability < MIN_MEMBERSHIP_MIN || values.minMembershipProbability > MIN_MEMBERSHIP_MAX)
  ) {
    errors.minMembershipProbability = `Minimum membership must be between ${MIN_MEMBERSHIP_MIN} and ${MIN_MEMBERSHIP_MAX}.`
  }

  if (values.limit < LIMIT_MIN || values.limit > LIMIT_MAX) {
    errors.limit = `Result limit must be between ${LIMIT_MIN} and ${LIMIT_MAX}.`
  }

  return errors
}

export function hasActiveClusterPaperFilters(values: ClusterPaperFilterValues): boolean {
  return values.category !== null || values.minMembershipProbability !== null
}
