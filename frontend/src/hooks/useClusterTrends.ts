import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { queryKeys, type TrendEntityListParams } from '@/api/queryKeys'
import type { TrendListResponse } from '@/api/types'
import { getClusterTrends } from '@/api/trends'

export interface UseClusterTrendsOptions {
  enabled?: boolean
}

const STALE_TIME_MS = 2 * 60 * 1000

/** The full normalized filter+sort+pagination object is baked into the
 * query key. keepPreviousData means changing a filter or page shows the
 * prior result set (with isFetching true) instead of flashing to a
 * loading skeleton. */
export function useClusterTrends(params: TrendEntityListParams, options?: UseClusterTrendsOptions) {
  return useQuery<TrendListResponse, ApiError>({
    queryKey: queryKeys.trendEntityList('cluster', params),
    queryFn: () => getClusterTrends(params),
    enabled: options?.enabled ?? true,
    staleTime: STALE_TIME_MS,
    retry: 1,
    placeholderData: keepPreviousData,
  })
}
