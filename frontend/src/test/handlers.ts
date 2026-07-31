import { http, HttpResponse } from 'msw'

/**
 * Minimal fixtures shaped exactly like the real generated schemas
 * (src/api/types.gen.ts) -- field names match the backend's actual Pydantic
 * response models, not invented shapes. Used as MSW's default "happy path"
 * for every endpoint; individual tests override specific handlers via
 * `server.use(...)` for error/edge cases.
 */

const API_BASE = 'http://127.0.0.1:8000'
const RUN_ID = '084a1215-53be-4644-86e5-6f8a84b5422f'
const PAPER_ID = '29085b7c-11d3-4dd5-aab0-e828fd5e777e'

export const healthResponse = { status: 'healthy', database: 'connected' }

export const statsOverviewResponse = {
  total_canonical_papers: 169,
  embedded_papers: 169,
  approved_clusters: 10,
  clustered_papers: 148,
  noise_papers: 21,
  latest_clustering_run_id: RUN_ID,
  database_status: 'connected',
}

export const clusterSummaryFixture = {
  cluster_id: 2,
  cluster_name: 'Visual Recognition, Segmentation, and Localization',
  short_description: 'This cluster covers computer-vision methods for modeling, recognizing, and localizing objects.',
  paper_count: 25,
  label_confidence: 0.82,
  top_keywords: ['classification', 'object detection'],
  dominant_category: 'cs.CV',
  average_membership_probability: 0.8936,
  clustering_run_id: RUN_ID,
}

export const clustersResponse = {
  clustering_run_id: RUN_ID,
  count: 1,
  clusters: [clusterSummaryFixture],
}

export const categoriesResponse = {
  count: 2,
  categories: [
    { code: 'cs.CV', display_name: 'cs.CV', paper_count: 52 },
    { code: 'cs.LG', display_name: 'cs.LG', paper_count: 26 },
  ],
}

const paperResultFixture = {
  paper_id: PAPER_ID,
  arxiv_id: '1601.01507',
  title: 'Fast Kronecker product kernel methods via generalized vec trick',
  abstract: 'Kronecker product kernel provides the standard approach for learning from graph data.',
  authors: ['Antti Airola', 'Tapio Pahikkala'],
  primary_category: 'stat.ML',
  publication_date: '2016-01-07T12:25:53Z',
  similarity_score: 0.7248,
}

export const searchResponse = { query: 'graph neural networks', count: 1, results: [paperResultFixture] }
export const similarPapersResponse = { source_paper_id: PAPER_ID, count: 1, results: [paperResultFixture] }

export const paperDetailFixture = {
  paper_id: PAPER_ID,
  arxiv_id: paperResultFixture.arxiv_id,
  title: paperResultFixture.title,
  abstract: paperResultFixture.abstract,
  authors: paperResultFixture.authors,
  primary_category: paperResultFixture.primary_category,
  publication_date: paperResultFixture.publication_date,
  current_version_number: 1,
  embedding_available: true,
}

export const clusterDetailFixture = {
  cluster_id: 2,
  cluster_name: clusterSummaryFixture.cluster_name,
  short_description: clusterSummaryFixture.short_description,
  paper_count: 25,
  label_confidence: 0.82,
  keywords: ['classification', 'object detection'],
  evidence: [{ paper_id: PAPER_ID, reason: 'Addresses fitting and optimization of appearance models.' }],
  category_distribution: [{ category: 'cs.CV', count: 21, percent: 84.0 }],
  average_membership_probability: 0.8936,
  representative_papers: [{ paper_id: PAPER_ID, arxiv_id: paperResultFixture.arxiv_id, title: paperResultFixture.title }],
  clustering_run_id: RUN_ID,
  created_at: '2026-07-01T00:00:00Z',
  reviewed_by: 'Jibin Solomon',
  reviewed_at: '2026-07-01T00:00:00Z',
}

const clusterPaperFixture = {
  paper_id: PAPER_ID,
  arxiv_id: paperResultFixture.arxiv_id,
  title: paperResultFixture.title,
  abstract: paperResultFixture.abstract,
  authors: paperResultFixture.authors,
  primary_category: paperResultFixture.primary_category,
  publication_date: paperResultFixture.publication_date,
  membership_probability: 1.0,
  is_noise: false,
}

export const clusterPapersResponse = { cluster_id: 2, total: 1, limit: 20, offset: 0, papers: [clusterPaperFixture] }

const noisePaperFixture = { ...clusterPaperFixture, membership_probability: 0.0, is_noise: true }
export const noisePapersResponse = { clustering_run_id: RUN_ID, total: 1, limit: 20, offset: 0, papers: [noisePaperFixture] }

// --- Trends (matches src/api/schemas/trends.py exactly) --------------------
// Field values below deliberately echo the three documented real examples
// from the approved trend-analysis design: Cluster 5 (11 vs 11 -> Stable),
// Cluster 0 (0 vs 6 -> Emerging), Cluster 4 (14 vs 0 -> Cooling).

