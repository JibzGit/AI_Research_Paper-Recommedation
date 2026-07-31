import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { queryKeys, type TrendEntityListParams } from '@/api/queryKeys'
import type { TrendListResponse } from '@/api/types'
import { getCategoryTrends } from '@/api/trends'

export interface UseCategoryTrendsOptions {
  enabled?: boolean
}

const STALE_TIME_MS = 2 * 60 * 1000

export function useCategoryTrends(params: TrendEntityListParams, options?: UseCategoryTrendsOptions) {
  return useQuery<TrendListResponse, ApiError>({
    queryKey: queryKeys.trendEntityList('category', params),
    queryFn: () => getCategoryTrends(params),
    enabled: options?.enabled ?? true,
    staleTime: STALE_TIME_MS,
    retry: 1,
    placeholderData: keepPreviousData,
  })
}
