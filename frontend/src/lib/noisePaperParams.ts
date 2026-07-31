import type { NoisePapersParams } from '@/api/queryKeys'
import { LIMIT_DEFAULT, LIMIT_MAX, LIMIT_MIN } from '@/lib/clusterPaperParams'
import { parseOptionalInt } from '@/lib/searchParams'

// GET /api/v1/clusters/noise shares the identical limit/offset Query()
// constraints as GET /api/v1/clusters/{cluster_id}/papers (confirmed
// against the live OpenAPI schema: limit ge=1 le=100 default 20, offset
// ge=0 default 0) -- reusing the same bounds rather than redefining them.
// No min_membership_probability parameter exists on this endpoint.
export interface NoisePaperFilterValues {
  limit: number
  offset: number
  category: string | null
}

export const DEFAULT_NOISE_PAPER_FILTER_VALUES: NoisePaperFilterValues = {
  limit: LIMIT_DEFAULT,
  offset: 0,
  category: null,
}

export function noisePaperFilterValuesFromUrl(params: URLSearchParams): NoisePaperFilterValues {
  const limitRaw = parseOptionalInt(params.get('limit') ?? '')
  const limit = limitRaw !== null && limitRaw >= LIMIT_MIN && limitRaw <= LIMIT_MAX ? limitRaw : LIMIT_DEFAULT

  const offsetRaw = parseOptionalInt(params.get('offset') ?? '')
  const offset = offsetRaw !== null && offsetRaw >= 0 ? offsetRaw : 0

  return {
    limit,
    offset,
    category: params.get('category') || null,
  }
}

/** limit and offset are always written -- offset=0 is a real, meaningful
 * value and must round-trip through the URL rather than being treated as
 * "empty" and omitted. category is omitted entirely when unset. */
export function urlParamsFromNoisePaperFilters(values: NoisePaperFilterValues): URLSearchParams {
  const params = new URLSearchParams()
  params.set('limit', String(values.limit))
  params.set('offset', String(values.offset))
  if (values.category) params.set('category', values.category)
  return params
}

export function toApiNoisePaperParams(values: NoisePaperFilterValues): NoisePapersParams {
  return {
    limit: values.limit,
    offset: values.offset,
    ...(values.category ? { category: values.category } : {}),
  }
}

export interface NoisePaperFilterErrors {
  limit?: string
}

/** Usability-only -- the backend still enforces this same bound itself
 * (a 422) regardless of what passes here. */
export function validateNoisePaperFilters(values: NoisePaperFilterValues): NoisePaperFilterErrors {
  const errors: NoisePaperFilterErrors = {}
  if (values.limit < LIMIT_MIN || values.limit > LIMIT_MAX) {
    errors.limit = `Result limit must be between ${LIMIT_MIN} and ${LIMIT_MAX}.`
  }
  return errors
}

export function hasActiveNoisePaperFilters(values: NoisePaperFilterValues): boolean {
  return values.category !== null
}
