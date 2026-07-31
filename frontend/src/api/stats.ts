import { apiGet } from '@/api/client'
import type { PlatformOverview } from '@/api/types'

export function getPlatformOverview(): Promise<PlatformOverview> {
  return apiGet<PlatformOverview>('/api/v1/stats/overview')
}