const TREND_RUN_ID = 'b79dd345-438d-46f3-876f-3aa5e8c35255'

export const trendContextFixture = {
  run_id: TREND_RUN_ID,
  calculation_version: 'trend-v1.0',
  requested_trend_mode: 'historical',
  effective_trend_mode: 'historical',
  trend_mode_label: 'Historical Cohort Comparison',
  freshness_status: 'PARTIALLY_CURRENT',
  status: 'SUCCEEDED',
  window_granularity: 'snapshot',
  comparison_period_start: '2016-01-01T00:00:00Z',
  comparison_period_end: '2016-01-12T00:00:00Z',
  recent_period_start: '2026-07-27T00:00:00Z',
  recent_period_end: '2026-07-28T00:00:00Z',
  total_canonical_papers: 169,
  calculated_at: '2026-07-31T06:45:22Z',
}

export const trendOverviewMessage =
  'These results are a Historical Cohort Comparison, not a continuous publication trend. Comparison cohort: papers published 2016-01-01 to 2016-01-11. Recent cohort: papers published 2026-07-27 to 2026-07-27.'

function makeTrendResult({
  entityType,
  entityId,
  entityName,
  recentCount,
  previousCount,
  growthRate,
  isNewActivity,
  trendScore,
  classification,
}: {
  entityType: string
  entityId: string
  entityName: string
  recentCount: number
  previousCount: number
  growthRate: number | null
  isNewActivity: boolean
  trendScore: number
  classification: string
}) {
  return {
    entity_type: entityType,
    entity_id: entityId,
    entity_name: entityName,
    metrics: {
      recent_paper_count: recentCount,
      previous_paper_count: previousCount,
      absolute_growth: recentCount - previousCount,
      growth_rate: growthRate,
      is_new_activity: isNewActivity,
      recent_publication_share: 0.2,
      previous_publication_share: 0.15,
      share_change: 0.05,
      acceleration: null,
      consistency: 0.5,
      recency_score: 0.97,
      total_papers: recentCount + previousCount,
    },
    score: {
      trend_type: entityType === 'cluster' ? 'cluster_growth' : 'category_growth',
      trend_score: trendScore,
      momentum_score: 0.5,
      trend_classification: classification,
      data_quality_level: 'LOW',
      component_breakdown: {
        recent_volume_component: 0.5,
        growth_rate_component: 0.5,
        share_change_component: 0.5,
        acceleration_component: 0.5,
        recency_component: 0.97,
        consistency_component: 0.5,
      },
    },
    evidence_summary: { recent_period_count: Math.min(recentCount, 10), comparison_period_count: Math.min(previousCount, 10) },
  }
}

export const cluster0EmergingResult = makeTrendResult({
  entityType: 'cluster',
  entityId: '0',
  entityName: 'Medical Imaging AI and Clinical Evaluation',
  recentCount: 6,
  previousCount: 0,
  growthRate: null,
  isNewActivity: true,
  trendScore: 34,
  classification: 'Emerging',
})

export const cluster4CoolingResult = makeTrendResult({
  entityType: 'cluster',
  entityId: '4',
  entityName: 'Online Media Analysis and Event Retrieval',
  recentCount: 0,
  previousCount: 14,
  growthRate: -1.0,
  isNewActivity: false,
  trendScore: 19,
  classification: 'Cooling',
})

export const cluster5StableResult = makeTrendResult({
  entityType: 'cluster',
  entityId: '5',
  entityName: 'Model Distillation and Policy Learning',
  recentCount: 11,
  previousCount: 11,
  growthRate: 0.0,
  isNewActivity: false,
  trendScore: 68,
  classification: 'Stable',
})

const categoryCoolingResult = makeTrendResult({
  entityType: 'category',
  entityId: 'cs.CV',
  entityName: 'cs.CV',
  recentCount: 12,
  previousCount: 40,
  growthRate: -0.7,
  isNewActivity: false,
  trendScore: 62,
  classification: 'Cooling',
})

export const trendOverviewResponse = {
  trend_context: trendContextFixture,
  cluster_summary: {
    entity_type: 'cluster',
    total_entities: 10,
    classification_counts: { Cooling: 8, Emerging: 1, Stable: 1 },
    data_quality_counts: { LOW: 10 },
  },
  category_summary: {
    entity_type: 'category',
    total_entities: 30,
    classification_counts: { Cooling: 8, 'Insufficient Data': 22 },
    data_quality_counts: { LOW: 8, INSUFFICIENT: 22 },
  },
  data_quality_summary: { LOW: 18, INSUFFICIENT: 22 },
  top_emerging: [cluster0EmergingResult],
  top_stable: [cluster5StableResult],
  top_cooling: [cluster4CoolingResult, categoryCoolingResult],
  message: trendOverviewMessage,
}

