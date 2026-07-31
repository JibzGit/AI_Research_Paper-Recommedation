from datetime import datetime

from pydantic import BaseModel


class TrendContext(BaseModel):
    """Attached to every trend response, list or detail. effective_trend_
    mode is always "historical" in v1 -- there is no code path that
    produces a "current" trend result yet (see trends/freshness.py) -- and
    trend_mode_label is always "Historical Cohort Comparison" for the same
    reason, never "Trending Now"/"Latest AI Trends"/any current-momentum
    phrasing. calculated_at is the persisted run's completed_at, i.e. when
    these numbers were actually computed, not when this request ran --
    nothing in this schema is ever computed live."""

    run_id: str
    calculation_version: str
    requested_trend_mode: str
    effective_trend_mode: str
    trend_mode_label: str
    freshness_status: str
    status: str
    window_granularity: str
    comparison_period_start: datetime
    comparison_period_end: datetime
    recent_period_start: datetime
    recent_period_end: datetime
    total_canonical_papers: int
    calculated_at: datetime | None


class TrendMetrics(BaseModel):
    """The raw counts/windows behind a score -- mirrors
    TrendEntitySnapshot exactly, including its nullability: growth_rate/
    share_change/acceleration/consistency/recency_score are all legitimate
    nulls (undefined growth rate, no comparison-period baseline, fewer
    than 3 windows of history), never coerced to 0 or omitted."""

    recent_paper_count: int
    previous_paper_count: int
    absolute_growth: int
    growth_rate: float | None
    is_new_activity: bool
    recent_publication_share: float | None
    previous_publication_share: float | None
    share_change: float | None
    acceleration: bool | None
    consistency: float | None
    recency_score: float | None
    total_papers: int


class TrendScore(BaseModel):
    """Mirrors the persisted TrendScore row for one (entity, trend_type)
    pair. trend_type is always "cluster_growth" or "category_growth" in
    v1 -- "citation_momentum"/"paper_momentum" are reserved but never
    populated (no repeated metric-snapshot dates exist yet to measure a
    citation change from)."""

    trend_type: str
    trend_score: int
    momentum_score: float | None
    trend_classification: str
    data_quality_level: str
    component_breakdown: dict


class TrendEvidenceSummary(BaseModel):
    recent_period_count: int
    comparison_period_count: int


class TrendEvidencePaper(BaseModel):
    """One paper backing a score. Never LLM-generated -- every field here
    is a plain join from trend_evidence_papers to papers, ordered
    deterministically by the same (publication_date, paper_id) convention
    the pipeline used to select it in the first place."""

    paper_id: str
    title: str
    arxiv_id: str | None
    publication_date: datetime | None
    role: str


class TrendResult(BaseModel):
    entity_type: str
    entity_id: str
    entity_name: str
    metrics: TrendMetrics
    score: TrendScore
    evidence_summary: TrendEvidenceSummary


class EntityTypeSummary(BaseModel):
    entity_type: str
    total_entities: int
    classification_counts: dict[str, int]
    data_quality_counts: dict[str, int]


class TrendOverviewResponse(BaseModel):
    """message is the prominent, non-optional historical-cohort warning
    required for every overview response -- explains in plain language
    that these results compare two ingestion cohorts (Comparison cohort:
    the January 2016 batch; Recent cohort: the July 2026 batch), not a
    continuous publication trend."""

    trend_context: TrendContext
    cluster_summary: EntityTypeSummary
    category_summary: EntityTypeSummary
    data_quality_summary: dict[str, int]
    top_emerging: list[TrendResult]
    top_stable: list[TrendResult]
    top_cooling: list[TrendResult]
    message: str


class TrendListResponse(BaseModel):
    trend_context: TrendContext
    results: list[TrendResult]
    total: int
    limit: int
    offset: int


class TrendDetailResponse(BaseModel):
    trend_context: TrendContext
    result: TrendResult
    recent_period_evidence: list[TrendEvidencePaper]
    comparison_period_evidence: list[TrendEvidencePaper]
