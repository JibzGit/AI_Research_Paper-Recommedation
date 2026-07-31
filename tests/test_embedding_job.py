"""Validates the embedding batch job: idempotent insert/skip/regenerate/
retry decisions, per-paper failure isolation, dimension validation, and
duplicate prevention on the real (paper_id, embedding_model, model_version)
unique constraint.

Design note on "mocked": embedding_job.py's core logic (skip-if-unchanged,
regenerate-if-changed, retry-if-failed, upsert) IS database interaction --
mocking the SQLAlchemy session away would mean not testing that logic at
all. So these tests mock only the expensive/external part (the embedding
MODEL, via encode_documents) and run for real against the local dev
database, using synthetic test papers/categories with clearly-namespaced
identifiers that are fully cleaned up after every test. They never touch
any of the real 169-paper corpus. This mirrors the project's existing
practice of running real integration checks against the disposable local
Docker Postgres rather than faking out the ORM layer.

No pytest dependency. Requires the local dev database to be running. Does
NOT download or call the real embedding model. Run directly:

    python3 tests/test_embedding_job.py
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import delete, select

from research_platform.db.models import Category, Paper, PaperEmbedding
from research_platform.db.session import SessionLocal
from research_platform.embeddings import embedding_job as ej

_VALID_VECTOR = [0.1] * 768
_ALT_VECTOR = [0.2] * 768
_WRONG_DIM_VECTOR = [0.1] * 384


def _make_test_paper(session, label: str, title: str = "Test Title", abstract: str = "Test abstract content."):
    suffix = uuid.uuid4().hex[:10]
    category = Category(
        taxonomy_source="zztest-embedding-job",
        code=f"zztest.{label}.{suffix}",
        display_name="Test Category",
    )
    session.add(category)
    session.flush()
    paper = Paper(
        arxiv_id=f"zztest-embedding-job.{label}.{suffix}",
        doi=None,
        normalized_title=title.lower(),
        title=title,
        abstract=abstract,
        primary_category_id=category.id,
        first_observed_source="test",
        first_observed_at=datetime.now(timezone.utc),
        current_version_number=1,
    )
    session.add(paper)
    session.commit()
    return paper, category


def _cleanup(session, paper_id, category_id):
    session.execute(delete(PaperEmbedding).where(PaperEmbedding.paper_id == paper_id))
    session.execute(delete(Paper).where(Paper.id == paper_id))
    session.execute(delete(Category).where(Category.id == category_id))
    session.commit()


def _embedding_rows(session, paper_id) -> list[PaperEmbedding]:
    # run_embedding_backfill() opens its OWN session internally (writes are
    # committed there, not on this test's session), so this test session's
    # identity map can hold stale cached objects from an earlier query in
    # the same test -- expire_all() forces a fresh read from the DB every
    # time, rather than silently reusing already-loaded attribute values.
    session.expire_all()
    return list(session.execute(select(PaperEmbedding).where(PaperEmbedding.paper_id == paper_id)).scalars().all())


def test_new_embedding_insertion():
    session = SessionLocal()
    paper, category = _make_test_paper(session, "insert")
    try:
        with patch.object(ej, "encode_documents", return_value=[_VALID_VECTOR]) as fake_encode:
            result = ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])

        assert result["attempted"] == 1
        assert result["created"] == 1
        assert result["updated"] == 0
        assert result["skipped"] == 0
        assert result["failed"] == 0
        assert fake_encode.call_count == 1

        rows = _embedding_rows(session, paper.id)
        assert len(rows) == 1
        row = rows[0]
        assert row.embedding_status == "SUCCEEDED"
        assert row.embedding_dimension == 768
        assert list(row.embedding) == _VALID_VECTOR
        assert row.generated_at is not None
        assert row.failure_reason is None
        print("PASS: new embedding insertion creates exactly one SUCCEEDED row")
    finally:
        _cleanup(session, paper.id, category.id)
        session.close()


def test_unchanged_hash_causes_skip():
    session = SessionLocal()
    paper, category = _make_test_paper(session, "skip")
    try:
        with patch.object(ej, "encode_documents", return_value=[_VALID_VECTOR]):
            ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])

        with patch.object(ej, "encode_documents", return_value=[_VALID_VECTOR]) as fake_encode:
            result = ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])

        assert result["skipped"] == 1
        assert result["created"] == 0
        assert result["updated"] == 0
        assert fake_encode.call_count == 0, "the model must not be called for an unchanged, already-SUCCEEDED paper"

        rows = _embedding_rows(session, paper.id)
        assert len(rows) == 1
        print("PASS: unchanged hash skips without calling the model, no duplicate row")
    finally:
        _cleanup(session, paper.id, category.id)
        session.close()


def test_changed_hash_causes_regeneration():
    session = SessionLocal()
    paper, category = _make_test_paper(session, "regen", title="Original Title")
    try:
        with patch.object(ej, "encode_documents", return_value=[_VALID_VECTOR]):
            ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])
        first_hash = _embedding_rows(session, paper.id)[0].source_text_hash

        paper.title = "Changed Title"
        session.add(paper)
        session.commit()

        with patch.object(ej, "encode_documents", return_value=[_ALT_VECTOR]) as fake_encode:
            result = ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])

        assert result["updated"] == 1
        assert result["created"] == 0
        assert result["skipped"] == 0
        assert fake_encode.call_count == 1

        rows = _embedding_rows(session, paper.id)
        assert len(rows) == 1, "regeneration must update the existing row, not insert a second one"
        row = rows[0]
        assert row.source_text_hash != first_hash
        assert list(row.embedding) == _ALT_VECTOR
        assert row.embedding_status == "SUCCEEDED"
        print("PASS: changed hash triggers regeneration, updates the same row, no duplicate")
    finally:
        _cleanup(session, paper.id, category.id)
        session.close()


def test_failed_row_is_retryable():
    session = SessionLocal()
    paper, category = _make_test_paper(session, "retry")
    try:
        with patch.object(ej, "encode_documents", side_effect=RuntimeError("simulated model failure")):
            result_1 = ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])

        assert result_1["failed"] == 1
        rows = _embedding_rows(session, paper.id)
        assert len(rows) == 1
        assert rows[0].embedding_status == "FAILED"
        assert rows[0].embedding is None
        assert "simulated model failure" in rows[0].failure_reason

        with patch.object(ej, "encode_documents", return_value=[_VALID_VECTOR]):
            result_2 = ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])

        assert result_2["failed"] == 0
        assert result_2["updated"] == 1, "a FAILED row must be retried, not skipped"
        rows = _embedding_rows(session, paper.id)
        assert len(rows) == 1, "retry must update the same row, not insert a second one"
        row = rows[0]
        assert row.embedding_status == "SUCCEEDED"
        assert list(row.embedding) == _VALID_VECTOR
        assert row.failure_reason is None, "failure_reason must be cleared on a successful retry"
        print("PASS: a FAILED row is retried on the next run and succeeds, no duplicate")
    finally:
        _cleanup(session, paper.id, category.id)
        session.close()


def test_wrong_vector_dimension_fails():
    session = SessionLocal()
    paper, category = _make_test_paper(session, "baddim")
    try:
        with patch.object(ej, "encode_documents", return_value=[_WRONG_DIM_VECTOR]):
            result = ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])

        assert result["failed"] == 1
        assert result["created"] == 0
        rows = _embedding_rows(session, paper.id)
        assert len(rows) == 1
        row = rows[0]
        assert row.embedding_status == "FAILED"
        assert row.embedding is None
        assert "768" in row.failure_reason and "384" in row.failure_reason
        print("PASS: wrong-dimension vector fails clearly, stores no vector")
    finally:
        _cleanup(session, paper.id, category.id)
        session.close()


def test_one_paper_failure_does_not_stop_the_batch():
    session = SessionLocal()
    paper_bad, category_bad = _make_test_paper(session, "batch-bad", title="Bad Paper")
    paper_good, category_good = _make_test_paper(session, "batch-good", title="Good Paper")
    try:
        def fake_encode(texts):
            if "Bad Paper" in texts[0]:
                raise RuntimeError("simulated failure for the bad paper only")
            return [_VALID_VECTOR]

        with patch.object(ej, "encode_documents", side_effect=fake_encode):
            result = ej.run_embedding_backfill(arxiv_ids=[paper_bad.arxiv_id, paper_good.arxiv_id])

        assert result["attempted"] == 2
        assert result["failed"] == 1
        assert result["created"] == 1

        bad_rows = _embedding_rows(session, paper_bad.id)
        good_rows = _embedding_rows(session, paper_good.id)
        assert len(bad_rows) == 1 and bad_rows[0].embedding_status == "FAILED"
        assert len(good_rows) == 1 and good_rows[0].embedding_status == "SUCCEEDED"
        print("PASS: one paper's failure is isolated -- the other paper in the same batch still succeeds")
    finally:
        _cleanup(session, paper_bad.id, category_bad.id)
        _cleanup(session, paper_good.id, category_good.id)
        session.close()


def test_no_duplicate_rows_across_repeated_runs():
    session = SessionLocal()
    paper, category = _make_test_paper(session, "noDupe", title="Version One")
    try:
        with patch.object(ej, "encode_documents", return_value=[_VALID_VECTOR]):
            ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])
        assert len(_embedding_rows(session, paper.id)) == 1

        with patch.object(ej, "encode_documents", return_value=[_VALID_VECTOR]):
            ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])  # unchanged -> skip
        assert len(_embedding_rows(session, paper.id)) == 1

        paper.title = "Version Two"
        session.add(paper)
        session.commit()
        with patch.object(ej, "encode_documents", return_value=[_ALT_VECTOR]) as fake_encode:
            ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])  # changed -> regenerate
        assert fake_encode.call_count == 1
        assert len(_embedding_rows(session, paper.id)) == 1

        with patch.object(ej, "encode_documents", side_effect=RuntimeError("must not be called")) as fake_encode:
            ej.run_embedding_backfill(arxiv_ids=[paper.arxiv_id])  # unchanged again -> skip, no model call
        assert fake_encode.call_count == 0
        assert len(_embedding_rows(session, paper.id)) == 1
        print("PASS: repeated runs (insert, skip, regenerate, skip) never produce a duplicate row")
    finally:
        _cleanup(session, paper.id, category.id)
        session.close()


if __name__ == "__main__":
    test_new_embedding_insertion()
    test_unchanged_hash_causes_skip()
    test_changed_hash_causes_regeneration()
    test_failed_row_is_retryable()
    test_wrong_vector_dimension_fails()
    test_one_paper_failure_does_not_stop_the_batch()
    test_no_duplicate_rows_across_repeated_runs()
    print("\nALL TESTS PASSED")
