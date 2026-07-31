import { useQuery } from '@tanstack/react-query'

import { ApiError, apiGet } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import type { HealthResponse } from '@/api/types'

export type HealthStatus = 'connected' | 'degraded' | 'offline' | 'checking'

const POLL_INTERVAL_MS = 30_000

/**
 * The only endpoint integration wired up in this scaffolding phase.
 * /health itself intentionally returns 503 (not 200) when the database is
 * unreachable, so a 503 response is a successful fetch carrying "degraded"
 * information -- apiGet() throwing an ApiError with status 503 is the
 * expected shape for that case, distinct from a thrown network failure
 * (status 0), which means the API process itself is unreachable.
 */
export function useHealth() {
  const query = useQuery<HealthResponse, ApiError>({
    queryKey: queryKeys.health(),
    queryFn: () => apiGet<HealthResponse>('/health'),
    refetchInterval: POLL_INTERVAL_MS,
    retry: false,
    // /health's whole point is to reflect current state -- always refetch
    // on refocus rather than trusting a stale cached "connected".
    refetchOnWindowFocus: true,
  })

  const status: HealthStatus = query.isPending
    ? 'checking'
    : query.data
      ? 'connected'
      : query.error?.status === 0
        ? 'offline'
        : 'degraded'

  return { ...query, status }
}
