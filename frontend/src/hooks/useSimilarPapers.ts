import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { getSimilarPapers } from '@/api/papers'
import { queryKeys, type SimilarPapersParams } from '@/api/queryKeys'
import type { SimilarPapersResponse } from '@/api/types'
import { isValidUuid } from '@/lib/uuid'

export interface UseSimilarPapersOptions {
  /** Callers gate this on the source paper's embedding_available flag
   * (the structured signal for "would this request even succeed"),
   * not on parsing the 400 this endpoint would otherwise return. */
  enabled?: boolean
}

const STALE_TIME_MS = 2 * 60 * 1000

/** Only fetches when paperId is a valid UUID and the caller's enabled
 * condition holds. keepPreviousData means changing a filter shows the
 * prior result set (with isFetching true) instead of flashing to a
 * loading skeleton -- the full param object is baked into the query key. */
export function useSimilarPapers(paperId: string | undefined, params: SimilarPapersParams, options?: UseSimilarPapersOptions) {
  const hasValidId = isValidUuid(paperId)

  return useQuery<SimilarPapersResponse, ApiError>({
    queryKey: queryKeys.similarPapers(paperId ?? 'unset', params),
    queryFn: () => getSimilarPapers(paperId as string, params),
    enabled: hasValidId && (options?.enabled ?? true),
    staleTime: STALE_TIME_MS,
    retry: 1,
    placeholderData: keepPreviousData,
  })
}
