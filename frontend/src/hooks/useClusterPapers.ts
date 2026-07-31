import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { getClusterPapers } from '@/api/clusters'
import { queryKeys, type ClusterPapersParams } from '@/api/queryKeys'
import type { ClusterPapersResponse } from '@/api/types'

export interface UseClusterPapersOptions {
  enabled?: boolean
}

const STALE_TIME_MS = 2 * 60 * 1000

/** Only fetches for a valid non-negative integer clusterId. The full
 * normalized filter+pagination object is baked into the query key, and
 * keepPreviousData means changing a filter or page shows the prior result
 * set (with isFetching true) instead of flashing to a loading skeleton. */
export function useClusterPapers(clusterId: number | undefined, params: ClusterPapersParams, options?: UseClusterPapersOptions) {
  const hasValidId = clusterId !== undefined && Number.isInteger(clusterId) && clusterId >= 0

  return useQuery<ClusterPapersResponse, ApiError>({
    queryKey: queryKeys.clusterPapers(clusterId, params),
    queryFn: () => getClusterPapers(clusterId as number, params),
    enabled: hasValidId && (options?.enabled ?? true),
    staleTime: STALE_TIME_MS,
    retry: 1,
    placeholderData: keepPreviousData,
  })
}
