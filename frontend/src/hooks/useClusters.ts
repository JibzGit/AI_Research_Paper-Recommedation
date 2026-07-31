import { useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { getClusters } from '@/api/clusters'
import { queryKeys } from '@/api/queryKeys'
import type { ClusterListResponse } from '@/api/types'

const STALE_TIME_MS = 5 * 60 * 1000

export function useClusters() {
  return useQuery<ClusterListResponse, ApiError>({
    queryKey: queryKeys.clusters(),
    queryFn: getClusters,
    staleTime: STALE_TIME_MS,
    retry: 1,
  })
}
