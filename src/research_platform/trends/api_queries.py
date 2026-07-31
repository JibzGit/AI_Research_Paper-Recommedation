"""Read-only API query layer for the trend endpoints. Every function here
opens and closes its own SessionLocal() -- the same per-request session
lifecycle papers/queries.py and clustering/queries.py already use, NOT the
injected-session style of trends/queries.py (that module is transactional
plumbing for the pipeline; this one serves single, independent HTTP
requests). Reads persisted rows from trend_analysis_runs /
trend_entity_snapshots / trend_scores / trend_evidence_papers only --
nothing here recomputes a score, calls a pure trends module, or writes a
row. Supports "cluster" and "category" entity types only in v1.
"""
import uuid
from datetime import timedelta

from sqlalchemy import func, select

from research_platform.db.models import Paper, TrendAnalysisRun, TrendEntitySnapshot, TrendEvidencePaper, TrendScore
from research_platform.db.session import SessionLocal
from research_platform.embeddings.search import publication_date_subquery
from research_platform.trends import classifications
from research_platform.trends.pipeline import ENTITY_TYPE_CATEGORY, ENTITY_TYPE_CLUSTER

MAX_LIMIT = 100
DEFAULT_LIMIT = 20
OVERVIEW_TOP_N = 5
SUPPORTED_ENTITY_TYPES = (ENTITY_TYPE_CLUSTER, ENTITY_TYPE_CATEGORY)
SORTABLE_FIELDS = ("trend_score", "growth_rate", "recent_paper_count", "entity_name")


class TrendRunNotFoundError(ValueError):
    """Raised only when an explicitly requested run_id does not match any
    TrendAnalysisRun row at all -- a run that exists but is RUNNING/FAILED
    is still "found" (its results are legitimately empty, not an error)."""


class TrendEntityNotFoundError(ValueError):
    """Raised when (entity_type, entity_id) has no persisted TrendScore
    row under the resolved run -- covers an entity_id that never existed
    and one that exists but wasn't scored in that particular run."""


class TrendResultsUnavailableError(ValueError):
    """Raised only when no run_id was given AND no SUCCEEDED
    TrendAnalysisRun exists at all -- the trend feature has not produced
    any usable results yet. Maps to 503, not 404: this is "not ready", not
    "doesn't exist"."""


