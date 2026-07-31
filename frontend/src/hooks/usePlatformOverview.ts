import { useQuery } from '@tanstack/react-query'

import { getPlatformOverview } from '@/api/stats'
import { ApiError } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import type { PlatformOverview } from '@/api/types'

// Platform totals only change when ingestion/clustering jobs run (minutes to
// hours apart), not seconds -- a short stale time and no polling would just
// cause needless refetching.
const STALE_TIME_MS = 5 * 60 * 1000

export function usePlatformOverview() {
  return useQuery<PlatformOverview, ApiError>({
    queryKey: queryKeys.statsOverview(),
    queryFn: getPlatformOverview,
    staleTime: STALE_TIME_MS,
    retry: 1,
  })
}
