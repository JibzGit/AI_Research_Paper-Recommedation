import { useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import type { TrendDetailResponse, TrendEntityType } from '@/api/types'
import { getTrendEntityDetail } from '@/api/trends'

export interface UseTrendEntityDetailOptions {
  enabled?: boolean
}

const STALE_TIME_MS = 5 * 60 * 1000

export function useTrendEntityDetail(
  entityType: TrendEntityType | undefined,
  entityId: string | undefined,
  runId?: string,
  options?: UseTrendEntityDetailOptions,
) {
  const hasValidParams = entityType !== undefined && entityId !== undefined && entityId.trim().length > 0

  return useQuery<TrendDetailResponse, ApiError>({
    queryKey: queryKeys.trendEntityDetail(entityType, entityId, runId),
    queryFn: () => getTrendEntityDetail(entityType as string, entityId as string, runId),
    enabled: hasValidParams && (options?.enabled ?? true),
    staleTime: STALE_TIME_MS,
    retry: 1,
  })
}
