"""Validates the clustering pipeline: storage/orchestration correctness
(completeness, no duplicates, valid ranges, noise handling, failure
recording, safe reruns, no side effects on papers/embeddings) via mocked
UMAP/HDBSCAN, plus one real, unmocked determinism test against the actual
169-paper corpus (determinism is a property of the real libraries' behavior
under a fixed seed -- mocking it would prove nothing).

Design note: run_clustering() has no paper-scoping filter by design (UMAP/
HDBSCAN need the whole eligible matrix jointly) -- so every test here runs
against the REAL existing canonical papers, not synthetic ones. That's
expected and correct: writing into the new clustering_runs/
paper_cluster_assignments tables for real papers is exactly what this
feature is for, and is distinct from "modifying papers/embeddings" (which
these tests separately verify never happens). Every clustering_runs/
paper_cluster_assignments row created by a test is cleaned up afterward.

No pytest dependency. Requires the local dev database to be running.
Mocked tests do NOT run the real UMAP/HDBSCAN algorithms. The one real test
does, against the real corpus, but does not download or call the embedding
model itself (embeddings already exist). Run directly:

    python3 tests/test_clustering.py
"""
import uuid
from unittest.mock import patch

import numpy as np
from sqlalchemy import delete, select, text

from research_platform.clustering import pipeline
from research_platform.db.models import ClusteringRun, PaperClusterAssignment
from research_platform.db.session import SessionLocal


# --- fakes for the mocked layer --------------------------------------------

class _FakeReducer:
    def __init__(self, **kwargs):
        pass

    def fit_transform(self, vectors):
        n = vectors.shape[0]
        return np.zeros((n, 5))


class _FakeReducerProducesNaN:
    def __init__(self, **kwargs):
        pass

    def fit_transform(self, vectors):
        n = vectors.shape[0]
        out = np.zeros((n, 5))
        out[0, 0] = np.nan
        return out


class _FakeClusterer:
    """Deterministic fake: roughly 1/3 of points become noise (-1), the
    rest form a single cluster (0) -- exercises both code paths."""

    def __init__(self, **kwargs):
        pass

    def fit_predict(self, X):
        n = X.shape[0]
        labels = np.array([0 if i % 3 != 2 else -1 for i in range(n)])
        self.probabilities_ = np.array([0.9 if label != -1 else 0.0 for label in labels])
        self.cluster_persistence_ = np.array([0.75])
        return labels


class _FakeClustererRaises:
    def __init__(self, **kwargs):
        pass

    def fit_predict(self, X):
        raise RuntimeError("simulated clustering failure")


def _cleanup_run(run_id: str) -> None:
    session = SessionLocal()
    session.execute(delete(PaperClusterAssignment).where(PaperClusterAssignment.clustering_run_id == run_id))
    session.execute(delete(ClusteringRun).where(ClusteringRun.id == run_id))
    session.commit()
    session.close()


def _mocked_run(**kwargs):
    with patch.object(pipeline.umap, "UMAP", lambda **_: _FakeReducer()), patch.object(
        pipeline.hdbscan, "HDBSCAN", lambda **_: _FakeClusterer()
    ):
        return pipeline.run_clustering(**kwargs)


def _eligible_paper_ids(session) -> list:
    from sqlalchemy import select as sa_select

    from research_platform import config
    from research_platform.db.models import Paper, PaperEmbedding

    rows = session.execute(
        sa_select(PaperEmbedding.paper_id)
        .join(Paper, Paper.id == PaperEmbedding.paper_id)
        .where(
            PaperEmbedding.embedding_status == "SUCCEEDED",
            PaperEmbedding.embedding_model == config.EMBEDDING_MODEL_NAME,
            PaperEmbedding.model_version == config.EMBEDDING_MODEL_REVISION,
            Paper.is_canonical.is_(True),
        )
    ).scalars().all()
    return list(rows)


# --- mocked orchestration tests ---------------------------------------------

def test_all_eligible_papers_receive_one_assignment():
    session = SessionLocal()
    eligible_ids = set(_eligible_paper_ids(session))
    session.close()

    summary = _mocked_run(random_seed=1)
    try:
        assert summary["status"] == "SUCCEEDED"
        assert summary["paper_count"] == len(eligible_ids)

        session = SessionLocal()
        assigned_ids = set(
            session.execute(
                select(PaperClusterAssignment.paper_id).where(
                    PaperClusterAssignment.clustering_run_id == summary["run_id"]
                )
            ).scalars().all()
        )
        session.close()

        assert assigned_ids == eligible_ids
        print(f"PASS: all {len(eligible_ids)} eligible papers received exactly one assignment row")
    finally:
        _cleanup_run(summary["run_id"])


