import type { TrendClassificationListParams, TrendEntityListParams } from '@/api/queryKeys'
import type { TrendClassification, TrendDataQuality, TrendSortBy, TrendSortOrder } from '@/api/types'
import { parseOptionalFloat, parseOptionalInt } from '@/lib/searchParams'

// Mirrors the backend's actual FastAPI Query() constraints for GET
// /api/v1/trends/{clusters,categories} (research_platform/api/routes/
// trends.py): limit ge=1 le=100 default 20, offset ge=0 default 0,
// min_score ge=0 le=100, classification/data_quality/sort_by/sort_order
// are fixed Literal sets validated as 422 server-side.
export const TREND_LIMIT_MIN = 1
export const TREND_LIMIT_MAX = 100
export const TREND_LIMIT_DEFAULT = 20
export const TREND_MIN_SCORE_MIN = 0
export const TREND_MIN_SCORE_MAX = 100

export const TREND_CLASSIFICATIONS: TrendClassification[] = [
  'Emerging',
  'Accelerating',
  'Consistently Active',
  'Stable',
  'Cooling',
  'Insufficient Data',
]
export const TREND_DATA_QUALITIES: TrendDataQuality[] = ['HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT']
const SORT_BY_VALUES: TrendSortBy[] = ['trend_score', 'growth_rate', 'recent_paper_count', 'entity_name']

export type TrendEntityTab = 'cluster' | 'category'

export interface TrendFilterValues {
  entityTab: TrendEntityTab
  classification: TrendClassification | null
  dataQuality: TrendDataQuality | null
  minScore: number | null
  sortBy: TrendSortBy
  sortOrder: TrendSortOrder
  limit: number
  offset: number
}

export const DEFAULT_TREND_FILTER_VALUES: TrendFilterValues = {
  entityTab: 'cluster',
  classification: null,
  dataQuality: null,
  minScore: null,
  sortBy: 'trend_score',
  sortOrder: 'desc',
  limit: TREND_LIMIT_DEFAULT,
  offset: 0,
}

function isTrendClassification(value: string): value is TrendClassification {
  return (TREND_CLASSIFICATIONS as string[]).includes(value)
}

function isTrendDataQuality(value: string): value is TrendDataQuality {
  return (TREND_DATA_QUALITIES as string[]).includes(value)
}

function isSortBy(value: string): value is TrendSortBy {
  return (SORT_BY_VALUES as string[]).includes(value)
}

/** The URL is the source of truth for the *committed* filters -- this is
 * the only place URL query strings are parsed into typed values. */
export function trendFilterValuesFromUrl(params: URLSearchParams): TrendFilterValues {
  const entityTab: TrendEntityTab = params.get('type') === 'category' ? 'category' : 'cluster'

  const classificationRaw = params.get('classification')
  const classification = classificationRaw && isTrendClassification(classificationRaw) ? classificationRaw : null

  const dataQualityRaw = params.get('data_quality')
  const dataQuality = dataQualityRaw && isTrendDataQuality(dataQualityRaw) ? dataQualityRaw : null

  const minScoreRaw = parseOptionalFloat(params.get('min_score') ?? '')
  const minScore = minScoreRaw !== null && minScoreRaw >= TREND_MIN_SCORE_MIN && minScoreRaw <= TREND_MIN_SCORE_MAX ? minScoreRaw : null

  const sortByRaw = params.get('sort_by')
  const sortBy: TrendSortBy = sortByRaw && isSortBy(sortByRaw) ? sortByRaw : 'trend_score'

  const sortOrder: TrendSortOrder = params.get('sort_order') === 'asc' ? 'asc' : 'desc'

  const limitRaw = parseOptionalInt(params.get('limit') ?? '')
  const limit = limitRaw !== null && limitRaw >= TREND_LIMIT_MIN && limitRaw <= TREND_LIMIT_MAX ? limitRaw : TREND_LIMIT_DEFAULT

  const offsetRaw = parseOptionalInt(params.get('offset') ?? '')
  const offset = offsetRaw !== null && offsetRaw >= 0 ? offsetRaw : 0

  return { entityTab, classification, dataQuality, minScore, sortBy, sortOrder, limit, offset }
}

/** type/sort_by/sort_order/limit/offset are always written (they always
 * have a value, including defaults); classification/data_quality/min_score
 * are omitted entirely when unset. */
export function urlParamsFromTrendFilters(values: TrendFilterValues): URLSearchParams {
  const params = new URLSearchParams()
  params.set('type', values.entityTab)
  if (values.classification) params.set('classification', values.classification)
  if (values.dataQuality) params.set('data_quality', values.dataQuality)
  if (values.minScore !== null) params.set('min_score', String(values.minScore))
  params.set('sort_by', values.sortBy)
  params.set('sort_order', values.sortOrder)
  params.set('limit', String(values.limit))
  params.set('offset', String(values.offset))
  return params
}

export function toApiTrendParams(values: TrendFilterValues, runId?: string): TrendEntityListParams {
  return {
    runId,
    ...(values.classification ? { classification: values.classification } : {}),
    ...(values.dataQuality ? { dataQuality: values.dataQuality } : {}),
    ...(values.minScore !== null ? { minScore: values.minScore } : {}),
    sortBy: values.sortBy,
    sortOrder: values.sortOrder,
    limit: values.limit,
    offset: values.offset,
  }
}

export function toApiClassificationParams(entityType: TrendEntityTab | null, runId?: string): TrendClassificationListParams {
  return { entityType: entityType ?? undefined, runId, limit: 5, offset: 0 }
}

export interface TrendFilterErrors {
  minScore?: string
  limit?: string
}

/** Usability-only -- the backend still enforces these same bounds itself
 * (a 422) regardless of what passes here. */
export function validateTrendFilters(values: TrendFilterValues): TrendFilterErrors {
  const errors: TrendFilterErrors = {}
  if (values.minScore !== null && (values.minScore < TREND_MIN_SCORE_MIN || values.minScore > TREND_MIN_SCORE_MAX)) {
    errors.minScore = `Minimum score must be between ${TREND_MIN_SCORE_MIN} and ${TREND_MIN_SCORE_MAX}.`
  }
  if (values.limit < TREND_LIMIT_MIN || values.limit > TREND_LIMIT_MAX) {
    errors.limit = `Result limit must be between ${TREND_LIMIT_MIN} and ${TREND_LIMIT_MAX}.`
  }
  return errors
}

export function hasActiveTrendFilters(values: TrendFilterValues): boolean {
  return (
    values.classification !== null ||
    values.dataQuality !== null ||
    values.minScore !== null ||
    values.sortBy !== 'trend_score' ||
    values.sortOrder !== 'desc'
  )
}
