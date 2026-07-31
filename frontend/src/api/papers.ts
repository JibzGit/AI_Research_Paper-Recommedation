import { apiGet } from '@/api/client'
import type { PaperSearchParams, SimilarPapersParams } from '@/api/queryKeys'
import type { PaperDetail, SearchResponse, SimilarPapersResponse } from '@/api/types'

/** apiGet() already omits undefined/null query params and preserves 0
 * (e.g. min_similarity=0) -- no extra filtering needed here. */
export function searchPapers(params: PaperSearchParams): Promise<SearchResponse> {
  return apiGet<SearchResponse>('/api/v1/papers/search', {
    query: params.query,
    top_k: params.topK,
    category: params.category,
    year_from: params.yearFrom,
    year_to: params.yearTo,
    min_similarity: params.minSimilarity,
  })
}

export function getPaperDetail(paperId: string): Promise<PaperDetail> {
  return apiGet<PaperDetail>(`/api/v1/papers/${encodeURIComponent(paperId)}`)
}

export function getSimilarPapers(paperId: string, params: SimilarPapersParams): Promise<SimilarPapersResponse> {
  return apiGet<SimilarPapersResponse>(`/api/v1/papers/${encodeURIComponent(paperId)}/similar`, {
    top_k: params.topK,
    category: params.category,
    year_from: params.yearFrom,
    year_to: params.yearTo,
    min_similarity: params.minSimilarity,
  })
}
