import { useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { getPaperDetail } from '@/api/papers'
import { queryKeys } from '@/api/queryKeys'
import type { PaperDetail } from '@/api/types'
import { isValidUuid } from '@/lib/uuid'

export interface UsePaperDetailOptions {
  enabled?: boolean
}

// Paper metadata (title/abstract/authors/etc.) essentially never changes
// after ingestion -- a longer stale time than search/similar results.
const STALE_TIME_MS = 10 * 60 * 1000

/** Only fetches when paperId is a syntactically valid UUID -- an obviously
 * malformed route param never reaches the network. */
export function usePaperDetail(paperId: string | undefined, options?: UsePaperDetailOptions) {
  const hasValidId = isValidUuid(paperId)

  return useQuery<PaperDetail, ApiError>({
    queryKey: queryKeys.paperDetail(paperId ?? 'unset'),
    queryFn: () => getPaperDetail(paperId as string),
    enabled: hasValidId && (options?.enabled ?? true),
    staleTime: STALE_TIME_MS,
    retry: 1,
  })
}
