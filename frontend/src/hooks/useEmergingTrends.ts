import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { queryKeys, type TrendClassificationListParams } from '@/api/queryKeys'
import type { TrendListResponse } from '@/api/types'
import { getEmergingTrends } from '@/api/trends'

export interface UseEmergingTrendsOptions {
  enabled?: boolean
}

const STALE_TIME_MS = 5 * 60 * 1000

export function useEmergingTrends(params: TrendClassificationListParams, options?: UseEmergingTrendsOptions) {
  return useQuery<TrendListResponse, ApiError>({
    queryKey: queryKeys.trendClassificationList('Emerging', params),
    queryFn: () => getEmergingTrends(params),
    enabled: options?.enabled ?? true,
    staleTime: STALE_TIME_MS,
    retry: 1,
    placeholderData: keepPreviousData,
  })
}
