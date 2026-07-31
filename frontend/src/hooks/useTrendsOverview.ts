import { useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import type { TrendOverviewResponse } from '@/api/types'
import { getTrendsOverview } from '@/api/trends'

const STALE_TIME_MS = 5 * 60 * 1000

/** 503 (no successful trend run yet) is a real, expected ApiError here --
 * callers should render it through ErrorState's dedicated 503 branch, not
 * treat it as an unexpected failure. */
export function useTrendsOverview(runId?: string) {
  return useQuery<TrendOverviewResponse, ApiError>({
    queryKey: queryKeys.trendsOverview(runId),
    queryFn: () => getTrendsOverview(runId),
    staleTime: STALE_TIME_MS,
    retry: 1,
  })
}