export const clusterTrendsListResponse = {
  trend_context: trendContextFixture,
  results: [cluster0EmergingResult, cluster5StableResult, cluster4CoolingResult],
  total: 10,
  limit: 20,
  offset: 0,
}

export const categoryTrendsListResponse = {
  trend_context: trendContextFixture,
  results: [categoryCoolingResult],
  total: 30,
  limit: 20,
  offset: 0,
}

const cluster0EvidencePaper = {
  paper_id: PAPER_ID,
  title: 'Evidence Attribution in Visual Document Understanding',
  arxiv_id: '2607.24651',
  publication_date: '2026-07-27T16:49:36Z',
  role: 'recent_period',
}

export const cluster0TrendDetailResponse = {
  trend_context: trendContextFixture,
  result: cluster0EmergingResult,
  recent_period_evidence: [cluster0EvidencePaper],
  comparison_period_evidence: [],
}

export const cluster4TrendDetailResponse = {
  trend_context: trendContextFixture,
  result: cluster4CoolingResult,
  recent_period_evidence: [],
  comparison_period_evidence: [{ ...cluster0EvidencePaper, role: 'comparison_period', publication_date: '2016-01-04T07:16:35Z' }],
}

export const cluster5TrendDetailResponse = {
  trend_context: trendContextFixture,
  result: cluster5StableResult,
  recent_period_evidence: [cluster0EvidencePaper],
  comparison_period_evidence: [{ ...cluster0EvidencePaper, role: 'comparison_period', publication_date: '2016-01-04T15:09:38Z' }],
}

export const emergingListResponse = { trend_context: trendContextFixture, results: [cluster0EmergingResult], total: 1, limit: 20, offset: 0 }
export const coolingListResponse = {
  trend_context: trendContextFixture,
  results: [cluster4CoolingResult, categoryCoolingResult],
  total: 2,
  limit: 20,
  offset: 0,
}
export const stableListResponse = { trend_context: trendContextFixture, results: [cluster5StableResult], total: 1, limit: 20, offset: 0 }

// Registration order matters, exactly like the backend's own route table:
// a literal path (/papers/search, /clusters/noise) must be listed before a
// same-shape dynamic path (/papers/:paperId, /clusters/:clusterId) or MSW
// would match the dynamic handler first.
export const handlers = [
  http.get(`${API_BASE}/health`, () => HttpResponse.json(healthResponse)),
  http.get(`${API_BASE}/api/v1/stats/overview`, () => HttpResponse.json(statsOverviewResponse)),
  http.get(`${API_BASE}/api/v1/clusters`, () => HttpResponse.json(clustersResponse)),
  http.get(`${API_BASE}/api/v1/categories`, () => HttpResponse.json(categoriesResponse)),
  http.get(`${API_BASE}/api/v1/papers/search`, () => HttpResponse.json(searchResponse)),
  http.get(`${API_BASE}/api/v1/papers/:paperId/similar`, () => HttpResponse.json(similarPapersResponse)),
  http.get(`${API_BASE}/api/v1/papers/:paperId`, () => HttpResponse.json(paperDetailFixture)),
  http.get(`${API_BASE}/api/v1/clusters/noise`, () => HttpResponse.json(noisePapersResponse)),
  http.get(`${API_BASE}/api/v1/clusters/:clusterId/papers`, () => HttpResponse.json(clusterPapersResponse)),
  http.get(`${API_BASE}/api/v1/clusters/:clusterId`, () => HttpResponse.json(clusterDetailFixture)),

  http.get(`${API_BASE}/api/v1/trends/overview`, () => HttpResponse.json(trendOverviewResponse)),
  http.get(`${API_BASE}/api/v1/trends/clusters`, () => HttpResponse.json(clusterTrendsListResponse)),
  http.get(`${API_BASE}/api/v1/trends/categories`, () => HttpResponse.json(categoryTrendsListResponse)),
  http.get(`${API_BASE}/api/v1/trends/emerging`, () => HttpResponse.json(emergingListResponse)),
  http.get(`${API_BASE}/api/v1/trends/cooling`, () => HttpResponse.json(coolingListResponse)),
  http.get(`${API_BASE}/api/v1/trends/stable`, () => HttpResponse.json(stableListResponse)),
  http.get(`${API_BASE}/api/v1/trends/:entityType/:entityId`, ({ params }) => {
    if (params.entityId === '0') return HttpResponse.json(cluster0TrendDetailResponse)
    if (params.entityId === '4') return HttpResponse.json(cluster4TrendDetailResponse)
    if (params.entityId === '5') return HttpResponse.json(cluster5TrendDetailResponse)
    return HttpResponse.json({ detail: `no trend result for ${params.entityType}=${params.entityId}` }, { status: 404 })
  }),
]
