"""Validates papers.queries.get_paper_by_id(): missing-paper -> 404
(PaperNotFoundError), non-canonical -> 400 (plain ValueError, mirroring
similar_papers()'s existing rule), embedding_available reflecting the same
"active successful embedding" definition similar_papers() uses, and correct
field mapping (authors in order, publication_date fallback).

No pytest dependency. Requires the local dev database to be running. Run
directly:

    python3 tests/test_paper_detail.py
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete

from research_platform import config
from research_platform.db.models import Author, Category, Paper, PaperAuthor, PaperEmbedding, PaperVersion
from research_platform.db.session import SessionLocal
from research_platform.embeddings.recommend import PaperNotFoundError
from research_platform.papers import queries as p


def _cat_code(label: str) -> str:
    return f"zztest-paperdetail.{label}.{uuid.uuid4().hex[:8]}"


def _make_paper(session, category_code, label, title="Test Title", abstract="Test abstract.",
                 is_canonical=True, submitted_at=None):
    suffix = uuid.uuid4().hex[:8]
    category = Category(taxonomy_source="zztest-paperdetail", code=category_code, display_name="Test Cat")
    session.add(category)
    session.flush()
    paper = Paper(
        arxiv_id=f"zztest-paperdetail.{label}.{suffix}", doi=None, normalized_title=title.lower(), title=title,
        abstract=abstract, primary_category_id=category.id, first_observed_source="test",
        first_observed_at=submitted_at or datetime.now(timezone.utc), current_version_number=2,
        is_canonical=is_canonical,
    )
    session.add(paper)
    session.flush()
    if submitted_at is not None:
        session.add(PaperVersion(
            paper_id=paper.id, source="test", version_number=1,
            version_identifier=f"{paper.arxiv_id}v1", title=title, abstract=abstract,
            submitted_at=submitted_at, content_verified=True, is_latest=True,
        ))
    session.commit()
    return paper, category


def _make_embedding(session, paper_id, status="SUCCEEDED", model_name=None, model_version=None):
    emb = PaperEmbedding(
        paper_id=paper_id,
        embedding_model=model_name or config.EMBEDDING_MODEL_NAME,
        model_version=model_version or config.EMBEDDING_MODEL_REVISION,
        embedding_dimension=config.EMBEDDING_DIMENSION,
        embedding=[0.0] * config.EMBEDDING_DIMENSION if status == "SUCCEEDED" else None,
        source_text_hash=uuid.uuid4().hex,
        embedding_status=status,
        generated_at=datetime.now(timezone.utc) if status == "SUCCEEDED" else None,
    )
    session.add(emb)
    session.commit()
    return emb


def _add_author(session, paper_id, name, order):
    author = Author(display_name=name, normalized_name=name.lower())
    session.add(author)
    session.flush()
    session.add(PaperAuthor(paper_id=paper_id, author_id=author.id, author_order=order))
    session.commit()


def _cleanup(session, paper, category):
    session.execute(delete(PaperAuthor).where(PaperAuthor.paper_id == paper.id))
    session.execute(delete(PaperVersion).where(PaperVersion.paper_id == paper.id))
    session.execute(delete(PaperEmbedding).where(PaperEmbedding.paper_id == paper.id))
    session.execute(delete(Paper).where(Paper.id == paper.id))
    session.execute(delete(Category).where(Category.id == category.id))
    session.commit()


def test_missing_paper_raises_not_found():
    try:
        p.get_paper_by_id(str(uuid.uuid4()))
        raised = False
    except PaperNotFoundError as exc:
        raised = True
        message = str(exc)
    assert raised
    assert "not found" in message.lower()
    print("PASS: a paper_id with no matching paper raises PaperNotFoundError")


def test_invalid_paper_id_raises_value_error():
    for bad in (None, "", "not-a-uuid", 12345):
        try:
            p.get_paper_by_id(bad)
            raised = False
        except PaperNotFoundError:
            raised = False
        except ValueError:
            raised = True
        assert raised, f"expected ValueError for paper_id={bad!r}"
    print("PASS: invalid/empty/non-UUID paper_id raises a plain ValueError, not PaperNotFoundError")


def test_non_canonical_paper_raises_value_error_not_not_found():
    session = SessionLocal()
    cat = _cat_code("noncanon")
    paper, category = _make_paper(session, cat, "p", is_canonical=False)
    try:
        try:
            p.get_paper_by_id(str(paper.id))
            raised, is_not_found = False, False
        except PaperNotFoundError:
            raised, is_not_found = True, True
        except ValueError:
            raised, is_not_found = True, False
        assert raised
        assert not is_not_found, "a non-canonical paper genuinely exists -- must be a plain ValueError (400), never PaperNotFoundError (404)"
        print("PASS: a non-canonical paper raises a plain ValueError (400), mirroring similar_papers()'s rule")
    finally:
        _cleanup(session, paper, category)
        session.close()


def test_canonical_paper_with_active_embedding_returns_full_detail():
    session = SessionLocal()
    cat = _cat_code("withemb")
    submitted = datetime(2020, 5, 1, tzinfo=timezone.utc)
    paper, category = _make_paper(session, cat, "p", title="A Real Paper", abstract="Abstract text.", submitted_at=submitted)
    try:
        _make_embedding(session, paper.id, status="SUCCEEDED")
        _add_author(session, paper.id, "Carol Third", 3)
        _add_author(session, paper.id, "Alice First", 1)
        _add_author(session, paper.id, "Bob Second", 2)

        result = p.get_paper_by_id(str(paper.id))

        assert result["paper_id"] == str(paper.id)
        assert result["title"] == "A Real Paper"
        assert result["abstract"] == "Abstract text."
        assert result["authors"] == ["Alice First", "Bob Second", "Carol Third"]
        assert result["primary_category"] in (category.display_name, category.code)
        assert result["publication_date"] == submitted
        assert result["current_version_number"] == 2
        assert result["embedding_available"] is True
        print("PASS: a canonical paper with an active SUCCEEDED embedding returns full detail, embedding_available=True")
    finally:
        _cleanup(session, paper, category)
        session.close()


def test_canonical_paper_without_embedding_row_returns_embedding_available_false():
    session = SessionLocal()
    cat = _cat_code("noemb")
    paper, category = _make_paper(session, cat, "p")
    try:
        # no PaperEmbedding row at all
        result = p.get_paper_by_id(str(paper.id))
        assert result["embedding_available"] is False
        print("PASS: a canonical paper with no embedding row at all returns embedding_available=False")
    finally:
        _cleanup(session, paper, category)
        session.close()


def test_canonical_paper_with_only_failed_embedding_returns_embedding_available_false():
    session = SessionLocal()
    cat = _cat_code("failedemb")
    paper, category = _make_paper(session, cat, "p")
    try:
        _make_embedding(session, paper.id, status="FAILED")
        result = p.get_paper_by_id(str(paper.id))
        assert result["embedding_available"] is False
        print("PASS: a paper with only a FAILED embedding row returns embedding_available=False")
    finally:
        _cleanup(session, paper, category)
        session.close()


def test_canonical_paper_with_only_stale_model_version_returns_embedding_available_false():
    session = SessionLocal()
    cat = _cat_code("staleemb")
    paper, category = _make_paper(session, cat, "p")
    try:
        _make_embedding(session, paper.id, status="SUCCEEDED", model_version="0" * 40)
        result = p.get_paper_by_id(str(paper.id))
        assert result["embedding_available"] is False
        print("PASS: a SUCCEEDED embedding under an inactive model version returns embedding_available=False")
    finally:
        _cleanup(session, paper, category)
        session.close()


def test_publication_date_falls_back_to_first_observed_at_when_no_v1_version():
    session = SessionLocal()
    cat = _cat_code("nofallback")
    paper, category = _make_paper(session, cat, "p")  # submitted_at=None -> no PaperVersion row created
    try:
        result = p.get_paper_by_id(str(paper.id))
        assert result["publication_date"] == paper.first_observed_at
        print("PASS: publication_date falls back to first_observed_at when no v1 PaperVersion row exists")
    finally:
        _cleanup(session, paper, category)
        session.close()


if __name__ == "__main__":
    test_missing_paper_raises_not_found()
    test_invalid_paper_id_raises_value_error()
    test_non_canonical_paper_raises_value_error_not_not_found()
    test_canonical_paper_with_active_embedding_returns_full_detail()
    test_canonical_paper_without_embedding_row_returns_embedding_available_false()
    test_canonical_paper_with_only_failed_embedding_returns_embedding_available_false()
    test_canonical_paper_with_only_stale_model_version_returns_embedding_available_false()
    test_publication_date_falls_back_to_first_observed_at_when_no_v1_version()
    print("\nALL TESTS PASSED")
