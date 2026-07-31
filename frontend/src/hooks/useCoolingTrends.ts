import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { queryKeys, type TrendClassificationListParams } from '@/api/queryKeys'
import type { TrendListResponse } from '@/api/types'
import { getCoolingTrends } from '@/api/trends'

export interface UseCoolingTrendsOptions {
  enabled?: boolean
}

const STALE_TIME_MS = 5 * 60 * 1000

export function useCoolingTrends(params: TrendClassificationListParams, options?: UseCoolingTrendsOptions) {
  return useQuery<TrendListResponse, ApiError>({
    queryKey: queryKeys.trendClassificationList('Cooling', params),
    queryFn: () => getCoolingTrends(params),
    enabled: options?.enabled ?? true,
    staleTime: STALE_TIME_MS,
    retry: 1,
    placeholderData: keepPreviousData,
  })
}
