"""Read-only source-data queries for the trend pipeline. Every function
here takes an already-open `session` (never opens its own SessionLocal())
so the pipeline can run the whole analysis inside one transaction and
control commit/rollback itself -- this module never calls session.commit()
or writes a row. Reuses the project's existing publication-date convention
(research_platform.embeddings.search.publication_date_subquery: v1 arXiv
submission date, falling back to first_observed_at) rather than defining a
second one. Excludes non-canonical papers everywhere, uses only the latest
SUCCEEDED clustering run, surfaces only APPROVED cluster labels, and always
keeps noise papers (is_noise=True) out of cluster-trend results.
"""
from datetime import datetime, timedelta
from typing import NamedTuple

from sqlalchemy import func, select

from research_platform.db.models import (
    Category,
    ClusterLabel,
    ClusteringRun,
    Paper,
    PaperClusterAssignment,
)
from research_platform.embeddings.search import publication_date_subquery

DEFAULT_RECENT_WINDOW_DAYS = 90


class PublicationDateRange(NamedTuple):
    earliest: datetime | None
    latest: datetime | None


class FreshnessAggregates(NamedTuple):
    total_canonical_papers: int
    days_since_latest_paper: int
    recent_period_paper_count: int
    comparison_period_paper_count: int
    recent_period_distinct_days: int
    recent_window_days: int


class EvidencePaperRow(NamedTuple):
    paper_id: str
    publication_date: datetime


def count_canonical_papers(session) -> int:
    return session.execute(
        select(func.count(Paper.id)).where(Paper.is_canonical.is_(True))
    ).scalar_one()


def get_publication_date_range(session) -> PublicationDateRange:
    """None/None when there are no canonical papers at all -- callers must
    handle that explicitly rather than assuming a date always exists."""
    v1_versions, publication_date_expr = publication_date_subquery()
    row = session.execute(
        select(func.min(publication_date_expr), func.max(publication_date_expr))
        .select_from(Paper)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(Paper.is_canonical.is_(True))
    ).one()
    return PublicationDateRange(earliest=row[0], latest=row[1])


def count_papers_in_window(session, window_start: datetime, window_end: datetime) -> int:
    """Corpus-wide canonical-paper count with an effective publication date
    in [window_start, window_end) -- the building block for every other
    windowed count in this module."""
    v1_versions, publication_date_expr = publication_date_subquery()
    return session.execute(
        select(func.count(Paper.id))
        .select_from(Paper)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(
            Paper.is_canonical.is_(True),
            publication_date_expr >= window_start,
            publication_date_expr < window_end,
        )
    ).scalar_one()


def count_distinct_publication_days(session, window_start: datetime, window_end: datetime) -> int:
    """Distinct calendar days (UTC) with at least one canonical paper's
    effective publication date inside the window -- used to detect
    ingestion-batch concentration (see trends.freshness)."""
    v1_versions, publication_date_expr = publication_date_subquery()
    day_expr = func.date_trunc("day", publication_date_expr)
    return session.execute(
        select(func.count(func.distinct(day_expr)))
        .select_from(Paper)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(
            Paper.is_canonical.is_(True),
            publication_date_expr >= window_start,
            publication_date_expr < window_end,
        )
    ).scalar_one()


def get_freshness_aggregates(
    session, *, now: datetime, recent_window_days: int = DEFAULT_RECENT_WINDOW_DAYS
) -> FreshnessAggregates:
    """Corpus-wide freshness inputs for trends.freshness.compute_freshness_status(),
    always measured against the real calendar `now` the caller supplies --
    independent of whatever historical cohort windows a given run is
    comparing."""
    total = count_canonical_papers(session)
    date_range = get_publication_date_range(session)

    if date_range.latest is None:
        return FreshnessAggregates(
            total_canonical_papers=total,
            days_since_latest_paper=0,
            recent_period_paper_count=0,
            comparison_period_paper_count=0,
            recent_period_distinct_days=0,
            recent_window_days=recent_window_days,
        )

    days_since_latest_paper = max(0, (now - date_range.latest).days)
    recent_start = now - timedelta(days=recent_window_days)
    comparison_start = now - timedelta(days=2 * recent_window_days)

    return FreshnessAggregates(
        total_canonical_papers=total,
        days_since_latest_paper=days_since_latest_paper,
        recent_period_paper_count=count_papers_in_window(session, recent_start, now),
        comparison_period_paper_count=count_papers_in_window(session, comparison_start, recent_start),
        recent_period_distinct_days=count_distinct_publication_days(session, recent_start, now),
        recent_window_days=recent_window_days,
    )


def list_distinct_publication_days(session) -> list[datetime]:
    """Every distinct calendar day (UTC, ascending) with at least one
    canonical paper's effective publication date -- the input the
    historical-cohort pipeline groups into cohorts (see
    trends.pipeline.resolve_cohort_windows()). Corpus-wide, no window
    filter: this is how cohort boundaries get discovered in the first
    place, not something computed from a window already known."""
    v1_versions, publication_date_expr = publication_date_subquery()
    day_expr = func.date_trunc("day", publication_date_expr)
    rows = session.execute(
        select(func.distinct(day_expr))
        .select_from(Paper)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(Paper.is_canonical.is_(True))
        .order_by(day_expr)
    ).all()
    return [day for (day,) in rows]


