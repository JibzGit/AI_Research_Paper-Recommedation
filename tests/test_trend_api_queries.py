"""Validates research_platform.trends.api_queries against the real,
persisted official trend run: latest-successful-run selection (including
that RUNNING/FAILED runs are excluded from the default), explicit run_id
selection/404, classification/data-quality/min-score filtering,
deterministic ordering with tie-breakers, pagination, evidence-paper
roles, unsupported-entity-type/missing-entity errors, and the overview
summary's content (including the mandatory historical-cohort wording).

Requires the local dev database running with the official trend run
persisted (trend_analysis_runs, 1 SUCCEEDED row; see
scripts/run_trend_analysis.py). Every synthetic row this file creates is
cleaned up in a `finally` block. Never writes to any source table. Run
directly:

    python3 tests/test_trend_api_queries.py
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import delete

from research_platform.db.models import TrendAnalysisRun
from research_platform.db.session import SessionLocal
from research_platform.trends import api_queries, classifications


def _synthetic_run(status: str, created_offset_seconds: int) -> TrendAnalysisRun:
    now = datetime.now(timezone.utc)
    return TrendAnalysisRun(
        id=uuid.uuid4(), calculation_version="test-version", requested_trend_mode="historical",
        effective_trend_mode="historical", freshness_status="PARTIALLY_CURRENT",
        corpus_latest_publication_date=now, recent_period_start=now - timedelta(days=1), recent_period_end=now,
        comparison_period_start=now - timedelta(days=365), comparison_period_end=now - timedelta(days=364),
        window_granularity="snapshot", parameters={}, total_canonical_papers=169,
        status=status, created_at=now + timedelta(seconds=created_offset_seconds),
        completed_at=now + timedelta(seconds=created_offset_seconds) if status != "RUNNING" else None,
    )


def test_latest_successful_run_excludes_running_and_failed():
    session = SessionLocal()
    real_latest = api_queries.get_latest_successful_trend_run(session)
    assert real_latest is not None, "expected the real persisted official run to exist"

    later_running = _synthetic_run("RUNNING", created_offset_seconds=1000)
    later_failed = _synthetic_run("FAILED", created_offset_seconds=2000)
    session.add_all([later_running, later_failed])
    session.commit()
    try:
        latest = api_queries.get_latest_successful_trend_run(session)
        assert latest.id == real_latest.id, "a later RUNNING/FAILED run must never be selected as 'latest successful'"
        print("PASS: more recent RUNNING and FAILED runs are excluded from default selection -- the real SUCCEEDED run remains latest")

        later_succeeded = _synthetic_run("SUCCEEDED", created_offset_seconds=3000)
        session.add(later_succeeded)
        session.commit()
        try:
            latest = api_queries.get_latest_successful_trend_run(session)
            assert latest.id == later_succeeded.id
            print("PASS: a more recent SUCCEEDED run is correctly selected as the new 'latest successful'")
        finally:
            session.execute(delete(TrendAnalysisRun).where(TrendAnalysisRun.id == later_succeeded.id))
            session.commit()
    finally:
        session.execute(delete(TrendAnalysisRun).where(TrendAnalysisRun.id.in_([later_running.id, later_failed.id])))
        session.commit()
        session.close()


def test_resolve_trend_run_explicit_run_id():
    session = SessionLocal()
    running = _synthetic_run("RUNNING", created_offset_seconds=0)
    session.add(running)
    session.commit()
    try:
        resolved = api_queries.resolve_trend_run(session, str(running.id))
        assert resolved.id == running.id, "an explicit run_id must be honored even for a RUNNING run"
        print("PASS: resolve_trend_run(explicit run_id) returns that exact run regardless of status")
    finally:
        session.execute(delete(TrendAnalysisRun).where(TrendAnalysisRun.id == running.id))
        session.commit()
        session.close()


def test_resolve_trend_run_unknown_run_id_raises_not_found():
    session = SessionLocal()
    try:
        try:
            api_queries.resolve_trend_run(session, str(uuid.uuid4()))
            raised = False
        except api_queries.TrendRunNotFoundError:
            raised = True
        assert raised
        print("PASS: an unknown run_id raises TrendRunNotFoundError")
    finally:
        session.close()


def test_resolve_trend_run_raises_results_unavailable_when_no_successful_run():
    session = SessionLocal()
    try:
        with patch.object(api_queries, "get_latest_successful_trend_run", return_value=None):
            try:
                api_queries.resolve_trend_run(session, None)
                raised = False
            except api_queries.TrendResultsUnavailableError:
                raised = True
        assert raised
        print("PASS: no run_id + no SUCCEEDED run anywhere raises TrendResultsUnavailableError (not a 404 case)")
    finally:
        session.close()


def test_classification_data_quality_min_score_filtering():
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, None)

        total, cooling = api_queries.get_entity_results(session, run.id, "cluster", classification="Cooling", limit=100)
        assert total == 8
        assert all(r["score"]["trend_classification"] == "Cooling" for r in cooling)

        total, low_quality = api_queries.get_entity_results(session, run.id, "cluster", data_quality="LOW", limit=100)
        assert total == 10, "every cluster in this run has LOW data quality (single-day recent-cohort concentration)"

        total, high_score = api_queries.get_entity_results(session, run.id, "cluster", min_score=60, limit=100)
        assert total == 1
        assert high_score[0]["entity_id"] == "5"
        print("PASS: classification, data_quality, and min_score filters each narrow results correctly against real data")
    finally:
        session.close()


def test_deterministic_ordering_with_tie_breakers():
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, None)

        _total, first = api_queries.get_entity_results(session, run.id, "cluster", limit=100, sort_by="recent_paper_count", sort_order="asc")
        _total, second = api_queries.get_entity_results(session, run.id, "cluster", limit=100, sort_by="recent_paper_count", sort_order="asc")
        assert [r["entity_id"] for r in first] == [r["entity_id"] for r in second], "repeated identical calls must return identical order"

        zero_recent = [r for r in first if r["metrics"]["recent_paper_count"] == 0]
        assert len(zero_recent) >= 2, "expected multiple clusters tied at recent_paper_count == 0 for this real run"
        names = [r["entity_name"] for r in zero_recent]
        assert names == sorted(names), "entities tied on the primary sort field must be broken by entity_name ascending"
        print("PASS: ordering is deterministic across repeated calls and ties are broken by entity_name/entity_id")
    finally:
        session.close()


def test_pagination():
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, None)
        total, page1 = api_queries.get_entity_results(session, run.id, "category", limit=10, offset=0)
        _total2, page2 = api_queries.get_entity_results(session, run.id, "category", limit=10, offset=10)
        assert total == 30
        assert len(page1) == 10
        assert len(page2) == 10
        assert {r["entity_id"] for r in page1}.isdisjoint({r["entity_id"] for r in page2})
        print("PASS: pagination (limit/offset) returns disjoint, correctly-sized pages with a consistent total")
    finally:
        session.close()


def test_evidence_paper_roles():
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, None)
        _result, score_id = api_queries.get_entity_result(session, run.id, "cluster", "5")
        recent, comparison = api_queries.get_evidence_papers(session, score_id)
        assert len(recent) > 0 and len(comparison) > 0, "Cluster 5 (11 vs 11) should have evidence on both sides"
        assert all(item["role"] == "recent_period" for item in recent)
        assert all(item["role"] == "comparison_period" for item in comparison)
        dates = [item["publication_date"] for item in recent]
        assert dates == sorted(dates), "evidence must be ordered by publication_date ascending"
        print("PASS: evidence papers are correctly split by role and deterministically ordered")
    finally:
        session.close()


def test_unsupported_entity_type_raises_value_error():
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, None)
        for fn, args in (
            (api_queries.get_entity_results, (session, run.id, "paper")),
            (api_queries.get_entity_result, (session, run.id, "paper", "x")),
        ):
            try:
                fn(*args)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"{fn.__name__} should reject an unsupported entity_type"
        print("PASS: an unsupported entity_type raises ValueError at the query layer")
    finally:
        session.close()


def test_missing_entity_raises_not_found():
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, None)
        try:
            api_queries.get_entity_result(session, run.id, "cluster", "999")
            raised = False
        except api_queries.TrendEntityNotFoundError:
            raised = True
        assert raised
        print("PASS: an entity_id with no persisted score raises TrendEntityNotFoundError")
    finally:
        session.close()


def test_overview_content_and_historical_wording():
    session = SessionLocal()
    try:
        run = api_queries.resolve_trend_run(session, None)
        overview = api_queries.get_overview(session, run)

        assert overview["cluster_summary"]["total_entities"] == 10
        assert overview["category_summary"]["total_entities"] == 30
        assert sum(overview["cluster_summary"]["classification_counts"].values()) == 10
        assert overview["trend_context"]["effective_trend_mode"] == "historical"
        assert overview["trend_context"]["trend_mode_label"] == classifications.HISTORICAL_COHORT_COMPARISON_LABEL

        message = overview["message"]
        assert "Historical Cohort Comparison" in message
        assert "Comparison cohort" in message
        assert "Recent cohort" in message
        for banned in ("Trending Now", "Latest AI Trends", "Current Momentum", "Year-over-Year", "continuous historical trend"):
            assert banned.lower() not in message.lower()
        print("PASS: overview summary counts are internally consistent and the message uses only approved historical-cohort wording")
    finally:
        session.close()


if __name__ == "__main__":
    test_latest_successful_run_excludes_running_and_failed()
    test_resolve_trend_run_explicit_run_id()
    test_resolve_trend_run_unknown_run_id_raises_not_found()
    test_resolve_trend_run_raises_results_unavailable_when_no_successful_run()
    test_classification_data_quality_min_score_filtering()
    test_deterministic_ordering_with_tie_breakers()
    test_pagination()
    test_evidence_paper_roles()
    test_unsupported_entity_type_raises_value_error()
    test_missing_entity_raises_not_found()
    test_overview_content_and_historical_wording()
    print("\nALL TESTS PASSED")
