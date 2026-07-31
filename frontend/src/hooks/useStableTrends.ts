import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { queryKeys, type TrendClassificationListParams } from '@/api/queryKeys'
import type { TrendListResponse } from '@/api/types'
import { getStableTrends } from '@/api/trends'

export interface UseStableTrendsOptions {
  enabled?: boolean
}

const STALE_TIME_MS = 5 * 60 * 1000

export function useStableTrends(params: TrendClassificationListParams, options?: UseStableTrendsOptions) {
  return useQuery<TrendListResponse, ApiError>({
    queryKey: queryKeys.trendClassificationList('Stable', params),
    queryFn: () => getStableTrends(params),
    enabled: options?.enabled ?? true,
    staleTime: STALE_TIME_MS,
    retry: 1,
    placeholderData: keepPreviousData,
  })
}
