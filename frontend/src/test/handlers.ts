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
]
