import { useQuery } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { getCategories } from '@/api/categories'
import { queryKeys } from '@/api/queryKeys'
import type { CategoryListResponse } from '@/api/types'

// Categories only change when a paper lands in a category that previously
// had zero canonical papers -- rare, so a long stale time avoids
// re-fetching the same short list on every page visit.
const STALE_TIME_MS = 30 * 60 * 1000

export function useCategories() {
  return useQuery<CategoryListResponse, ApiError>({
    queryKey: queryKeys.categories(),
    queryFn: getCategories,
    staleTime: STALE_TIME_MS,
    retry: 1,
  })
}
