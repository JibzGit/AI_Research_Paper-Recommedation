from datetime import datetime

from pydantic import BaseModel


class ClusterPaper(BaseModel):
    """Shared by /clusters/{id}/papers and /clusters/noise. Distinct from
    embeddings.PaperResult (search/similar-papers) on purpose: this carries
    membership_probability (confidence a PAPER belongs to its cluster) and
    is_noise, neither of which is a similarity_score -- the two concepts
    are never conflated under one "confidence" field anywhere in this API."""

    paper_id: str
    arxiv_id: str | None
    title: str
    abstract: str
    authors: list[str]
    primary_category: str
    publication_date: datetime | None
    membership_probability: float
    is_noise: bool


class ClusterSummary(BaseModel):
    cluster_id: int
    cluster_name: str
    short_description: str
    paper_count: int
    label_confidence: float  # confidence the APPROVED LABEL accurately describes the cluster
    top_keywords: list[str]
    dominant_category: str | None
    average_membership_probability: float  # avg confidence PAPERS belong to this cluster
    clustering_run_id: str


class ClusterListResponse(BaseModel):
    clustering_run_id: str | None
    count: int
    clusters: list[ClusterSummary]


class ClusterEvidenceItem(BaseModel):
    paper_id: str
    reason: str


class CategoryDistributionItem(BaseModel):
    category: str
    count: int
    percent: float


class RepresentativePaper(BaseModel):
    paper_id: str
    arxiv_id: str | None
    title: str


class ClusterDetail(BaseModel):
    cluster_id: int
    cluster_name: str
    short_description: str
    paper_count: int
    label_confidence: float
    keywords: list[str]
    evidence: list[ClusterEvidenceItem]
    category_distribution: list[CategoryDistributionItem]
    average_membership_probability: float
    representative_papers: list[RepresentativePaper]
    clustering_run_id: str
    created_at: datetime
    reviewed_by: str | None
    reviewed_at: datetime | None


class ClusterPapersResponse(BaseModel):
    cluster_id: int
    total: int
    limit: int
    offset: int
    papers: list[ClusterPaper]


class NoisePapersResponse(BaseModel):
    clustering_run_id: str | None
    total: int
    limit: int
    offset: int
    papers: list[ClusterPaper]
