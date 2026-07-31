"""Validates the four trend-table SQLAlchemy models at the database level:
CHECK constraints (trend_score range, evidence role), FK constraints
(including that a nonexistent parent is rejected), uniqueness constraints,
and ON DELETE CASCADE behavior from trend_analysis_runs down through
trend_entity_snapshots/trend_scores/trend_evidence_papers.

Requires the local dev database to be running with the trend-tables
migration already applied (see test_trend_migration.py, which must run
first). Every synthetic row this file creates is cleaned up in a `finally`
block, following the same pattern as test_cluster_labeling.py. Never
modifies any existing papers/clustering_runs/cluster_labels row -- only
reads one real paper_id for the evidence-FK tests. Run directly:

    python3 tests/test_trend_models.py
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from research_platform.db.models import (
    Paper,
    TrendAnalysisRun,
    TrendEntitySnapshot,
    TrendEvidencePaper,
    TrendScore,
)
from research_platform.db.session import SessionLocal

NOW = datetime.now(timezone.utc)


def _make_run(session) -> TrendAnalysisRun:
    run = TrendAnalysisRun(
        id=uuid.uuid4(),
        calculation_version="test-version",
        requested_trend_mode="historical",
        effective_trend_mode="historical",
        freshness_status="PARTIALLY_CURRENT",
        corpus_latest_publication_date=NOW,
        recent_period_start=NOW - timedelta(days=1),
        recent_period_end=NOW,
        comparison_period_start=NOW - timedelta(days=365),
        comparison_period_end=NOW - timedelta(days=364),
        window_granularity="snapshot",
        parameters={"test": True},
        total_canonical_papers=169,
        status="RUNNING",
        created_at=NOW,
    )
    session.add(run)
    session.commit()
    return run


def _cleanup_run(session, run_id) -> None:
    session.rollback()  # in case a prior assertion left the transaction aborted
    session.execute(delete(TrendAnalysisRun).where(TrendAnalysisRun.id == run_id))
    session.commit()


def _real_paper_id(session):
    return session.execute(select(Paper.id).limit(1)).scalar_one()


def _expect_integrity_error(session, build_and_add) -> None:
    try:
        build_and_add()
        session.commit()
        raised = False
    except IntegrityError:
        raised = True
    session.rollback()
    assert raised, "expected an IntegrityError, but the insert/commit succeeded"


def test_trend_score_range_check_constraint():
    session = SessionLocal()
    run = _make_run(session)
    try:
        _expect_integrity_error(
            session,
            lambda: session.add(
                TrendScore(
                    trend_run_id=run.id, entity_type="cluster", entity_id="0", trend_type="cluster_growth",
                    trend_score=101, trend_classification="Emerging", data_quality_level="LOW",
                    component_breakdown={}, created_at=NOW,
                )
            ),
        )
        print("PASS: trend_score=101 rejected by ck_trend_scores_score_range")

        _expect_integrity_error(
            session,
            lambda: session.add(
                TrendScore(
                    trend_run_id=run.id, entity_type="cluster", entity_id="1", trend_type="cluster_growth",
                    trend_score=-1, trend_classification="Cooling", data_quality_level="LOW",
                    component_breakdown={}, created_at=NOW,
                )
            ),
        )
        print("PASS: trend_score=-1 rejected by ck_trend_scores_score_range")

        session.add(
            TrendScore(
                trend_run_id=run.id, entity_type="cluster", entity_id="2", trend_type="cluster_growth",
                trend_score=0, trend_classification="Insufficient Data", data_quality_level="INSUFFICIENT",
                component_breakdown={}, created_at=NOW,
            )
        )
        session.add(
            TrendScore(
                trend_run_id=run.id, entity_type="cluster", entity_id="3", trend_type="cluster_growth",
                trend_score=100, trend_classification="Accelerating", data_quality_level="HIGH",
                component_breakdown={}, created_at=NOW,
            )
        )
        session.commit()
        print("PASS: trend_score=0 and trend_score=100 (the valid boundary values) are accepted")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_evidence_role_check_constraint():
    session = SessionLocal()
    run = _make_run(session)
    try:
        paper_id = _real_paper_id(session)
        score = TrendScore(
            trend_run_id=run.id, entity_type="cluster", entity_id="0", trend_type="cluster_growth",
            trend_score=50, trend_classification="Stable", data_quality_level="LOW",
            component_breakdown={}, created_at=NOW,
        )
        session.add(score)
        session.commit()

        _expect_integrity_error(
            session,
            lambda: session.add(
                TrendEvidencePaper(trend_score_id=score.id, paper_id=paper_id, role="not_a_real_role", created_at=NOW)
            ),
        )
        print("PASS: role='not_a_real_role' rejected by ck_trend_evidence_papers_role")

        session.add(TrendEvidencePaper(trend_score_id=score.id, paper_id=paper_id, role="recent_period", created_at=NOW))
        session.commit()
        print("PASS: role='recent_period' (an allowed value) is accepted")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_foreign_key_rejects_nonexistent_parent():
    session = SessionLocal()
    run = _make_run(session)
    try:
        _expect_integrity_error(
            session,
            lambda: session.add(
                TrendEntitySnapshot(
                    trend_run_id=uuid.uuid4(),  # no such run
                    entity_type="cluster", entity_id="0", entity_name="Nonexistent",
                    recent_paper_count=1, previous_paper_count=1, absolute_growth=0,
                    is_new_activity=False, total_papers=2, created_at=NOW,
                )
            ),
        )
        print("PASS: trend_entity_snapshots.trend_run_id referencing a nonexistent run is rejected")

        _expect_integrity_error(
            session,
            lambda: session.add(
                TrendEvidencePaper(trend_score_id=uuid.uuid4(), paper_id=_real_paper_id(session), role="recent_period", created_at=NOW)
            ),
        )
        print("PASS: trend_evidence_papers.trend_score_id referencing a nonexistent score is rejected")

        score = TrendScore(
            trend_run_id=run.id, entity_type="cluster", entity_id="0", trend_type="cluster_growth",
            trend_score=50, trend_classification="Stable", data_quality_level="LOW", component_breakdown={}, created_at=NOW,
        )
        session.add(score)
        session.commit()
        _expect_integrity_error(
            session,
            lambda: session.add(
                TrendEvidencePaper(trend_score_id=score.id, paper_id=uuid.uuid4(), role="recent_period", created_at=NOW)
            ),
        )
        print("PASS: trend_evidence_papers.paper_id referencing a nonexistent paper is rejected")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_uniqueness_constraints():
    session = SessionLocal()
    run = _make_run(session)
    try:
        session.add(
            TrendEntitySnapshot(
                trend_run_id=run.id, entity_type="cluster", entity_id="5", entity_name="Model Distillation",
                recent_paper_count=11, previous_paper_count=11, absolute_growth=0, growth_rate=0.0,
                is_new_activity=False, total_papers=22, created_at=NOW,
            )
        )
        session.commit()
        _expect_integrity_error(
            session,
            lambda: session.add(
                TrendEntitySnapshot(
                    trend_run_id=run.id, entity_type="cluster", entity_id="5", entity_name="Duplicate",
                    recent_paper_count=1, previous_paper_count=1, absolute_growth=0,
                    is_new_activity=False, total_papers=2, created_at=NOW,
                )
            ),
        )
        print("PASS: duplicate (trend_run_id, entity_type, entity_id) rejected by uq_trend_entity_snapshots_run_entity")

        session.add(
            TrendScore(
                trend_run_id=run.id, entity_type="cluster", entity_id="5", trend_type="cluster_growth",
                trend_score=68, trend_classification="Stable", data_quality_level="LOW", component_breakdown={}, created_at=NOW,
            )
        )
        session.commit()
        _expect_integrity_error(
            session,
            lambda: session.add(
                TrendScore(
                    trend_run_id=run.id, entity_type="cluster", entity_id="5", trend_type="cluster_growth",
                    trend_score=1, trend_classification="Insufficient Data", data_quality_level="INSUFFICIENT",
                    component_breakdown={}, created_at=NOW,
                )
            ),
        )
        print("PASS: duplicate (trend_run_id, entity_type, entity_id, trend_type) rejected by uq_trend_scores_run_entity_type")

        # A different trend_type for the SAME entity must be allowed --
        # uniqueness is scoped per trend_type, not per entity alone.
        session.add(
            TrendScore(
                trend_run_id=run.id, entity_type="cluster", entity_id="5", trend_type="publication_trend",
                trend_score=68, trend_classification="Stable", data_quality_level="LOW", component_breakdown={}, created_at=NOW,
            )
        )
        session.commit()
        print("PASS: the same entity with a different trend_type is a distinct, allowed row")

        paper_id = _real_paper_id(session)
        score_id = session.execute(
            select(TrendScore.id).where(TrendScore.trend_run_id == run.id, TrendScore.trend_type == "cluster_growth")
        ).scalar_one()
        session.add(TrendEvidencePaper(trend_score_id=score_id, paper_id=paper_id, role="recent_period", created_at=NOW))
        session.commit()
        _expect_integrity_error(
            session,
            lambda: session.add(
                TrendEvidencePaper(trend_score_id=score_id, paper_id=paper_id, role="recent_period", created_at=NOW)
            ),
        )
        print("PASS: duplicate (trend_score_id, paper_id, role) rejected by uq_trend_evidence_papers_score_paper_role")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_cascade_delete_from_run_through_evidence():
    session = SessionLocal()
    run = _make_run(session)
    try:
        session.add(
            TrendEntitySnapshot(
                trend_run_id=run.id, entity_type="cluster", entity_id="0", entity_name="Medical Imaging",
                recent_paper_count=6, previous_paper_count=0, absolute_growth=6, is_new_activity=True,
                total_papers=6, created_at=NOW,
            )
        )
        score = TrendScore(
            trend_run_id=run.id, entity_type="cluster", entity_id="0", trend_type="cluster_growth",
            trend_score=34, trend_classification="Emerging", data_quality_level="LOW", component_breakdown={}, created_at=NOW,
        )
        session.add(score)
        session.commit()

        paper_id = _real_paper_id(session)
        session.add(TrendEvidencePaper(trend_score_id=score.id, paper_id=paper_id, role="recent_period", created_at=NOW))
        session.commit()

        snapshot_count_before = session.execute(
            select(TrendEntitySnapshot).where(TrendEntitySnapshot.trend_run_id == run.id)
        ).scalars().all()
        score_count_before = session.execute(select(TrendScore).where(TrendScore.trend_run_id == run.id)).scalars().all()
        evidence_count_before = session.execute(
            select(TrendEvidencePaper).where(TrendEvidencePaper.trend_score_id == score.id)
        ).scalars().all()
        assert len(snapshot_count_before) == 1 and len(score_count_before) == 1 and len(evidence_count_before) == 1

        session.execute(delete(TrendAnalysisRun).where(TrendAnalysisRun.id == run.id))
        session.commit()

        snapshot_count_after = session.execute(
            select(TrendEntitySnapshot).where(TrendEntitySnapshot.trend_run_id == run.id)
        ).scalars().all()
        score_count_after = session.execute(select(TrendScore).where(TrendScore.trend_run_id == run.id)).scalars().all()
        evidence_count_after = session.execute(
            select(TrendEvidencePaper).where(TrendEvidencePaper.trend_score_id == score.id)
        ).scalars().all()
        assert len(snapshot_count_after) == 0
        assert len(score_count_after) == 0
        assert len(evidence_count_after) == 0
        print("PASS: deleting a TrendAnalysisRun cascades through snapshots, scores, and evidence at the database level")
    finally:
        # the run itself is already gone via cascade in the success path;
        # this is a no-op then, and a real cleanup only if an assertion
        # failed before the delete happened.
        session.rollback()
        session.execute(delete(TrendAnalysisRun).where(TrendAnalysisRun.id == run.id))
        session.commit()
        session.close()


if __name__ == "__main__":
    test_trend_score_range_check_constraint()
    test_evidence_role_check_constraint()
    test_foreign_key_rejects_nonexistent_parent()
    test_uniqueness_constraints()
    test_cascade_delete_from_run_through_evidence()
    print("\nALL TESTS PASSED")
