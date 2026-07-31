"""Validates research_platform.trends.pipeline end to end against the real
database: successful persistence, failed-run status + safe error-message
redaction + rollback of partial child rows, dry-run writing nothing,
deterministic repeated runs, historical-mode-only labeling (no current-
trend claims, no citation-momentum rows), and that every pre-existing
source-table row count is unchanged before and after.

Requires the local dev database running with the trend-tables migration
applied (test_trend_migration.py) and the real, already-completed
clustering run intact. Every TrendAnalysisRun this file creates is deleted
in a `finally` block (cascades to its snapshots/scores/evidence at the
database level, per test_trend_models.py's cascade test). Run directly:

    python3 tests/test_trend_pipeline.py
"""
from unittest.mock import patch

from sqlalchemy import delete, func, select

from research_platform.db.models import (
    ClusterLabel,
    ClusteringRun,
    Paper,
    PaperClusterAssignment,
    PaperEmbedding,
    PaperMetricSnapshot,
    TrendAnalysisRun,
    TrendEntitySnapshot,
    TrendEvidencePaper,
    TrendScore,
)
from research_platform.db.session import SessionLocal
from research_platform.trends import classifications, pipeline

SOURCE_TABLES = [Paper, PaperEmbedding, ClusteringRun, ClusterLabel, PaperClusterAssignment, PaperMetricSnapshot]


def _source_table_counts(session) -> dict:
    return {model.__tablename__: session.execute(select(func.count()).select_from(model)).scalar_one() for model in SOURCE_TABLES}


def _delete_run(run_id) -> None:
    session = SessionLocal()
    try:
        session.execute(delete(TrendAnalysisRun).where(TrendAnalysisRun.id == run_id))
        session.commit()
    finally:
        session.close()


def test_successful_pipeline_persistence():
    session = SessionLocal()
    before = _source_table_counts(session)
    session.close()

    summary = pipeline.run_historical_cohort_pipeline(dry_run=False, evidence_limit=5)
    run_id = summary["run_id"]
    try:
        assert summary["status"] == "SUCCEEDED"
        assert run_id is not None

        session = SessionLocal()
        try:
            run = session.get(TrendAnalysisRun, run_id)
            assert run.status == "SUCCEEDED"
            assert run.requested_trend_mode == "historical"
            assert run.effective_trend_mode == "historical"
            assert run.window_granularity == "snapshot"
            assert run.completed_at is not None

            snapshot_count = session.execute(
                select(func.count()).select_from(TrendEntitySnapshot).where(TrendEntitySnapshot.trend_run_id == run.id)
            ).scalar_one()
            score_count = session.execute(
                select(func.count()).select_from(TrendScore).where(TrendScore.trend_run_id == run.id)
            ).scalar_one()
            assert snapshot_count == len(summary["cluster_results"]) + len(summary["category_results"])
            assert score_count == snapshot_count
            assert snapshot_count == 10 + 30, f"expected 10 clusters + 30 categories = 40 entities, got {snapshot_count}"

            cluster_5 = session.execute(
                select(TrendScore).where(
                    TrendScore.trend_run_id == run.id, TrendScore.entity_type == "cluster", TrendScore.entity_id == "5"
                )
            ).scalar_one()
            cluster_0 = session.execute(
                select(TrendScore).where(
                    TrendScore.trend_run_id == run.id, TrendScore.entity_type == "cluster", TrendScore.entity_id == "0"
                )
            ).scalar_one()
            cluster_4 = session.execute(
                select(TrendScore).where(
                    TrendScore.trend_run_id == run.id, TrendScore.entity_type == "cluster", TrendScore.entity_id == "4"
                )
            ).scalar_one()
            assert cluster_5.trend_classification == "Stable"
            assert cluster_0.trend_classification == "Emerging"
            assert cluster_4.trend_classification == "Cooling"

            evidence_count = session.execute(
                select(func.count())
                .select_from(TrendEvidencePaper)
                .join(TrendScore, TrendScore.id == TrendEvidencePaper.trend_score_id)
                .where(TrendScore.trend_run_id == run.id)
            ).scalar_one()
            assert evidence_count > 0, "at least some entities should have evidence papers"

            print(
                f"PASS: a real persisted run creates {snapshot_count} snapshots, {score_count} scores, "
                f"{evidence_count} evidence rows, and Cluster 5/0/4 classify exactly as documented "
                "(Stable / Emerging / Cooling)"
            )
        finally:
            session.close()

        session = SessionLocal()
        after = _source_table_counts(session)
        session.close()
        assert before == after, f"source-table counts changed: before={before} after={after}"
        print("PASS: every pre-existing source-table row count is unchanged after a real persisted run")
    finally:
        _delete_run(run_id)


def test_dry_run_creates_no_rows():
    session = SessionLocal()
    before_runs = session.execute(select(func.count()).select_from(TrendAnalysisRun)).scalar_one()
    before_snapshots = session.execute(select(func.count()).select_from(TrendEntitySnapshot)).scalar_one()
    before_scores = session.execute(select(func.count()).select_from(TrendScore)).scalar_one()
    before_evidence = session.execute(select(func.count()).select_from(TrendEvidencePaper)).scalar_one()
    session.close()

    summary = pipeline.run_historical_cohort_pipeline(dry_run=True)
    assert summary["run_id"] is None
    assert summary["status"] == "SUCCEEDED"
    assert len(summary["cluster_results"]) == 10
    assert len(summary["category_results"]) == 30

    session = SessionLocal()
    after_runs = session.execute(select(func.count()).select_from(TrendAnalysisRun)).scalar_one()
    after_snapshots = session.execute(select(func.count()).select_from(TrendEntitySnapshot)).scalar_one()
    after_scores = session.execute(select(func.count()).select_from(TrendScore)).scalar_one()
    after_evidence = session.execute(select(func.count()).select_from(TrendEvidencePaper)).scalar_one()
    session.close()

    assert before_runs == after_runs
    assert before_snapshots == after_snapshots
    assert before_scores == after_scores
    assert before_evidence == after_evidence
    print("PASS: dry_run=True computes a full summary but persists zero rows to any of the four trend tables")