def _coerce_run_id(run_id) -> uuid.UUID:
    if isinstance(run_id, uuid.UUID):
        return run_id
    try:
        return uuid.UUID(str(run_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"run_id must be a valid UUID; got {run_id!r}") from exc


def get_latest_successful_trend_run(session) -> TrendAnalysisRun | None:
    return session.execute(
        select(TrendAnalysisRun)
        .where(TrendAnalysisRun.status == "SUCCEEDED")
        .order_by(TrendAnalysisRun.completed_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def resolve_trend_run(session, run_id) -> TrendAnalysisRun:
    """Default (run_id=None): latest SUCCEEDED run, or
    TrendResultsUnavailableError (-> 503) if none exists yet. Explicit
    run_id: that exact run regardless of status, or TrendRunNotFoundError
    (-> 404) if it doesn't exist at all -- never silently substitutes the
    latest run for a run_id the caller explicitly asked for."""
    if run_id is None:
        run = get_latest_successful_trend_run(session)
        if run is None:
            raise TrendResultsUnavailableError("no successful trend analysis run is available yet")
        return run

    run_uuid = _coerce_run_id(run_id)
    run = session.get(TrendAnalysisRun, run_uuid)
    if run is None:
        raise TrendRunNotFoundError(f"trend run not found: {run_id}")
    return run


def build_trend_context(run: TrendAnalysisRun) -> dict:
    trend_mode_label = (
        classifications.HISTORICAL_COHORT_COMPARISON_LABEL
        if run.effective_trend_mode == "historical"
        else classifications.CURRENT_TRENDS_LABEL
    )
    return {
        "run_id": str(run.id),
        "calculation_version": run.calculation_version,
        "requested_trend_mode": run.requested_trend_mode,
        "effective_trend_mode": run.effective_trend_mode,
        "trend_mode_label": trend_mode_label,
        "freshness_status": run.freshness_status,
        "status": run.status,
        "window_granularity": run.window_granularity,
        "comparison_period_start": run.comparison_period_start,
        "comparison_period_end": run.comparison_period_end,
        "recent_period_start": run.recent_period_start,
        "recent_period_end": run.recent_period_end,
        "total_canonical_papers": run.total_canonical_papers,
        "calculated_at": run.completed_at,
    }


def _evidence_counts_by_score(session, score_ids: list) -> dict:
    """entity trend_score_id -> {"recent_period": n, "comparison_period": n}.
    One grouped query for however many scores the caller is about to
    render, instead of one query per entity (avoids N+1 on list
    endpoints)."""
    if not score_ids:
        return {}
    rows = session.execute(
        select(TrendEvidencePaper.trend_score_id, TrendEvidencePaper.role, func.count())
        .where(TrendEvidencePaper.trend_score_id.in_(score_ids))
        .group_by(TrendEvidencePaper.trend_score_id, TrendEvidencePaper.role)
    ).all()
    counts: dict = {}
    for score_id, role, count in rows:
        counts.setdefault(score_id, {"recent_period": 0, "comparison_period": 0})[role] = count
    return counts


def _snapshot_to_metrics(snapshot: TrendEntitySnapshot) -> dict:
    return {
        "recent_paper_count": snapshot.recent_paper_count,
        "previous_paper_count": snapshot.previous_paper_count,
        "absolute_growth": snapshot.absolute_growth,
        "growth_rate": snapshot.growth_rate,
        "is_new_activity": snapshot.is_new_activity,
        "recent_publication_share": snapshot.recent_publication_share,
        "previous_publication_share": snapshot.previous_publication_share,
        "share_change": snapshot.share_change,
        "acceleration": snapshot.acceleration,
        "consistency": snapshot.consistency,
        "recency_score": snapshot.recency_score,
        "total_papers": snapshot.total_papers,
    }


def _score_to_schema(score: TrendScore) -> dict:
    return {
        "trend_type": score.trend_type,
        "trend_score": score.trend_score,
        "momentum_score": score.momentum_score,
        "trend_classification": score.trend_classification,
        "data_quality_level": score.data_quality_level,
        "component_breakdown": score.component_breakdown,
    }


def _build_result(snapshot: TrendEntitySnapshot, score: TrendScore, evidence_counts: dict) -> dict:
    counts = evidence_counts.get(score.id, {"recent_period": 0, "comparison_period": 0})
    return {
        "entity_type": snapshot.entity_type,
        "entity_id": snapshot.entity_id,
        "entity_name": snapshot.entity_name,
        "metrics": _snapshot_to_metrics(snapshot),
        "score": _score_to_schema(score),
        "evidence_summary": {
            "recent_period_count": counts.get("recent_period", 0),
            "comparison_period_count": counts.get("comparison_period", 0),
        },
    }


def _base_query(run_id, entity_type: str):
    return (
        select(TrendEntitySnapshot, TrendScore)
        .join(
            TrendScore,
            (TrendScore.trend_run_id == TrendEntitySnapshot.trend_run_id)
            & (TrendScore.entity_type == TrendEntitySnapshot.entity_type)
            & (TrendScore.entity_id == TrendEntitySnapshot.entity_id),
        )
        .where(TrendEntitySnapshot.trend_run_id == run_id, TrendEntitySnapshot.entity_type == entity_type)
    )


def _apply_sort(stmt, sort_by: str, sort_order: str):
    """entity_name/entity_id are always appended as tie-breakers, whatever
    the caller's primary sort_by/sort_order is -- deterministic ordering
    is never left to the database's arbitrary row order."""
    if sort_by not in SORTABLE_FIELDS:
        raise ValueError(f"sort_by must be one of {SORTABLE_FIELDS}; got {sort_by!r}")
    if sort_order not in ("asc", "desc"):
        raise ValueError(f"sort_order must be 'asc' or 'desc'; got {sort_order!r}")

    column = {
        "trend_score": TrendScore.trend_score,
        "growth_rate": TrendEntitySnapshot.growth_rate,
        "recent_paper_count": TrendEntitySnapshot.recent_paper_count,
        "entity_name": TrendEntitySnapshot.entity_name,
    }[sort_by]
    primary = column.asc().nulls_last() if sort_order == "asc" else column.desc().nulls_last()
    return stmt.order_by(primary, TrendEntitySnapshot.entity_name.asc(), TrendEntitySnapshot.entity_id.asc())


def get_entity_results(
    session,
    run_id,
    entity_type: str,
    *,
    classification: str | None = None,
    data_quality: str | None = None,
    min_score: float | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    sort_by: str = "trend_score",
    sort_order: str = "desc",
) -> tuple[int, list[dict]]:
    """Paginated, filtered, deterministically-ordered results for one
    entity_type ('cluster' or 'category') under the given run."""
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {SUPPORTED_ENTITY_TYPES}; got {entity_type!r}")

    stmt = _base_query(run_id, entity_type)
    if classification is not None:
        stmt = stmt.where(TrendScore.trend_classification == classification)
    if data_quality is not None:
        stmt = stmt.where(TrendScore.data_quality_level == data_quality)
    if min_score is not None:
        stmt = stmt.where(TrendScore.trend_score >= min_score)

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    stmt = _apply_sort(stmt, sort_by, sort_order).limit(limit).offset(offset)
    rows = session.execute(stmt).all()

    evidence_counts = _evidence_counts_by_score(session, [score.id for _, score in rows])
    results = [_build_result(snapshot, score, evidence_counts) for snapshot, score in rows]
    return total, results


def get_entity_result(session, run_id, entity_type: str, entity_id: str) -> tuple[dict, uuid.UUID]:
    """Returns (result_dict, trend_score_id) -- the raw score id is not
    part of the public TrendResult shape, but the detail endpoint needs it
    to separately fetch this entity's evidence papers."""
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {SUPPORTED_ENTITY_TYPES}; got {entity_type!r}")

    row = session.execute(_base_query(run_id, entity_type).where(TrendEntitySnapshot.entity_id == entity_id)).first()
    if row is None:
        raise TrendEntityNotFoundError(f"no trend result for {entity_type}={entity_id} in run {run_id}")
    snapshot, score = row
    evidence_counts = _evidence_counts_by_score(session, [score.id])
    return _build_result(snapshot, score, evidence_counts), score.id


def get_results_by_classification(
    session, run_id, classification: str, *, entity_type: str | None = None, limit: int = DEFAULT_LIMIT, offset: int = 0,
) -> tuple[int, list[dict]]:
    """Backs /trends/emerging, /trends/cooling, and /trends/stable --
    identical shape for all three, parametrized only by which
    classification string to filter on. entity_type is optional: omitted
    means "across both clusters and categories together"."""
    if entity_type is not None and entity_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {SUPPORTED_ENTITY_TYPES}; got {entity_type!r}")

    stmt = (
        select(TrendEntitySnapshot, TrendScore)
        .join(
            TrendScore,
            (TrendScore.trend_run_id == TrendEntitySnapshot.trend_run_id)
            & (TrendScore.entity_type == TrendEntitySnapshot.entity_type)
            & (TrendScore.entity_id == TrendEntitySnapshot.entity_id),
        )
        .where(TrendScore.trend_run_id == run_id, TrendScore.trend_classification == classification)
    )
    if entity_type is not None:
        stmt = stmt.where(TrendScore.entity_type == entity_type)

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    stmt = stmt.order_by(
        TrendScore.trend_score.desc(), TrendEntitySnapshot.entity_name.asc(), TrendEntitySnapshot.entity_id.asc()
    ).limit(limit).offset(offset)
    rows = session.execute(stmt).all()

    evidence_counts = _evidence_counts_by_score(session, [score.id for _, score in rows])
    results = [_build_result(snapshot, score, evidence_counts) for snapshot, score in rows]
    return total, results


def get_evidence_papers(session, trend_score_id) -> tuple[list[dict], list[dict]]:
    """(recent_period, comparison_period) evidence paper lists, each
    ordered by (publication_date, paper_id) -- the same deterministic
    order the pipeline used to select them, never re-sorted by anything
    popularity-flavored. Returns ([], []) for an unknown trend_score_id
    rather than raising -- callers already resolved the entity/score
    before calling this, so an empty pair here means "no evidence rows",
    a legitimate (if unlikely) state, not a not-found condition."""
    v1_versions, publication_date_expr = publication_date_subquery()
    rows = session.execute(
        select(
            TrendEvidencePaper.role,
            Paper.id.label("paper_id"),
            Paper.title,
            Paper.arxiv_id,
            publication_date_expr.label("publication_date"),
        )
        .select_from(TrendEvidencePaper)
        .join(Paper, Paper.id == TrendEvidencePaper.paper_id)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(TrendEvidencePaper.trend_score_id == trend_score_id)
        .order_by(publication_date_expr, Paper.id)
    ).all()

    recent, comparison = [], []
    for role, paper_id, title, arxiv_id, publication_date in rows:
        item = {
            "paper_id": str(paper_id),
            "title": title,
            "arxiv_id": arxiv_id,
            "publication_date": publication_date,
            "role": role,
        }
        (recent if role == "recent_period" else comparison).append(item)
    return recent, comparison


def get_classification_counts(session, run_id, entity_type: str) -> dict[str, int]:
    rows = session.execute(
        select(TrendScore.trend_classification, func.count())
        .join(
            TrendEntitySnapshot,
            (TrendScore.trend_run_id == TrendEntitySnapshot.trend_run_id)
            & (TrendScore.entity_type == TrendEntitySnapshot.entity_type)
            & (TrendScore.entity_id == TrendEntitySnapshot.entity_id),
        )
        .where(TrendScore.trend_run_id == run_id, TrendScore.entity_type == entity_type)
        .group_by(TrendScore.trend_classification)
    ).all()
    return {classification: count for classification, count in rows}


def get_data_quality_counts(session, run_id, entity_type: str | None = None) -> dict[str, int]:
    stmt = select(TrendScore.data_quality_level, func.count()).where(TrendScore.trend_run_id == run_id)
    if entity_type is not None:
        stmt = stmt.where(TrendScore.entity_type == entity_type)
    rows = session.execute(stmt.group_by(TrendScore.data_quality_level)).all()
    return {level: count for level, count in rows}


def _entity_type_summary(session, run_id, entity_type: str) -> dict:
    total_entities = session.execute(
        select(func.count()).select_from(TrendEntitySnapshot).where(
            TrendEntitySnapshot.trend_run_id == run_id, TrendEntitySnapshot.entity_type == entity_type
        )
    ).scalar_one()
    return {
        "entity_type": entity_type,
        "total_entities": total_entities,
        "classification_counts": get_classification_counts(session, run_id, entity_type),
        "data_quality_counts": get_data_quality_counts(session, run_id, entity_type),
    }


def _top_by_classification(session, run_id, classification: str, limit: int) -> list[dict]:
    """Thin wrapper over get_results_by_classification() -- overview only
    ever wants the top page (no total, no explicit entity_type filter),
    so this discards what it doesn't need rather than duplicating the
    query."""
    _total, results = get_results_by_classification(session, run_id, classification, limit=limit, offset=0)
    return results


def get_overview(session, run) -> dict:
    """Corpus-wide summary for GET /trends/overview. message is the
    mandatory, prominent warning that these numbers compare two ingestion
    cohorts, not a continuous trend -- concrete cohort dates are
    interpolated in so the warning is specific, not generic boilerplate."""
    cluster_summary = _entity_type_summary(session, run.id, ENTITY_TYPE_CLUSTER)
    category_summary = _entity_type_summary(session, run.id, ENTITY_TYPE_CATEGORY)
    data_quality_summary = get_data_quality_counts(session, run.id)

    top_emerging = _top_by_classification(session, run.id, classifications.EMERGING, OVERVIEW_TOP_N)
    top_stable = _top_by_classification(session, run.id, classifications.STABLE, OVERVIEW_TOP_N)
    top_cooling = _top_by_classification(session, run.id, classifications.COOLING, OVERVIEW_TOP_N)

    # *_period_end are exclusive upper bounds (trends/pipeline.py's
    # resolve_cohort_windows() defines a window as [start, last_day + 1
    # day)) -- subtract a day so the message names the actual last
    # included date, not the day after the cohort ends.
    comparison_start = run.comparison_period_start.date().isoformat()
    comparison_end = (run.comparison_period_end.date() - timedelta(days=1)).isoformat()
    recent_start = run.recent_period_start.date().isoformat()
    recent_end = (run.recent_period_end.date() - timedelta(days=1)).isoformat()
    message = (
        "These results are a Historical Cohort Comparison, not a continuous publication trend. "
        f"Comparison cohort: papers published {comparison_start} to {comparison_end}. "
        f"Recent cohort: papers published {recent_start} to {recent_end}. "
        "The corpus currently contains two disjoint ingestion batches with a multi-year gap between "
        "them, not a continuously sampled publication history -- these numbers describe how those two "
        "specific batches compare to each other, not organic month-over-month research momentum."
    )

    return {
        "trend_context": build_trend_context(run),
        "cluster_summary": cluster_summary,
        "category_summary": category_summary,
        "data_quality_summary": data_quality_summary,
        "top_emerging": top_emerging,
        "top_stable": top_stable,
        "top_cooling": top_cooling,
        "message": message,
    }
