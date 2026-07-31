import uuid
from typing import Literal

from fastapi import APIRouter, Query

from research_platform.api.schemas.errors import ErrorResponse
from research_platform.api.schemas.trends import TrendDetailResponse, TrendListResponse, TrendOverviewResponse
from research_platform.db.session import SessionLocal
from research_platform.trends import api_queries, classifications
from research_platform.trends.pipeline import ENTITY_TYPE_CATEGORY, ENTITY_TYPE_CLUSTER

router = APIRouter(prefix="/trends", tags=["trends"])

# Literal path/query types, not free strings: FastAPI validates these before
# the handler body ever runs (-> 422 on an invalid value), the same
# "malformed input never reaches the function" convention already used for
# /papers/{paper_id}'s uuid.UUID path type -- no hand-written "invalid
# entity_type" ValueError anywhere in this file.
EntityTypeParam = Literal[ENTITY_TYPE_CLUSTER, ENTITY_TYPE_CATEGORY]
ClassificationParam = Literal[
    classifications.EMERGING,
    classifications.ACCELERATING,
    classifications.CONSISTENTLY_ACTIVE,
    classifications.STABLE,
    classifications.COOLING,
    classifications.INSUFFICIENT_DATA,
]
DataQualityParam = Literal[
    classifications.HIGH, classifications.MEDIUM, classifications.LOW, classifications.INSUFFICIENT
]
SortByParam = Literal["trend_score", "growth_rate", "recent_paper_count", "entity_name"]
SortOrderParam = Literal["asc", "desc"]

RUN_NOT_FOUND = {"description": "run_id does not match any trend analysis run", "model": ErrorResponse}
RESULTS_UNAVAILABLE = {"description": "No successful trend analysis run is available yet", "model": ErrorResponse}
ENTITY_NOT_FOUND = {"description": "No trend result for this entity under the resolved run", "model": ErrorResponse}


def _entity_list(
    run_id, entity_type, classification, data_quality, min_score, limit, offset, sort_by, sort_order
) -> TrendListResponse:
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, run_id)
        total, results = api_queries.get_entity_results(
            session,
            run.id,
            entity_type,
            classification=classification,
            data_quality=data_quality,
            min_score=min_score,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return TrendListResponse(
            trend_context=api_queries.build_trend_context(run), results=results, total=total, limit=limit, offset=offset
        )
    finally:
        session.close()


def _classification_list(run_id, classification, entity_type, limit, offset) -> TrendListResponse:
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, run_id)
        total, results = api_queries.get_results_by_classification(
            session, run.id, classification, entity_type=entity_type, limit=limit, offset=offset
        )
        return TrendListResponse(
            trend_context=api_queries.build_trend_context(run), results=results, total=total, limit=limit, offset=offset
        )
    finally:
        session.close()


@router.get(
    "/overview",
    response_model=TrendOverviewResponse,
    responses={503: RESULTS_UNAVAILABLE, 404: RUN_NOT_FOUND},
)
def overview(run_id: uuid.UUID | None = Query(None, description="Explicit trend_analysis_runs.id; defaults to the latest SUCCEEDED run.")) -> TrendOverviewResponse:
    """Historical Cohort Comparison summary.

    Every value here is read from a persisted trend_analysis_runs /
    trend_entity_snapshots / trend_scores row -- nothing is recalculated
    on this request. Returns classification and data-quality breakdowns
    for clusters and categories, the top Emerging/Stable/Cooling entities,
    and a mandatory `message` explaining that these results compare two
    disjoint ingestion cohorts (the corpus's January 2016 and July 2026
    batches), not a continuous publication trend. `trend_context.
    effective_trend_mode` is always "historical" in v1 -- Current Trend
    Mode does not exist yet, and this endpoint never claims otherwise.

    503 when no run has ever completed successfully (the feature has no
    data yet, not a missing resource). 404 only when an explicit `run_id`
    was given and doesn't exist.
    """
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, run_id)
        return TrendOverviewResponse(**api_queries.get_overview(session, run))
    finally:
        session.close()


@router.get("/clusters", response_model=TrendListResponse, responses={503: RESULTS_UNAVAILABLE, 404: RUN_NOT_FOUND})
def clusters(
    run_id: uuid.UUID | None = Query(None),
    classification: ClassificationParam | None = Query(None),
    data_quality: DataQualityParam | None = Query(None),
    min_score: float | None = Query(None, ge=0, le=100),
    limit: int = Query(api_queries.DEFAULT_LIMIT, ge=1, le=api_queries.MAX_LIMIT),
    offset: int = Query(0, ge=0),
    sort_by: SortByParam = Query("trend_score"),
    sort_order: SortOrderParam = Query("desc"),
) -> TrendListResponse:
    """Cluster-level Historical Cohort Comparison results (trend_type
    "cluster_growth"). Ranked by trend_score descending by default, with
    entity_name/entity_id as fixed tie-breakers regardless of sort_by --
    ordering is always fully deterministic, never left to incidental
    database row order."""
    return _entity_list(run_id, ENTITY_TYPE_CLUSTER, classification, data_quality, min_score, limit, offset, sort_by, sort_order)


