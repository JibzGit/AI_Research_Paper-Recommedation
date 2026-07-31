/**
 * Ergonomic aliases over the generated OpenAPI types -- no field is
 * redefined here, only named. Regenerate src/api/types.gen.ts (npm run
 * generate:api) whenever the backend's response shapes change; these
 * aliases update automatically since they reference it directly.
 */
import type { components } from '@/api/types.gen'

export type HealthResponse = components['schemas']['HealthResponse']
export type PlatformOverview = components['schemas']['PlatformOverview']
export type CategoryListResponse = components['schemas']['CategoryListResponse']
export type CategorySummary = components['schemas']['CategorySummary']
export type ClusterListResponse = components['schemas']['ClusterListResponse']
export type ClusterSummary = components['schemas']['ClusterSummary']
export type ClusterDetail = components['schemas']['ClusterDetail']
export type ClusterPapersResponse = components['schemas']['ClusterPapersResponse']
export type ClusterPaper = components['schemas']['ClusterPaper']
export type RepresentativePaper = components['schemas']['RepresentativePaper']
export type CategoryDistributionItem = components['schemas']['CategoryDistributionItem']
export type ClusterEvidenceItem = components['schemas']['ClusterEvidenceItem']
export type NoisePapersResponse = components['schemas']['NoisePapersResponse']
export type SearchResponse = components['schemas']['SearchResponse']
export type SimilarPapersResponse = components['schemas']['SimilarPapersResponse']
export type PaperResult = components['schemas']['PaperResult']
export type PaperDetail = components['schemas']['PaperDetail']
export type ErrorResponse = components['schemas']['ErrorResponse']

export type TrendContext = components['schemas']['TrendContext']
export type TrendMetrics = components['schemas']['TrendMetrics']
export type TrendScore = components['schemas']['TrendScore']
export type TrendEvidencePaper = components['schemas']['TrendEvidencePaper']
export type TrendEvidenceSummary = components['schemas']['TrendEvidenceSummary']
export type TrendResult = components['schemas']['TrendResult']
export type EntityTypeSummary = components['schemas']['EntityTypeSummary']
export type TrendOverviewResponse = components['schemas']['TrendOverviewResponse']
export type TrendListResponse = components['schemas']['TrendListResponse']
export type TrendDetailResponse = components['schemas']['TrendDetailResponse']

export type TrendEntityType = 'cluster' | 'category'
export type TrendClassification = 'Emerging' | 'Accelerating' | 'Consistently Active' | 'Stable' | 'Cooling' | 'Insufficient Data'
export type TrendDataQuality = 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT'
export type TrendSortBy = 'trend_score' | 'growth_rate' | 'recent_paper_count' | 'entity_name'
export type TrendSortOrder = 'asc' | 'desc'