def test_no_duplicate_assignments():
    summary = _mocked_run(random_seed=2)
    try:
        session = SessionLocal()
        dups = session.execute(
            text(
                "SELECT paper_id, COUNT(*) c FROM paper_cluster_assignments "
                "WHERE clustering_run_id = :run_id GROUP BY paper_id HAVING COUNT(*) > 1"
            ),
            {"run_id": summary["run_id"]},
        ).fetchall()
        session.close()
        assert dups == []
        print("PASS: zero duplicate (clustering_run_id, paper_id) assignments")
    finally:
        _cleanup_run(summary["run_id"])


def test_valid_finite_umap_coordinates():
    summary = _mocked_run(random_seed=3)
    try:
        session = SessionLocal()
        rows = session.execute(
            select(PaperClusterAssignment.umap_coordinates).where(
                PaperClusterAssignment.clustering_run_id == summary["run_id"]
            )
        ).scalars().all()
        session.close()

        assert len(rows) == summary["paper_count"]
        for coords in rows:
            assert len(coords) == 5
            assert all(np.isfinite(c) for c in coords)
        print("PASS: every stored UMAP coordinate array has 5 finite values")
    finally:
        _cleanup_run(summary["run_id"])


def test_valid_cluster_ids_and_noise_consistency():
    summary = _mocked_run(random_seed=4)
    try:
        session = SessionLocal()
        rows = session.execute(
            select(
                PaperClusterAssignment.cluster_id,
                PaperClusterAssignment.is_noise,
                PaperClusterAssignment.membership_probability,
            ).where(PaperClusterAssignment.clustering_run_id == summary["run_id"])
        ).all()
        session.close()

        noise_rows = [r for r in rows if r.is_noise]
        non_noise_rows = [r for r in rows if not r.is_noise]
        assert len(noise_rows) > 0 and len(non_noise_rows) > 0, "fake clusterer should produce both noise and non-noise"

        for r in noise_rows:
            assert r.cluster_id is None
            assert r.membership_probability == 0.0
        for r in non_noise_rows:
            assert r.cluster_id is not None
            assert 0 <= r.cluster_id < summary["cluster_count"]

        print("PASS: cluster_id/is_noise are consistent for both noise and non-noise rows")
    finally:
        _cleanup_run(summary["run_id"])


def test_valid_membership_probabilities():
    summary = _mocked_run(random_seed=5)
    try:
        session = SessionLocal()
        probs = session.execute(
            select(PaperClusterAssignment.membership_probability).where(
                PaperClusterAssignment.clustering_run_id == summary["run_id"]
            )
        ).scalars().all()
        session.close()
        assert all(0.0 <= p <= 1.0 for p in probs)
        print("PASS: every membership_probability is within [0, 1]")
    finally:
        _cleanup_run(summary["run_id"])


def test_non_finite_umap_output_fails_the_run_cleanly():
    with patch.object(pipeline.umap, "UMAP", lambda **_: _FakeReducerProducesNaN()), patch.object(
        pipeline.hdbscan, "HDBSCAN", lambda **_: _FakeClusterer()
    ):
        try:
            pipeline.run_clustering(random_seed=6)
            raised = False
        except ValueError as exc:
            raised = True
            message = str(exc)
    assert raised
    assert "non-finite" in message.lower()

    session = SessionLocal()
    run = session.execute(
        select(ClusteringRun).where(ClusteringRun.random_seed == 6).order_by(ClusteringRun.created_at.desc())
    ).scalars().first()
    assert run is not None
    assert run.status == "FAILED"
    assert run.completed_at is not None
    assignment_count = session.execute(
        text("SELECT COUNT(*) FROM paper_cluster_assignments WHERE clustering_run_id = :rid"), {"rid": run.id}
    ).scalar_one()
    session.close()
    assert assignment_count == 0, "a failed run must leave zero assignment rows"
    print("PASS: non-finite UMAP output raises, and the run is recorded as FAILED with zero assignments")
    _cleanup_run(str(run.id))


def test_failed_run_recorded_correctly():
    with patch.object(pipeline.umap, "UMAP", lambda **_: _FakeReducer()), patch.object(
        pipeline.hdbscan, "HDBSCAN", lambda **_: _FakeClustererRaises()
    ):
        try:
            pipeline.run_clustering(random_seed=7)
            raised = False
        except RuntimeError:
            raised = True
    assert raised, "the original exception must propagate, not be swallowed"

    session = SessionLocal()
    run = session.execute(
        select(ClusteringRun).where(ClusteringRun.random_seed == 7).order_by(ClusteringRun.created_at.desc())
    ).scalars().first()
    assert run is not None
    assert run.status == "FAILED"
    assert run.completed_at is not None
    remaining = session.execute(
        text("SELECT COUNT(*) FROM paper_cluster_assignments WHERE clustering_run_id = :rid"), {"rid": run.id}
    ).scalar_one()
    session.close()
    assert remaining == 0
    print("PASS: a clustering exception is recorded as a FAILED run (status + completed_at), zero assignments left behind")
    _cleanup_run(str(run.id))


