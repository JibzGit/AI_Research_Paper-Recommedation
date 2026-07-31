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
