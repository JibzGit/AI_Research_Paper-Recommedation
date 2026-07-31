import { apiGet } from '@/api/client'
import type { TrendClassificationListParams, TrendEntityListParams } from '@/api/queryKeys'
import type { TrendDetailResponse, TrendListResponse, TrendOverviewResponse } from '@/api/types'

export function getTrendsOverview(runId?: string): Promise<TrendOverviewResponse> {
  return apiGet<TrendOverviewResponse>('/api/v1/trends/overview', { run_id: runId })
}

export function getClusterTrends(params: TrendEntityListParams): Promise<TrendListResponse> {
  return apiGet<TrendListResponse>('/api/v1/trends/clusters', {
    run_id: params.runId,
    classification: params.classification,
    data_quality: params.dataQuality,
    min_score: params.minScore,
    limit: params.limit,
    offset: params.offset,
    sort_by: params.sortBy,
    sort_order: params.sortOrder,
  })
}

export function getCategoryTrends(params: TrendEntityListParams): Promise<TrendListResponse> {
  return apiGet<TrendListResponse>('/api/v1/trends/categories', {
    run_id: params.runId,
    classification: params.classification,
    data_quality: params.dataQuality,
    min_score: params.minScore,
    limit: params.limit,
    offset: params.offset,
    sort_by: params.sortBy,
    sort_order: params.sortOrder,
  })
}

export function getTrendEntityDetail(entityType: string, entityId: string, runId?: string): Promise<TrendDetailResponse> {
  return apiGet<TrendDetailResponse>(`/api/v1/trends/${entityType}/${entityId}`, { run_id: runId })
}

export function getEmergingTrends(params: TrendClassificationListParams): Promise<TrendListResponse> {
  return apiGet<TrendListResponse>('/api/v1/trends/emerging', {
    entity_type: params.entityType,
    run_id: params.runId,
    limit: params.limit,
    offset: params.offset,
  })
}

export function getCoolingTrends(params: TrendClassificationListParams): Promise<TrendListResponse> {
  return apiGet<TrendListResponse>('/api/v1/trends/cooling', {
    entity_type: params.entityType,
    run_id: params.runId,
    limit: params.limit,
    offset: params.offset,
  })
}

export function getStableTrends(params: TrendClassificationListParams): Promise<TrendListResponse> {
  return apiGet<TrendListResponse>('/api/v1/trends/stable', {
    entity_type: params.entityType,
    run_id: params.runId,
    limit: params.limit,
    offset: params.offset,
  })
}