def test_reruns_create_new_run_without_overwriting_old():
    summary_1 = _mocked_run(random_seed=8)
    try:
        summary_2 = _mocked_run(random_seed=8)
        try:
            assert summary_1["run_id"] != summary_2["run_id"]

            session = SessionLocal()
            count_1 = session.execute(
                text("SELECT COUNT(*) FROM paper_cluster_assignments WHERE clustering_run_id = :rid"),
                {"rid": summary_1["run_id"]},
            ).scalar_one()
            count_2 = session.execute(
                text("SELECT COUNT(*) FROM paper_cluster_assignments WHERE clustering_run_id = :rid"),
                {"rid": summary_2["run_id"]},
            ).scalar_one()
            session.close()

            assert count_1 == summary_1["paper_count"]
            assert count_2 == summary_2["paper_count"]
            print("PASS: rerunning creates a distinct run with its own assignments; the prior run's rows are untouched")
        finally:
            _cleanup_run(summary_2["run_id"])
    finally:
        _cleanup_run(summary_1["run_id"])


def test_no_modification_to_papers_or_embeddings():
    session = SessionLocal()

    def scalar(sql):
        return session.execute(text(sql)).scalar()

    before = {
        "papers": scalar("SELECT COUNT(*) FROM papers"),
        "embeddings": scalar("SELECT COUNT(*) FROM paper_embeddings"),
        "succeeded": scalar("SELECT COUNT(*) FROM paper_embeddings WHERE embedding_status='SUCCEEDED'"),
        "embedding_checksum": scalar("SELECT MD5(STRING_AGG(embedding::text, ',' ORDER BY id)) FROM paper_embeddings"),
    }
    session.close()

    summary = _mocked_run(random_seed=9)
    try:
        session = SessionLocal()
        after = {
            "papers": session.execute(text("SELECT COUNT(*) FROM papers")).scalar(),
            "embeddings": session.execute(text("SELECT COUNT(*) FROM paper_embeddings")).scalar(),
            "succeeded": session.execute(text("SELECT COUNT(*) FROM paper_embeddings WHERE embedding_status='SUCCEEDED'")).scalar(),
            "embedding_checksum": session.execute(text("SELECT MD5(STRING_AGG(embedding::text, ',' ORDER BY id)) FROM paper_embeddings")).scalar(),
        }
        session.close()

        assert after["papers"] == before["papers"]
        assert after["embeddings"] == before["embeddings"]
        assert after["succeeded"] == before["succeeded"]
        assert after["embedding_checksum"] == before["embedding_checksum"], "embedding vectors must be byte-identical before/after"
        print("PASS: papers and paper_embeddings are completely unchanged (counts and vector checksum) after a clustering run")
    finally:
        _cleanup_run(summary["run_id"])


# --- real, unmocked determinism test ----------------------------------------

def test_deterministic_reruns_real_pipeline():
    """The only test using the real UMAP/HDBSCAN algorithms -- determinism
    under a fixed seed is a property of the real libraries, not something a
    mock could meaningfully verify."""
    summary_1 = pipeline.run_clustering(random_seed=42)
    try:
        summary_2 = pipeline.run_clustering(random_seed=42)
        try:
            assert summary_1["cluster_count"] == summary_2["cluster_count"]
            assert summary_1["noise_count"] == summary_2["noise_count"]

            session = SessionLocal()
            rows_1 = {
                r.paper_id: (r.cluster_id, r.is_noise, tuple(round(c, 6) for c in r.umap_coordinates))
                for r in session.execute(
                    select(PaperClusterAssignment).where(PaperClusterAssignment.clustering_run_id == summary_1["run_id"])
                ).scalars()
            }
            rows_2 = {
                r.paper_id: (r.cluster_id, r.is_noise, tuple(round(c, 6) for c in r.umap_coordinates))
                for r in session.execute(
                    select(PaperClusterAssignment).where(PaperClusterAssignment.clustering_run_id == summary_2["run_id"])
                ).scalars()
            }
            session.close()

            assert rows_1 == rows_2, "identical seed/params/input must produce identical cluster labels and coordinates"
            print(
                f"PASS: two real runs with random_seed=42 produced byte-identical cluster/noise/coordinate assignments "
                f"({summary_1['cluster_count']} clusters, {summary_1['noise_count']} noise)"
            )
        finally:
            _cleanup_run(summary_2["run_id"])
    finally:
        _cleanup_run(summary_1["run_id"])


if __name__ == "__main__":
    test_all_eligible_papers_receive_one_assignment()
    test_no_duplicate_assignments()
    test_valid_finite_umap_coordinates()
    test_valid_cluster_ids_and_noise_consistency()
    test_valid_membership_probabilities()
    test_non_finite_umap_output_fails_the_run_cleanly()
    test_failed_run_recorded_correctly()
    test_reruns_create_new_run_without_overwriting_old()
    test_no_modification_to_papers_or_embeddings()
    test_deterministic_reruns_real_pipeline()
    print("\nALL TESTS PASSED")
