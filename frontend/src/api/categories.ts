import { apiGet } from '@/api/client'
import type { CategoryListResponse } from '@/api/types'

export function getCategories(): Promise<CategoryListResponse> {
  return apiGet<CategoryListResponse>('/api/v1/categories')
}
