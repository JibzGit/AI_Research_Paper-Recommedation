import { useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { getClusterDetail } from '@/api/clusters'
import { queryKeys } from '@/api/queryKeys'
import type { ClusterDetail } from '@/api/types'

const STALE_TIME_MS = 5 * 60 * 1000

export interface UseClusterDetailOptions {
  enabled?: boolean
}

/** Only fetches once a real cluster ID is available -- clusterId is
 * commonly derived from a route param or another query's result, both of
 * which are `undefined` for at least the first render. */
export function useClusterDetail(clusterId: number | undefined, options?: UseClusterDetailOptions) {
  const hasValidId = clusterId !== undefined && Number.isFinite(clusterId)

  return useQuery<ClusterDetail, ApiError>({
    queryKey: queryKeys.clusterDetail(clusterId),
    queryFn: () => getClusterDetail(clusterId as number),
    enabled: hasValidId && (options?.enabled ?? true),
    staleTime: STALE_TIME_MS,
    retry: 1,
  })
}
