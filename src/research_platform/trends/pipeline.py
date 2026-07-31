"""Historical Cohort Comparison pipeline: compares the two disjoint
ingestion batches this corpus actually contains (the earliest cohort --
today, the January 2016 sample/quota-ingestion batch -- and the most
recent cohort -- today, the July 2026 quota-ingestion batch) for every
approved cluster and primary category, using only the pure deterministic
modules in metrics.py / scoring.py / classifications.py / freshness.py.

This is a two-snapshot comparison, not a continuous month-over-month
trend -- every result this pipeline produces is labeled
classifications.HISTORICAL_COHORT_COMPARISON_LABEL ("Historical Cohort
Comparison"), never "Trending Now" or any current-momentum phrasing.
Current Trend Mode is not implemented here at all: every run this module
creates has requested_trend_mode="historical",
effective_trend_mode="historical" (see freshness.resolve_trend_request()
for how a genuine current-mode request would be handled -- this pipeline
never calls it with "current").

No citation-momentum or paper-momentum trend_type is ever inserted -- the
corpus has exactly one metric-snapshot date per paper (no citation time
series exists to measure), so this pipeline only ever writes
trend_type in {"cluster_growth", "category_growth"}.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from research_platform.db.models import (
    TrendAnalysisRun,
    TrendEntitySnapshot,
    TrendEvidencePaper,
    TrendScore,
)
from research_platform.db.session import SessionLocal
from research_platform.trends import classifications, freshness, metrics, queries, scoring

CALCULATION_VERSION = "trend-v1.0"
WINDOW_GRANULARITY = "snapshot"
REQUESTED_TREND_MODE = "historical"
EFFECTIVE_TREND_MODE = "historical"

ENTITY_TYPE_CLUSTER = "cluster"
ENTITY_TYPE_CATEGORY = "category"
TREND_TYPE_CLUSTER_GROWTH = "cluster_growth"
TREND_TYPE_CATEGORY_GROWTH = "category_growth"

EVIDENCE_ROLE_RECENT = "recent_period"
EVIDENCE_ROLE_COMPARISON = "comparison_period"

DEFAULT_EVIDENCE_LIMIT = 10
DEFAULT_COHORT_GAP_DAYS = 30

# This pipeline only ever has two comparison windows (comparison, recent) --
# not the >=4-window history "Consistently Active" and "acceleration" were
# designed around (see metrics.compute_acceleration's own 3-point minimum).
# consistency maxes out at 1.0 with only two windows, so passing the
# classifier's default 0.75 threshold would let "both cohorts have any
# activity at all" masquerade as "consistently active across many windows"
# -- e.g. Cluster 5 (11 vs 11, flat) would wrongly outrank Stable. Raising
# the threshold above consistency's own maximum disables that branch for
# this 2-window regime without touching classifications.py itself; a
# future multi-run pipeline with >=3 real windows can pass the normal
# 0.75 default instead.
HISTORICAL_COHORT_CONSISTENCY_THRESHOLD = 1.01

_CONNECTION_STRING_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s]*@[^\s]*")


def _safe_error_message(exc: Exception) -> str:
    """Never persists a raw connection string/DSN, even if some underlying
    driver exception happened to include one -- same posture as the API's
    unhandled_exception_handler never leaking internals to a client,
    applied here to a row stored in our own database instead."""
    message = f"{type(exc).__name__}: {exc}"
    redacted = _CONNECTION_STRING_RE.sub("[redacted-connection-string]", message)
    return redacted[:1000]


class CohortWindows(NamedTuple):
    comparison_start: datetime
    comparison_end: datetime
    recent_start: datetime
    recent_end: datetime


def _group_consecutive_days(days: list[datetime], gap_threshold_days: int) -> list[list[datetime]]:
    if not days:
        return []
    groups = [[days[0]]]
    for day in days[1:]:
        if (day - groups[-1][-1]).days > gap_threshold_days:
            groups.append([day])
        else:
            groups[-1].append(day)
    return groups


def resolve_cohort_windows(session, *, gap_threshold_days: int = DEFAULT_COHORT_GAP_DAYS) -> CohortWindows:
    """Finds the two historical ingestion cohorts this corpus actually
    contains by grouping distinct publication days wherever the gap
    between consecutive active days exceeds gap_threshold_days -- not
    hardcoded to literal "January 2016" / "July 2026" dates, so this stays
    correct if/when more historical batches are ingested later. The
    earliest group becomes the comparison cohort, the latest group becomes
    the recent cohort.

    Raises ValueError when there are fewer than 2 distinct publication
    days, or when every active day collapses into a single group (no real
    gap exists) -- both mean there is nothing to compare."""
    days = queries.list_distinct_publication_days(session)
    if len(days) < 2:
        raise ValueError("fewer than 2 distinct publication days exist -- cannot resolve a two-cohort comparison")
    groups = _group_consecutive_days(days, gap_threshold_days)
    if len(groups) < 2:
        raise ValueError(
            f"only one publication cohort detected (all {len(days)} distinct days are within "
            f"{gap_threshold_days} days of each other) -- cannot resolve a two-cohort comparison"
        )
    comparison_group = groups[0]
    recent_group = groups[-1]
    return CohortWindows(
        comparison_start=comparison_group[0],
        comparison_end=comparison_group[-1] + timedelta(days=1),
        recent_start=recent_group[0],
        recent_end=recent_group[-1] + timedelta(days=1),
    )


def _entity_recency_days(
    recent_count: int, previous_count: int, cohorts: CohortWindows, now: datetime
) -> float:
    """Recency relative to whichever cohort actually contains this
    entity's papers -- the recent cohort if it has any, else the
    comparison cohort. Window ends are used as a same-day approximation of
    each cohort's true latest date (recency is a day-granularity signal,
    so this is accurate to within one day)."""
    if recent_count > 0:
        reference = cohorts.recent_end
    elif previous_count > 0:
        reference = cohorts.comparison_end
    else:
        return 0.0
    days_since = max(0, (now - reference).days)
    return metrics.compute_recency(days_since)


class EntityTrendInputs(NamedTuple):
    entity_type: str
    entity_id: str
    entity_name: str
    recent_count: int
    previous_count: int


def _score_entity(
    entity: EntityTrendInputs,
    *,
    cohorts: CohortWindows,
    now: datetime,
    max_recent_count: int,
    recent_total: int,
    previous_total: int,
    recent_period_distinct_days: int,
    min_support_total: int,
    min_support_period: int,
) -> dict:
    """Runs one entity through every pure metrics/scoring/classification
    function -- no database access here, purely composing the already-
    committed, unit-tested trends modules over already-fetched counts."""
    growth = metrics.compute_growth_rate(entity.recent_count, entity.previous_count)
    absolute_growth = metrics.compute_absolute_growth(entity.recent_count, entity.previous_count)
    # total_papers = recent + previous, not a separate "all-time" query:
    # in this two-cohort phase the corpus IS exactly these two windows, so
    # summing them is both correct and avoids implying a third bucket that
    # doesn't exist (see pipeline module docstring / design deviations).
    total_papers = entity.recent_count + entity.previous_count

    recent_share = metrics.compute_publication_share(entity.recent_count, recent_total)
    previous_share = metrics.compute_publication_share(entity.previous_count, previous_total)
    share_change = metrics.compute_share_change(recent_share, previous_share)

    # Only two windows exist -> acceleration can never be computed (needs
    # >=3 consecutive non-null growth rates); consistency is still
    # reported (see HISTORICAL_COHORT_CONSISTENCY_THRESHOLD for why it
    # can't unlock "Consistently Active" in this phase).
    acceleration = metrics.compute_acceleration([])
    consistency = metrics.compute_consistency([entity.previous_count > 0, entity.recent_count > 0])
    recency = _entity_recency_days(entity.recent_count, entity.previous_count, cohorts, now)
    momentum = metrics.compute_momentum(entity.recent_count, growth.growth_rate, max_recent_count)

    support_factor = scoring.compute_support_factor(total_papers, min_support_total=min_support_total)
    components = scoring.TrendScoreComponents(
        recent_volume_component=scoring.recent_volume_component(entity.recent_count, max_recent_count),
        growth_rate_component=scoring.growth_rate_component(growth.growth_rate),
        share_change_component=scoring.share_change_component(share_change),
        acceleration_component=scoring.acceleration_component(acceleration),
        recency_component=scoring.recency_component(recency),
        consistency_component=scoring.consistency_component(consistency),
    )
    trend_score = scoring.compute_trend_score(components, support_factor)

    classification = classifications.classify_trend(
        total_papers=total_papers,
        recent_count=entity.recent_count,
        previous_count=entity.previous_count,
        growth_rate=growth.growth_rate,
        is_new_activity=growth.is_new_activity,
        acceleration=acceleration,
        consistency=consistency,
        min_support_total=min_support_total,
        min_support_period=min_support_period,
        consistency_threshold=HISTORICAL_COHORT_CONSISTENCY_THRESHOLD,
    )
    # recent_window_days is deliberately the standard 90-day reference
    # period, not the (much shorter) literal span of the detected recent
    # cohort: the concentration check exists to answer "if this were a
    # normal rolling window, would the activity look suspiciously bunched
    # up?" -- using the cohort's own 1-day span as the denominator would
    # hide exactly the signal it's meant to catch (see pipeline module
    # design notes / final report deviations).
    data_quality_level = classifications.compute_data_quality_level(
        total_papers=total_papers,
        previous_count=entity.previous_count,
        recent_period_distinct_days=recent_period_distinct_days,
        recent_window_days=queries.DEFAULT_RECENT_WINDOW_DAYS,
        min_support_total=min_support_total,
        min_support_period=min_support_period,
    )

    return {
        "entity": entity,
        "total_papers": total_papers,
        "absolute_growth": absolute_growth,
        "growth_rate": growth.growth_rate,
        "is_new_activity": growth.is_new_activity,
        "recent_share": recent_share,
        "previous_share": previous_share,
        "share_change": share_change,
        "acceleration": acceleration,
        "consistency": consistency,
        "recency": recency,
        "momentum": momentum,
        "trend_score": trend_score,
        "component_breakdown": components._asdict(),
        "trend_classification": classification,
        "data_quality_level": data_quality_level,
        "support_factor": support_factor,
    }


def _persist_entity_result(
    session,
    *,
    run_id,
    clustering_run_id,
    trend_type: str,
    result: dict,
    cohorts: CohortWindows,
    evidence_limit: int,
    now: datetime,
) -> None:
    """Writes one TrendEntitySnapshot + one TrendScore + up to
    2*evidence_limit TrendEvidencePaper rows for a single already-scored
    entity. No calculation happens here -- result is exactly what
    _score_entity() returned; this function only shapes it into rows."""
    entity = result["entity"]

    session.add(
        TrendEntitySnapshot(
            trend_run_id=run_id,
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
            entity_name=entity.entity_name,
            recent_paper_count=entity.recent_count,
            previous_paper_count=entity.previous_count,
            absolute_growth=result["absolute_growth"],
            growth_rate=result["growth_rate"],
            is_new_activity=result["is_new_activity"],
            recent_publication_share=result["recent_share"],
            previous_publication_share=result["previous_share"],
            share_change=result["share_change"],
            acceleration=result["acceleration"],
            consistency=result["consistency"],
            recency_score=result["recency"],
            total_papers=result["total_papers"],
            created_at=now,
        )
    )

    score_id = uuid.uuid4()
    session.add(
        TrendScore(
            id=score_id,
            trend_run_id=run_id,
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
            trend_type=trend_type,
            trend_score=result["trend_score"],
            momentum_score=result["momentum"],
            trend_classification=result["trend_classification"],
            data_quality_level=result["data_quality_level"],
            component_breakdown=result["component_breakdown"],
            generated_explanation=None,
            explanation_model=None,
            created_at=now,
        )
    )

    if entity.entity_type == ENTITY_TYPE_CLUSTER:
        recent_evidence = queries.select_cluster_evidence_papers(
            session, clustering_run_id, int(entity.entity_id), cohorts.recent_start, cohorts.recent_end, evidence_limit
        )
        comparison_evidence = queries.select_cluster_evidence_papers(
            session, clustering_run_id, int(entity.entity_id), cohorts.comparison_start, cohorts.comparison_end, evidence_limit
        )
    else:
        recent_evidence = queries.select_category_evidence_papers(
            session, entity.entity_id, cohorts.recent_start, cohorts.recent_end, evidence_limit
        )
        comparison_evidence = queries.select_category_evidence_papers(
            session, entity.entity_id, cohorts.comparison_start, cohorts.comparison_end, evidence_limit
        )

    for evidence_row in recent_evidence:
        session.add(
            TrendEvidencePaper(
                trend_score_id=score_id,
                paper_id=uuid.UUID(evidence_row.paper_id),
                role=EVIDENCE_ROLE_RECENT,
                created_at=now,
            )
        )
    for evidence_row in comparison_evidence:
        session.add(
            TrendEvidencePaper(
                trend_score_id=score_id,
                paper_id=uuid.UUID(evidence_row.paper_id),
                role=EVIDENCE_ROLE_COMPARISON,
                created_at=now,
            )
        )


def run_historical_cohort_pipeline(
    *,
    calculation_version: str = CALCULATION_VERSION,
    min_support_total: int = metrics.DEFAULT_MIN_SUPPORT_TOTAL,
    min_support_period: int = metrics.DEFAULT_MIN_SUPPORT_PERIOD,
    evidence_limit: int = DEFAULT_EVIDENCE_LIMIT,
    cohort_gap_days: int = DEFAULT_COHORT_GAP_DAYS,
    dry_run: bool = False,
) -> dict:
    """Runs one Historical Cohort Comparison over every approved cluster
    and every primary category present in the corpus. Always
    requested_trend_mode="historical" / effective_trend_mode="historical"
    -- this function never accepts or produces a "current" mode result
    (see freshness.resolve_trend_request(), which this pipeline calls only
    to confirm a historical comparison is actually available before doing
    any work).

    dry_run=True computes and returns the full summary without writing
    anything to the database at all -- no TrendAnalysisRun row, no
    snapshots, no scores, no evidence.

    Deterministic for identical corpus state and parameters: every input
    comes from queries.py's deterministic reads and the pure trends
    modules, with no randomness and no wall-clock dependency in the
    scoring path itself (`now` is captured once, up front, and threaded
    through consistently)."""
    now = datetime.now(timezone.utc)
    parameters = {
        "min_support_total": min_support_total,
        "min_support_period": min_support_period,
        "evidence_limit": evidence_limit,
        "cohort_gap_days": cohort_gap_days,
        "consistency_threshold": HISTORICAL_COHORT_CONSISTENCY_THRESHOLD,
        "recent_window_days_reference": queries.DEFAULT_RECENT_WINDOW_DAYS,
    }

    session = SessionLocal()
    run = None
    try:
        cohorts = resolve_cohort_windows(session, gap_threshold_days=cohort_gap_days)
        date_range = queries.get_publication_date_range(session)
        freshness_aggregates = queries.get_freshness_aggregates(session, now=now)
        freshness_status = freshness.compute_freshness_status(**freshness_aggregates._asdict())
        mode_resolution = freshness.resolve_trend_request(REQUESTED_TREND_MODE, freshness_status)
        if mode_resolution.resolved_state == freshness.HISTORICAL_UNAVAILABLE:
            raise ValueError(f"historical cohort comparison unavailable: {mode_resolution.reason}")

        recent_period_distinct_days_capped = min(
            queries.count_distinct_publication_days(session, cohorts.recent_start, cohorts.recent_end),
            queries.DEFAULT_RECENT_WINDOW_DAYS,
        )

        latest_clustering_run = queries.get_latest_successful_clustering_run(session)
        if latest_clustering_run is None:
            raise ValueError("no successful clustering run exists -- cannot compute cluster trends")

        run = TrendAnalysisRun(
            id=uuid.uuid4(),
            calculation_version=calculation_version,
            requested_trend_mode=REQUESTED_TREND_MODE,
            effective_trend_mode=EFFECTIVE_TREND_MODE,
            freshness_status=freshness_status,
            corpus_latest_publication_date=date_range.latest,
            recent_period_start=cohorts.recent_start,
            recent_period_end=cohorts.recent_end,
            comparison_period_start=cohorts.comparison_start,
            comparison_period_end=cohorts.comparison_end,
            window_granularity=WINDOW_GRANULARITY,
            parameters=parameters,
            total_canonical_papers=freshness_aggregates.total_canonical_papers,
            status="RUNNING",
            created_at=now,
        )
        if not dry_run:
            session.add(run)
            session.commit()

        try:
            cluster_results = []
            approved_labels = queries.get_approved_cluster_labels(session, latest_clustering_run.id)
            cluster_recent_counts = queries.count_cluster_papers_in_window(
                session, latest_clustering_run.id, cohorts.recent_start, cohorts.recent_end
            )
            cluster_previous_counts = queries.count_cluster_papers_in_window(
                session, latest_clustering_run.id, cohorts.comparison_start, cohorts.comparison_end
            )
            cluster_recent_total = sum(cluster_recent_counts.values())
            cluster_previous_total = sum(cluster_previous_counts.values())
            cluster_max_recent = max(cluster_recent_counts.values(), default=0)

            for label in approved_labels:
                entity = EntityTrendInputs(
                    entity_type=ENTITY_TYPE_CLUSTER,
                    entity_id=str(label.cluster_id),
                    entity_name=label.cluster_name or f"Cluster {label.cluster_id}",
                    recent_count=cluster_recent_counts.get(label.cluster_id, 0),
                    previous_count=cluster_previous_counts.get(label.cluster_id, 0),
                )
                result = _score_entity(
                    entity,
                    cohorts=cohorts,
                    now=now,
                    max_recent_count=cluster_max_recent,
                    recent_total=cluster_recent_total,
                    previous_total=cluster_previous_total,
                    recent_period_distinct_days=recent_period_distinct_days_capped,
                    min_support_total=min_support_total,
                    min_support_period=min_support_period,
                )
                cluster_results.append(result)
                if not dry_run:
                    _persist_entity_result(
                        session,
                        run_id=run.id,
                        clustering_run_id=latest_clustering_run.id,
                        trend_type=TREND_TYPE_CLUSTER_GROWTH,
                        result=result,
                        cohorts=cohorts,
                        evidence_limit=evidence_limit,
                        now=now,
                    )

            category_results = []
            category_codes = queries.get_all_primary_category_codes(session)
            category_recent_counts = queries.count_category_papers_in_window(session, cohorts.recent_start, cohorts.recent_end)
            category_previous_counts = queries.count_category_papers_in_window(
                session, cohorts.comparison_start, cohorts.comparison_end
            )
            category_recent_total = sum(category_recent_counts.values())
            category_previous_total = sum(category_previous_counts.values())
            category_max_recent = max(category_recent_counts.values(), default=0)

            for code in category_codes:
                entity = EntityTrendInputs(
                    entity_type=ENTITY_TYPE_CATEGORY,
                    entity_id=code,
                    entity_name=code,
                    recent_count=category_recent_counts.get(code, 0),
                    previous_count=category_previous_counts.get(code, 0),
                )
                result = _score_entity(
                    entity,
                    cohorts=cohorts,
                    now=now,
                    max_recent_count=category_max_recent,
                    recent_total=category_recent_total,
                    previous_total=category_previous_total,
                    recent_period_distinct_days=recent_period_distinct_days_capped,
                    min_support_total=min_support_total,
                    min_support_period=min_support_period,
                )
                category_results.append(result)
                if not dry_run:
                    _persist_entity_result(
                        session,
                        run_id=run.id,
                        clustering_run_id=None,
                        trend_type=TREND_TYPE_CATEGORY_GROWTH,
                        result=result,
                        cohorts=cohorts,
                        evidence_limit=evidence_limit,
                        now=now,
                    )

            if not dry_run:
                run.status = "SUCCEEDED"
                run.completed_at = datetime.now(timezone.utc)
                session.add(run)
                session.commit()

        except Exception as exc:
            if not dry_run and run is not None:
                session.rollback()
                run.status = "FAILED"
                run.error_message = _safe_error_message(exc)
                run.completed_at = datetime.now(timezone.utc)
                session.add(run)
                session.commit()
            raise

        return {
            # None in dry-run mode even though `run` holds an in-memory
            # UUID -- that id was never added/committed to the session, so
            # reporting it would look like a real persisted run when
            # nothing was actually saved.
            "run_id": None if dry_run else (str(run.id) if run is not None else None),
            "status": "SUCCEEDED" if dry_run else run.status,
            "dry_run": dry_run,
            "freshness_status": freshness_status,
            "trend_mode_resolution": mode_resolution,
            "cohorts": cohorts,
            "cluster_results": cluster_results,
            "category_results": category_results,
        }
    finally:
        session.close()
