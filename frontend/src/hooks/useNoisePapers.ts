import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { getNoisePapers } from '@/api/clusters'
import { queryKeys, type NoisePapersParams } from '@/api/queryKeys'
import type { NoisePapersResponse } from '@/api/types'

export interface UseNoisePapersOptions {
  enabled?: boolean
}

const STALE_TIME_MS = 2 * 60 * 1000

/** The full normalized pagination+filter object is baked into the query
 * key. keepPreviousData means changing the category filter or page shows
 * the prior result set (with isFetching true) instead of flashing to a
 * loading skeleton. */
export function useNoisePapers(params: NoisePapersParams, options?: UseNoisePapersOptions) {
  return useQuery<NoisePapersResponse, ApiError>({
    queryKey: queryKeys.noisePapers(params),
    queryFn: () => getNoisePapers(params),
    enabled: options?.enabled ?? true,
    staleTime: STALE_TIME_MS,
    retry: 1,
    placeholderData: keepPreviousData,
  })
}