def get_latest_successful_clustering_run(session) -> ClusteringRun | None:
    return session.execute(
        select(ClusteringRun)
        .where(ClusteringRun.status == "SUCCEEDED")
        .order_by(ClusteringRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_approved_cluster_labels(session, clustering_run_id) -> list[ClusterLabel]:
    """Only review_status='APPROVED' labels -- the same convention already
    used by the read-facing cluster API (list_approved_clusters() /
    get_cluster_detail() in clustering/queries.py). A cluster whose label
    was never approved has no trustworthy display name and is excluded
    from trend results entirely, not shown with a placeholder name."""
    return list(
        session.execute(
            select(ClusterLabel)
            .where(
                ClusterLabel.clustering_run_id == clustering_run_id,
                ClusterLabel.review_status == "APPROVED",
            )
            .order_by(ClusterLabel.cluster_id)
        ).scalars()
    )


def count_cluster_papers_in_window(
    session, clustering_run_id, window_start: datetime, window_end: datetime
) -> dict[int, int]:
    """cluster_id -> paper count with an effective publication date inside
    the window, for the given run. is_noise rows are always excluded --
    noise papers never contribute to cluster-trend counts."""
    v1_versions, publication_date_expr = publication_date_subquery()
    rows = session.execute(
        select(PaperClusterAssignment.cluster_id, func.count(PaperClusterAssignment.paper_id))
        .select_from(PaperClusterAssignment)
        .join(Paper, Paper.id == PaperClusterAssignment.paper_id)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(
            PaperClusterAssignment.clustering_run_id == clustering_run_id,
            PaperClusterAssignment.is_noise.is_(False),
            Paper.is_canonical.is_(True),
            publication_date_expr >= window_start,
            publication_date_expr < window_end,
        )
        .group_by(PaperClusterAssignment.cluster_id)
    ).all()
    return {int(cluster_id): count for cluster_id, count in rows}


def count_category_papers_in_window(session, window_start: datetime, window_end: datetime) -> dict[str, int]:
    """category code -> paper count with an effective publication date
    inside the window, keyed on Paper.primary_category_id (the single
    stable per-paper category, not the paper_categories many-to-many
    table) -- the same denominator convention the rest of the app uses for
    "primary category"."""
    v1_versions, publication_date_expr = publication_date_subquery()
    rows = session.execute(
        select(Category.code, func.count(Paper.id))
        .select_from(Paper)
        .join(Category, Category.id == Paper.primary_category_id)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(
            Paper.is_canonical.is_(True),
            publication_date_expr >= window_start,
            publication_date_expr < window_end,
        )
        .group_by(Category.code)
    ).all()
    return {code: count for code, count in rows}


def get_all_primary_category_codes(session) -> list[str]:
    """Every distinct primary-category code with at least one canonical
    paper, regardless of window -- the universe of category entities a
    trend run should consider."""
    rows = session.execute(
        select(Category.code)
        .join(Paper, Paper.primary_category_id == Category.id)
        .where(Paper.is_canonical.is_(True))
        .distinct()
        .order_by(Category.code)
    ).all()
    return [code for (code,) in rows]


def select_cluster_evidence_papers(
    session, clustering_run_id, cluster_id: int, window_start: datetime, window_end: datetime, limit: int
) -> list[EvidencePaperRow]:
    """Deterministic evidence selection: ordered by (effective publication
    date, paper_id) so identical corpus state always yields the identical
    evidence set/order, never by citation count or any other
    popularity-flavored signal -- evidence documents which papers a count
    is made of, it does not argue the trend is important."""
    v1_versions, publication_date_expr = publication_date_subquery()
    rows = session.execute(
        select(Paper.id, publication_date_expr.label("publication_date"))
        .select_from(PaperClusterAssignment)
        .join(Paper, Paper.id == PaperClusterAssignment.paper_id)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(
            PaperClusterAssignment.clustering_run_id == clustering_run_id,
            PaperClusterAssignment.cluster_id == cluster_id,
            PaperClusterAssignment.is_noise.is_(False),
            Paper.is_canonical.is_(True),
            publication_date_expr >= window_start,
            publication_date_expr < window_end,
        )
        .order_by(publication_date_expr, Paper.id)
        .limit(limit)
    ).all()
    return [EvidencePaperRow(paper_id=str(paper_id), publication_date=publication_date) for paper_id, publication_date in rows]


def select_category_evidence_papers(
    session, category_code: str, window_start: datetime, window_end: datetime, limit: int
) -> list[EvidencePaperRow]:
    v1_versions, publication_date_expr = publication_date_subquery()
    rows = session.execute(
        select(Paper.id, publication_date_expr.label("publication_date"))
        .select_from(Paper)
        .join(Category, Category.id == Paper.primary_category_id)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(
            Category.code == category_code,
            Paper.is_canonical.is_(True),
            publication_date_expr >= window_start,
            publication_date_expr < window_end,
        )
        .order_by(publication_date_expr, Paper.id)
        .limit(limit)
    ).all()
    return [EvidencePaperRow(paper_id=str(paper_id), publication_date=publication_date) for paper_id, publication_date in rows]