def test_repeated_runs_produce_equivalent_calculated_values():
    summary_a = pipeline.run_historical_cohort_pipeline(dry_run=False, calculation_version="determinism-test-a")
    try:
        summary_b = pipeline.run_historical_cohort_pipeline(dry_run=False, calculation_version="determinism-test-b")
        try:
            assert summary_a["run_id"] != summary_b["run_id"]

            def _as_map(results):
                return {(r["entity"].entity_type, r["entity"].entity_id): r for r in results}

            map_a = _as_map(summary_a["cluster_results"] + summary_a["category_results"])
            map_b = _as_map(summary_b["cluster_results"] + summary_b["category_results"])
            assert map_a.keys() == map_b.keys()

            mismatches = []
            for key, result_a in map_a.items():
                result_b = map_b[key]
                for field in ("trend_score", "growth_rate", "trend_classification", "data_quality_level", "component_breakdown"):
                    if result_a[field] != result_b[field]:
                        mismatches.append((key, field, result_a[field], result_b[field]))
            assert not mismatches, f"non-deterministic fields found: {mismatches}"
            print(
                f"PASS: two independent runs over identical corpus state and parameters produced byte-identical "
                f"calculated values across all {len(map_a)} entities (only run_id/timestamps differ)"
            )
        finally:
            _delete_run(summary_b["run_id"])
    finally:
        _delete_run(summary_a["run_id"])


def test_no_current_trend_claims_and_no_citation_momentum_rows():
    summary = pipeline.run_historical_cohort_pipeline(dry_run=False)
    run_id = summary["run_id"]
    try:
        session = SessionLocal()
        try:
            run = session.get(TrendAnalysisRun, run_id)
            assert run.requested_trend_mode == "historical"
            assert run.effective_trend_mode == "historical"
            assert "current" not in (run.requested_trend_mode, run.effective_trend_mode)

            trend_types = session.execute(
                select(func.distinct(TrendScore.trend_type)).where(TrendScore.trend_run_id == run_id)
            ).scalars().all()
            assert set(trend_types) <= {"cluster_growth", "category_growth"}
            assert "citation_momentum" not in trend_types
            assert "paper_momentum" not in trend_types

            classifications_present = session.execute(
                select(func.distinct(TrendScore.trend_classification)).where(TrendScore.trend_run_id == run_id)
            ).scalars().all()
            assert "Trending Now" not in classifications_present

            label = classifications.resolve_trend_mode_label(summary["trend_mode_resolution"].resolved_state)
            assert label == "Historical Cohort Comparison"
            print(
                "PASS: the persisted run is requested/effective='historical' only, inserts zero citation-momentum/"
                'paper-momentum rows, never classifies anything "Trending Now", and resolves to the '
                '"Historical Cohort Comparison" label'
            )
        finally:
            session.close()
    finally:
        _delete_run(run_id)


def test_failed_run_status_redacted_error_and_rollback():
    fake_error = RuntimeError(
        "connection failed: postgresql://research_user:supersecret@localhost:5433/research_platform"
    )
    with patch.object(pipeline.queries, "get_all_primary_category_codes", side_effect=fake_error):
        try:
            pipeline.run_historical_cohort_pipeline(dry_run=False)
            raised = False
        except RuntimeError:
            raised = True
    assert raised, "the pipeline must re-raise the underlying exception after marking the run FAILED"

    session = SessionLocal()
    try:
        failed_run = session.execute(
            select(TrendAnalysisRun).where(TrendAnalysisRun.status == "FAILED").order_by(TrendAnalysisRun.created_at.desc()).limit(1)
        ).scalar_one()
        assert failed_run.status == "FAILED"
        assert failed_run.completed_at is not None
        assert failed_run.error_message is not None
        assert "supersecret" not in failed_run.error_message
        assert "research_user:supersecret" not in failed_run.error_message
        assert "[redacted-connection-string]" in failed_run.error_message

        orphan_snapshots = session.execute(
            select(func.count()).select_from(TrendEntitySnapshot).where(TrendEntitySnapshot.trend_run_id == failed_run.id)
        ).scalar_one()
        orphan_scores = session.execute(
            select(func.count()).select_from(TrendScore).where(TrendScore.trend_run_id == failed_run.id)
        ).scalar_one()
        assert orphan_snapshots == 0, "cluster snapshots added-but-uncommitted before the failure must be rolled back"
        assert orphan_scores == 0
        print(
            "PASS: a mid-run failure (during category processing, after cluster processing had already staged "
            "uncommitted rows) marks the run FAILED, redacts the connection string from error_message, and "
            "rolls back every partial child row -- including the already-processed clusters, not just categories"
        )
        failed_run_id = failed_run.id
    finally:
        session.close()
    _delete_run(failed_run_id)


if __name__ == "__main__":
    test_successful_pipeline_persistence()
    test_dry_run_creates_no_rows()
    test_repeated_runs_produce_equivalent_calculated_values()
    test_no_current_trend_claims_and_no_citation_momentum_rows()
    test_failed_run_status_redacted_error_and_rollback()
    print("\nALL TESTS PASSED")
