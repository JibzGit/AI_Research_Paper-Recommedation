"""Validates research_platform.trends.queries against the real database:
latest-successful-clustering-run selection, approved-label filtering,
noise-paper exclusion, publication-date-convention reuse (including the
first_observed_at fallback), cluster/category cohort aggregation against
the real corpus's known numbers, and evidence selection (limit
enforcement + deterministic ordering).

Requires the local dev database running with the trend-tables migration
applied (test_trend_migration.py) and the real, already-completed
clustering run (084a1215-53be-4644-86e5-6f8a84b5422f, 169 papers / 10
clusters / 21 noise) intact. Every synthetic row is cleaned up in a
`finally` block; the real corpus data is only ever read, never written.
Run directly:

    python3 tests/test_trend_queries.py
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from research_platform.db.models import Category, ClusterLabel, ClusteringRun, Paper
from research_platform.db.session import SessionLocal
from research_platform.trends import queries

REAL_RUN_ID = uuid.UUID("084a1215-53be-4644-86e5-6f8a84b5422f")
COHORT_2016_START = datetime(2016, 1, 1, tzinfo=timezone.utc)
COHORT_2016_END = datetime(2016, 1, 12, tzinfo=timezone.utc)
COHORT_2026_START = datetime(2026, 7, 27, tzinfo=timezone.utc)
COHORT_2026_END = datetime(2026, 7, 28, tzinfo=timezone.utc)
FAR_PAST = datetime(1, 1, 1, tzinfo=timezone.utc)
FAR_FUTURE = datetime(9999, 1, 1, tzinfo=timezone.utc)


def test_latest_successful_clustering_run_selection():
    session = SessionLocal()
    later_failed = ClusteringRun(
        id=uuid.uuid4(), embedding_model="test", embedding_model_version="test",
        algorithm_parameters={}, random_seed=1, paper_count=0, cluster_count=0, noise_count=0,
        status="FAILED", created_at=datetime.now(timezone.utc),
    )
    session.add(later_failed)
    session.commit()
    try:
        latest = queries.get_latest_successful_clustering_run(session)
        assert latest is not None
        assert latest.id == REAL_RUN_ID, "a later FAILED run must not be selected over the real SUCCEEDED run"
        print("PASS: a more recent FAILED run is not selected -- the real SUCCEEDED run remains 'latest'")

        even_later_succeeded = ClusteringRun(
            id=uuid.uuid4(), embedding_model="test", embedding_model_version="test",
            algorithm_parameters={}, random_seed=1, paper_count=0, cluster_count=0, noise_count=0,
            status="SUCCEEDED", created_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        )
        session.add(even_later_succeeded)
        session.commit()
        try:
            latest = queries.get_latest_successful_clustering_run(session)
            assert latest.id == even_later_succeeded.id
            print("PASS: a more recent SUCCEEDED run is correctly selected as the new 'latest'")
        finally:
            session.execute(delete(ClusteringRun).where(ClusteringRun.id == even_later_succeeded.id))
            session.commit()
    finally:
        session.execute(delete(ClusteringRun).where(ClusteringRun.id == later_failed.id))
        session.commit()
        session.close()


def test_approved_label_filtering():
    session = SessionLocal()
    unapproved = ClusterLabel(
        id=uuid.uuid4(), clustering_run_id=REAL_RUN_ID, cluster_id=999,
        cluster_name="Unapproved Test Cluster", short_description=None, keywords=None, confidence=None,
        evidence=None, provider="test", model="test", model_version="test", prompt_version="test",
        input_hash="test-hash", generation_status="SUCCEEDED", review_status="PENDING_REVIEW",
    )
    session.add(unapproved)
    session.commit()
    try:
        labels = queries.get_approved_cluster_labels(session, REAL_RUN_ID)
        label_cluster_ids = {label.cluster_id for label in labels}
        assert 999 not in label_cluster_ids, "a PENDING_REVIEW label must never be treated as approved"
        assert len(labels) == 10, f"expected exactly the 10 real APPROVED labels, got {len(labels)}"
        assert label_cluster_ids == set(range(10))
        print("PASS: get_approved_cluster_labels excludes a PENDING_REVIEW label and returns exactly the 10 real APPROVED ones")
    finally:
        session.execute(delete(ClusterLabel).where(ClusterLabel.id == unapproved.id))
        session.commit()
        session.close()


def test_noise_papers_excluded_from_cluster_counts():
    session = SessionLocal()
    try:
        counts = queries.count_cluster_papers_in_window(session, REAL_RUN_ID, FAR_PAST, FAR_FUTURE)
        total_non_noise = sum(counts.values())
        assert total_non_noise == 148, (
            f"expected exactly the 148 known non-noise assignments across all time, got {total_non_noise}"
        )
        print("PASS: count_cluster_papers_in_window across all time sums to exactly 148 -- the 21 noise papers never contribute")
    finally:
        session.close()


def test_publication_date_convention_reuse_including_fallback():
    """A synthetic paper with NO PaperVersion row at all must fall back to
    first_observed_at -- the same convention embeddings.search.
    publication_date_subquery() already defines, reused here rather than
    redefined."""
    session = SessionLocal()
    category_id = session.execute(select(Category.id).limit(1)).scalar_one()
    fallback_date = datetime(2099, 6, 15, tzinfo=timezone.utc)
    synthetic = Paper(
        id=uuid.uuid4(), arxiv_id=None, doi=None, normalized_title="synthetic fallback test paper",
        title="Synthetic Fallback Test Paper", abstract="Test abstract.", primary_category_id=category_id,
        first_observed_source="test", first_observed_at=fallback_date, current_version_number=0,
        is_canonical=True,
    )
    session.add(synthetic)
    session.commit()
    try:
        count_in_2099 = queries.count_papers_in_window(
            session, datetime(2099, 1, 1, tzinfo=timezone.utc), datetime(2100, 1, 1, tzinfo=timezone.utc)
        )
        assert count_in_2099 == 1, "a paper with no PaperVersion row must still be found via the first_observed_at fallback"

        date_range = queries.get_publication_date_range(session)
        assert date_range.latest == fallback_date, "the fallback-dated paper must be reflected in the corpus-wide latest date"
        print("PASS: a paper with no v1 PaperVersion row correctly falls back to first_observed_at (same convention as embeddings.search)")
    finally:
        session.execute(delete(Paper).where(Paper.id == synthetic.id))
        session.commit()
        session.close()


def test_cluster_cohort_aggregation_matches_real_corpus():
    session = SessionLocal()
    try:
        recent = queries.count_cluster_papers_in_window(session, REAL_RUN_ID, COHORT_2026_START, COHORT_2026_END)
        previous = queries.count_cluster_papers_in_window(session, REAL_RUN_ID, COHORT_2016_START, COHORT_2016_END)

        assert recent.get(5, 0) == 11 and previous.get(5, 0) == 11, "Cluster 5 must be 11 vs 11"
        assert recent.get(0, 0) == 6 and previous.get(0, 0) == 0, "Cluster 0 must be 6 vs 0"
        assert recent.get(4, 0) == 0 and previous.get(4, 0) == 14, "Cluster 4 must be 0 vs 14"
        print("PASS: cluster cohort aggregation matches the documented real examples (5: 11/11, 0: 6/0, 4: 0/14)")
    finally:
        session.close()


def test_category_cohort_aggregation_matches_real_corpus():
    session = SessionLocal()
    try:
        recent = queries.count_category_papers_in_window(session, COHORT_2026_START, COHORT_2026_END)
        previous = queries.count_category_papers_in_window(session, COHORT_2016_START, COHORT_2016_END)
        assert recent.get("cs.CV", 0) == 12 and previous.get("cs.CV", 0) == 40
        print("PASS: category cohort aggregation matches the real corpus (cs.CV: 12 recent / 40 previous)")
    finally:
        session.close()


def test_evidence_limit_enforcement_and_deterministic_ordering():
    session = SessionLocal()
    try:
        # Cluster 2 has 20 real papers in the 2016 cohort -- well above any small limit.
        limited = queries.select_cluster_evidence_papers(session, REAL_RUN_ID, 2, COHORT_2016_START, COHORT_2016_END, 3)
        assert len(limited) == 3, f"expected exactly 3 evidence rows (the configured limit), got {len(limited)}"

        unlimited = queries.select_cluster_evidence_papers(session, REAL_RUN_ID, 2, COHORT_2016_START, COHORT_2016_END, 100)
        assert len(unlimited) == 20, f"expected all 20 real Cluster 2 papers in the 2016 cohort, got {len(unlimited)}"

        dates = [row.publication_date for row in unlimited]
        assert dates == sorted(dates), "evidence must be ordered by publication_date ascending"
        assert limited == unlimited[:3], "the limited call must return exactly the same first 3 rows as the unlimited call"

        repeat = queries.select_cluster_evidence_papers(session, REAL_RUN_ID, 2, COHORT_2016_START, COHORT_2016_END, 3)
        assert repeat == limited, "identical inputs must produce an identical, deterministically-ordered result"
        print("PASS: evidence selection enforces the limit, orders deterministically by publication_date, and is stable across repeated calls")
    finally:
        session.close()


if __name__ == "__main__":
    test_latest_successful_clustering_run_selection()
    test_approved_label_filtering()
    test_noise_papers_excluded_from_cluster_counts()
    test_publication_date_convention_reuse_including_fallback()
    test_cluster_cohort_aggregation_matches_real_corpus()
    test_category_cohort_aggregation_matches_real_corpus()
    test_evidence_limit_enforcement_and_deterministic_ordering()
    print("\nALL TESTS PASSED")
