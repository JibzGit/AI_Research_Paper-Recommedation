/**
 * Centralized query-key factories, one per resource this API exposes.
 * Scaffolding only: these keys are defined so hooks/components have a
 * single, consistent source to build against, but not every resource has a
 * real useQuery hook wired up yet (only health does, in this phase).
 */

export interface PaperSearchParams {
  query: string
  topK?: number
  category?: string
  yearFrom?: number
  yearTo?: number
  minSimilarity?: number
}

export interface SimilarPapersParams {
  topK?: number
  category?: string
  yearFrom?: number
  yearTo?: number
  minSimilarity?: number
}

export interface ClusterPapersParams {
  limit?: number
  offset?: number
  category?: string
  minMembershipProbability?: number
}

export interface NoisePapersParams {
  limit?: number
  offset?: number
  category?: string
}

export const queryKeys = {
  health: () => ['health'] as const,
  statsOverview: () => ['stats', 'overview'] as const,
  categories: () => ['categories'] as const,

  paperSearch: (params: PaperSearchParams) => ['papers', 'search', params] as const,
  paperDetail: (paperId: string) => ['papers', paperId, 'detail'] as const,
  similarPapers: (paperId: string, params?: SimilarPapersParams) =>
    ['papers', paperId, 'similar', params ?? {}] as const,

  clusters: () => ['clusters'] as const,
  clusterDetail: (clusterId: number | undefined) => ['clusters', clusterId ?? 'unset', 'detail'] as const,
  clusterPapers: (clusterId: number | undefined, params?: ClusterPapersParams) =>
    ['clusters', clusterId ?? 'unset', 'papers', params ?? {}] as const,
  noisePapers: (params?: NoisePapersParams) => ['clusters', 'noise', params ?? {}] as const,
}
