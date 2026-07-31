import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { searchPapers } from '@/api/papers'
import { queryKeys, type PaperSearchParams } from '@/api/queryKeys'
import type { SearchResponse } from '@/api/types'

export interface UsePaperSearchOptions {
  enabled?: boolean
}

/**
 * Only executes once the trimmed query is non-empty -- a blank/whitespace
 * query never reaches the network, matching the backend's own "empty query
 * -> 400" rule by simply never sending the request in the first place.
 * keepPreviousData means changing a filter or top_k shows the prior
 * result set (with isFetching true) instead of flashing to a loading
 * skeleton, since the full param object -- not just the query text -- is
 * baked into the query key.
 */
export function usePaperSearch(params: PaperSearchParams, options?: UsePaperSearchOptions) {
  const hasQuery = params.query.trim() !== ''

  return useQuery<SearchResponse, ApiError>({
    queryKey: queryKeys.paperSearch(params),
    queryFn: () => searchPapers(params),
    enabled: hasQuery && (options?.enabled ?? true),
    staleTime: 2 * 60 * 1000,
    retry: 1,
    placeholderData: keepPreviousData,
  })
}