@router.get("/categories", response_model=TrendListResponse, responses={503: RESULTS_UNAVAILABLE, 404: RUN_NOT_FOUND})
def categories(
    run_id: uuid.UUID | None = Query(None),
    classification: ClassificationParam | None = Query(None),
    data_quality: DataQualityParam | None = Query(None),
    min_score: float | None = Query(None, ge=0, le=100),
    limit: int = Query(api_queries.DEFAULT_LIMIT, ge=1, le=api_queries.MAX_LIMIT),
    offset: int = Query(0, ge=0),
    sort_by: SortByParam = Query("trend_score"),
    sort_order: SortOrderParam = Query("desc"),
) -> TrendListResponse:
    """Category-level (arXiv primary category) Historical Cohort
    Comparison results (trend_type "category_growth"). Same filtering,
    pagination, and deterministic-ordering behavior as /trends/clusters."""
    return _entity_list(run_id, ENTITY_TYPE_CATEGORY, classification, data_quality, min_score, limit, offset, sort_by, sort_order)


@router.get(
    "/emerging",
    response_model=TrendListResponse,
    responses={503: RESULTS_UNAVAILABLE, 404: RUN_NOT_FOUND},
)
def emerging(
    entity_type: EntityTypeParam | None = Query(None, description="Restrict to 'cluster' or 'category'; omit for both."),
    run_id: uuid.UUID | None = Query(None),
    limit: int = Query(api_queries.DEFAULT_LIMIT, ge=1, le=api_queries.MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> TrendListResponse:
    """Entities classified Emerging under the resolved run, across
    clusters and categories together unless entity_type narrows it."""
    return _classification_list(run_id, classifications.EMERGING, entity_type, limit, offset)


@router.get(
    "/cooling",
    response_model=TrendListResponse,
    responses={503: RESULTS_UNAVAILABLE, 404: RUN_NOT_FOUND},
)
def cooling(
    entity_type: EntityTypeParam | None = Query(None, description="Restrict to 'cluster' or 'category'; omit for both."),
    run_id: uuid.UUID | None = Query(None),
    limit: int = Query(api_queries.DEFAULT_LIMIT, ge=1, le=api_queries.MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> TrendListResponse:
    """Entities classified Cooling under the resolved run. Same shape as
    /trends/emerging."""
    return _classification_list(run_id, classifications.COOLING, entity_type, limit, offset)


@router.get(
    "/stable",
    response_model=TrendListResponse,
    responses={503: RESULTS_UNAVAILABLE, 404: RUN_NOT_FOUND},
)
def stable(
    entity_type: EntityTypeParam | None = Query(None, description="Restrict to 'cluster' or 'category'; omit for both."),
    run_id: uuid.UUID | None = Query(None),
    limit: int = Query(api_queries.DEFAULT_LIMIT, ge=1, le=api_queries.MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> TrendListResponse:
    """Entities classified Stable under the resolved run. Added for
    symmetry with /trends/emerging and /trends/cooling -- reuses the exact
    same query function, parametrized only by classification."""
    return _classification_list(run_id, classifications.STABLE, entity_type, limit, offset)


# Declared after the literal single-segment routes above for readability,
# though not load-bearing: FastAPI/Starlette route matching is by path
# *shape*, and every route above this one has a different segment count
# than /{entity_type}/{entity_id}, so no ordering collision is possible --
# same non-issue already documented for /papers/{paper_id} vs
# /papers/{paper_id}/similar.
@router.get(
    "/{entity_type}/{entity_id}",
    response_model=TrendDetailResponse,
    responses={404: ENTITY_NOT_FOUND, 503: RESULTS_UNAVAILABLE},
)
def entity_detail(
    entity_type: EntityTypeParam, entity_id: str, run_id: uuid.UUID | None = Query(None)
) -> TrendDetailResponse:
    """Full detail for one cluster or category: metrics, score, and every
    persisted evidence paper split by role (recent_period vs
    comparison_period), each ordered deterministically by
    (publication_date, paper_id). No evidence explanation is generated or
    inferred here -- every field is a direct join to trend_evidence_papers
    and papers."""
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, run_id)
        result, score_id = api_queries.get_entity_result(session, run.id, entity_type, entity_id)
        recent_evidence, comparison_evidence = api_queries.get_evidence_papers(session, score_id)
        return TrendDetailResponse(
            trend_context=api_queries.build_trend_context(run),
            result=result,
            recent_period_evidence=recent_evidence,
            comparison_period_evidence=comparison_evidence,
        )
    finally:
        session.close()
