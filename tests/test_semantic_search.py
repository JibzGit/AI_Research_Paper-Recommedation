"""Validates search_papers(): input validation, exact cosine ranking,
filters (category/year/min_similarity/top_k), exclusion of inactive model
versions / non-SUCCEEDED rows / non-canonical papers, empty-result handling,
and batched (not N+1) author fetching.

Design note on "mocked": as with test_embedding_job.py, the logic under
test IS the database query (ranking, filtering, exclusion) -- mocking the
session away would mean not testing it. These tests mock only the
embedding MODEL (encode_query, via controlled hand-crafted unit vectors
with exactly known cosine similarities) and run for real against the local
dev database, using synthetic papers/categories that are always scoped to
a unique per-test category code (so results are provably isolated from the
real 169-paper corpus) and fully cleaned up afterward.

No pytest dependency. Requires the local dev database to be running. Does
NOT download or call the real embedding model, and NEVER writes to
paper_embeddings for a real corpus paper. Run directly:

    python3 tests/test_semantic_search.py
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import delete, select

from research_platform import config
from research_platform.db.models import Author, Category, Paper, PaperAuthor, PaperEmbedding, PaperVersion
from research_platform.db.session import SessionLocal
from research_platform.embeddings import search as s

TOL = 1e-4


def _vec(active_dims: dict) -> list:
    v = [0.0] * config.EMBEDDING_DIMENSION
    for idx, val in active_dims.items():
        v[idx] = val
    return v


E0 = _vec({0: 1.0})  # unit vector, dim 0
E1 = _vec({1: 1.0})  # unit vector, dim 1 -- orthogonal to E0 (similarity 0.0 against E0)
MIX = _vec({0: 0.6, 1: 0.8})  # unit vector -- similarity 0.6 against E0


def _make_paper(session, category_code, label, title="Test Title", abstract="Test abstract.",
                 is_canonical=True, submitted_at=None, category_display=None):
    suffix = uuid.uuid4().hex[:8]
    category = session.execute(select(Category).where(Category.code == category_code)).scalar_one_or_none()
    if category is None:
        category = Category(taxonomy_source="zztest-search", code=category_code, display_name=category_display or category_code)
        session.add(category)
        session.flush()
    paper = Paper(
        arxiv_id=f"zztest-search.{label}.{suffix}",
        doi=None,
        normalized_title=title.lower(),
        title=title,
        abstract=abstract,
        primary_category_id=category.id,
        first_observed_source="test",
        first_observed_at=submitted_at or datetime.now(timezone.utc),
        current_version_number=1,
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


def _make_embedding(session, paper_id, vector, status="SUCCEEDED", model_name=None, model_version=None):
    emb = PaperEmbedding(
        paper_id=paper_id,
        embedding_model=model_name or config.EMBEDDING_MODEL_NAME,
        model_version=model_version or config.EMBEDDING_MODEL_REVISION,
        embedding_dimension=config.EMBEDDING_DIMENSION,
        embedding=vector,
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


def _cleanup(session, *paper_category_pairs):
    for paper, category in paper_category_pairs:
        session.execute(delete(PaperAuthor).where(PaperAuthor.paper_id == paper.id))
        session.execute(delete(PaperVersion).where(PaperVersion.paper_id == paper.id))
        session.execute(delete(PaperEmbedding).where(PaperEmbedding.paper_id == paper.id))
        session.execute(delete(Paper).where(Paper.id == paper.id))
    # categories may be shared across papers in the same test -- delete distinct ones only
    seen = set()
    for _, category in paper_category_pairs:
        if category.id not in seen:
            session.execute(delete(Category).where(Category.id == category.id))
            seen.add(category.id)
    session.commit()


def _cat_code(label: str) -> str:
    return f"zztest-search.{label}.{uuid.uuid4().hex[:8]}"


# --- validation ---------------------------------------------------------

def test_empty_query_raises():
    with patch.object(s, "encode_query") as fake_encode:
        for bad in (None, "", "   "):
            try:
                s.search_papers(bad)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"expected ValueError for query={bad!r}"
        assert fake_encode.call_count == 0, "encode_query must not be called when validation fails"
    print("PASS: empty/None/whitespace-only query raises ValueError, no model call")


def test_invalid_top_k_raises():
    with patch.object(s, "encode_query") as fake_encode:
        for bad in (0, -1, 101, 1000, "10", 3.5, True):
            try:
                s.search_papers("some query", top_k=bad)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"expected ValueError for top_k={bad!r}"
        assert fake_encode.call_count == 0
    print("PASS: invalid top_k (out of range, non-int, bool) raises ValueError, no model call")


def test_invalid_year_types_raise():
    with patch.object(s, "encode_query"):
        for bad in ("2020", 2020.5, True):
            try:
                s.search_papers("q", year_from=bad)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"expected ValueError for year_from={bad!r}"
            try:
                s.search_papers("q", year_to=bad)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"expected ValueError for year_to={bad!r}"
    print("PASS: non-integer year_from/year_to raise ValueError")


def test_invalid_year_range_raises():
    with patch.object(s, "encode_query"):
        try:
            s.search_papers("q", year_from=2022, year_to=2018)
            raised = False
        except ValueError:
            raised = True
    assert raised, "expected ValueError when year_from > year_to"
    print("PASS: year_from > year_to raises ValueError")


def test_invalid_min_similarity_raises():
    with patch.object(s, "encode_query"):
        for bad in (-1.5, 1.5, "0.5", True):
            try:
                s.search_papers("q", min_similarity=bad)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"expected ValueError for min_similarity={bad!r}"
    print("PASS: out-of-range/non-numeric min_similarity raises ValueError")


# --- ranking / filters (scoped to synthetic-only categories) ------------

def test_similarity_ranking_with_controlled_vectors():
    session = SessionLocal()
    cat = _cat_code("rank")
    a, cat_a = _make_paper(session, cat, "a", title="Paper A")
    b, cat_b = _make_paper(session, cat, "b", title="Paper B")
    c, cat_c = _make_paper(session, cat, "c", title="Paper C")
    try:
        _make_embedding(session, a.id, E0)     # similarity 1.0 against query=E0
        _make_embedding(session, b.id, MIX)    # similarity 0.6
        _make_embedding(session, c.id, E1)     # similarity 0.0

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("irrelevant text", top_k=10, category=cat)

        assert [r["arxiv_id"] for r in results] == [a.arxiv_id, b.arxiv_id, c.arxiv_id]
        assert abs(results[0]["similarity_score"] - 1.0) < TOL
        assert abs(results[1]["similarity_score"] - 0.6) < TOL
        assert abs(results[2]["similarity_score"] - 0.0) < TOL
        print("PASS: results ranked highest-to-lowest similarity with correct scores")
    finally:
        _cleanup(session, (a, cat_a), (b, cat_b), (c, cat_c))
        session.close()


def test_top_k_limit():
    session = SessionLocal()
    cat = _cat_code("topk")
    papers = []
    try:
        for i, dim_val in enumerate([1.0, 0.9, 0.8, 0.7, 0.6]):
            p, c = _make_paper(session, cat, f"p{i}", title=f"Paper {i}")
            vec = _vec({0: dim_val, 1: (1 - dim_val**2) ** 0.5})
            _make_embedding(session, p.id, vec)
            papers.append((p, c))

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=2, category=cat)

        assert len(results) == 2
        assert results[0]["arxiv_id"] == papers[0][0].arxiv_id
        assert results[1]["arxiv_id"] == papers[1][0].arxiv_id
        print("PASS: top_k limits result count to the highest-similarity subset")
    finally:
        _cleanup(session, *papers)
        session.close()


def test_category_filter_isolates_results():
    session = SessionLocal()
    cat_x = _cat_code("catx")
    cat_y = _cat_code("caty")
    px, cx = _make_paper(session, cat_x, "x", title="In Category X")
    py, cy = _make_paper(session, cat_y, "y", title="In Category Y")
    try:
        _make_embedding(session, px.id, E0)
        _make_embedding(session, py.id, E0)

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=10, category=cat_x)

        arxiv_ids = [r["arxiv_id"] for r in results]
        assert px.arxiv_id in arxiv_ids
        assert py.arxiv_id not in arxiv_ids
        print("PASS: category filter excludes papers from other categories")
    finally:
        _cleanup(session, (px, cx), (py, cy))
        session.close()


def test_year_from_only_filter():
    session = SessionLocal()
    cat = _cat_code("yfrom")
    old, cat_old = _make_paper(session, cat, "old", submitted_at=datetime(2015, 1, 1, tzinfo=timezone.utc))
    new, cat_new = _make_paper(session, cat, "new", submitted_at=datetime(2022, 1, 1, tzinfo=timezone.utc))
    try:
        _make_embedding(session, old.id, E0)
        _make_embedding(session, new.id, E0)

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=10, category=cat, year_from=2020)

        arxiv_ids = [r["arxiv_id"] for r in results]
        assert new.arxiv_id in arxiv_ids
        assert old.arxiv_id not in arxiv_ids
        print("PASS: year_from-only filter excludes papers published before the cutoff")
    finally:
        _cleanup(session, (old, cat_old), (new, cat_new))
        session.close()


def test_year_to_only_filter():
    session = SessionLocal()
    cat = _cat_code("yto")
    old, cat_old = _make_paper(session, cat, "old", submitted_at=datetime(2015, 1, 1, tzinfo=timezone.utc))
    new, cat_new = _make_paper(session, cat, "new", submitted_at=datetime(2022, 1, 1, tzinfo=timezone.utc))
    try:
        _make_embedding(session, old.id, E0)
        _make_embedding(session, new.id, E0)

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=10, category=cat, year_to=2018)

        arxiv_ids = [r["arxiv_id"] for r in results]
        assert old.arxiv_id in arxiv_ids
        assert new.arxiv_id not in arxiv_ids
        print("PASS: year_to-only filter excludes papers published after the cutoff")
    finally:
        _cleanup(session, (old, cat_old), (new, cat_new))
        session.close()


def test_combined_year_range_filter():
    session = SessionLocal()
    cat = _cat_code("yrange")
    early, c1 = _make_paper(session, cat, "early", submitted_at=datetime(2012, 1, 1, tzinfo=timezone.utc))
    mid, c2 = _make_paper(session, cat, "mid", submitted_at=datetime(2018, 1, 1, tzinfo=timezone.utc))
    late, c3 = _make_paper(session, cat, "late", submitted_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    try:
        for p in (early, mid, late):
            _make_embedding(session, p.id, E0)

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=10, category=cat, year_from=2016, year_to=2020)

        arxiv_ids = [r["arxiv_id"] for r in results]
        assert arxiv_ids == [mid.arxiv_id]
        print("PASS: combined year_from/year_to keeps only papers inside the range")
    finally:
        _cleanup(session, (early, c1), (mid, c2), (late, c3))
        session.close()


def test_min_similarity_filter():
    session = SessionLocal()
    cat = _cat_code("minsim")
    high, c1 = _make_paper(session, cat, "high")
    mid, c2 = _make_paper(session, cat, "mid")
    low, c3 = _make_paper(session, cat, "low")
    try:
        _make_embedding(session, high.id, E0)   # similarity 1.0
        _make_embedding(session, mid.id, MIX)   # similarity 0.6
        _make_embedding(session, low.id, E1)    # similarity 0.0

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=10, category=cat, min_similarity=0.5)

        arxiv_ids = {r["arxiv_id"] for r in results}
        assert arxiv_ids == {high.arxiv_id, mid.arxiv_id}
        assert all(r["similarity_score"] >= 0.5 - TOL for r in results)
        print("PASS: min_similarity filter excludes results below the threshold")
    finally:
        _cleanup(session, (high, c1), (mid, c2), (low, c3))
        session.close()


def test_inactive_model_version_excluded():
    session = SessionLocal()
    cat = _cat_code("oldver")
    p, c = _make_paper(session, cat, "p")
    try:
        _make_embedding(session, p.id, E0)  # current pinned version
        _make_embedding(session, p.id, E0, model_version="0" * 40)  # stale/inactive version

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=10, category=cat)

        assert len(results) == 1, "only the currently-configured model version should ever be returned"
        print("PASS: embeddings under an inactive model version are excluded")
    finally:
        _cleanup(session, (p, c))
        session.close()


def test_failed_and_pending_embeddings_excluded():
    session = SessionLocal()
    cat = _cat_code("badstatus")
    failed, c1 = _make_paper(session, cat, "failed")
    pending, c2 = _make_paper(session, cat, "pending")
    try:
        _make_embedding(session, failed.id, None, status="FAILED")
        _make_embedding(session, pending.id, None, status="PENDING")

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=10, category=cat)

        assert results == []
        print("PASS: FAILED and PENDING embeddings never appear in results (and cause no error)")
    finally:
        _cleanup(session, (failed, c1), (pending, c2))
        session.close()


def test_noncanonical_papers_excluded():
    session = SessionLocal()
    cat = _cat_code("noncanon")
    p, c = _make_paper(session, cat, "p", is_canonical=False)
    try:
        _make_embedding(session, p.id, E0)

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=10, category=cat)

        assert results == []
        print("PASS: non-canonical papers are excluded even with a valid SUCCEEDED embedding")
    finally:
        _cleanup(session, (p, c))
        session.close()


def test_no_results_case_returns_empty_list():
    empty_category = _cat_code("empty")
    with patch.object(s, "encode_query", return_value=E0):
        results = s.search_papers("q", top_k=10, category=empty_category)
    assert results == []
    print("PASS: valid query/filters with no matches returns an empty list, not an error")


def test_ordered_authors_returned_correctly():
    session = SessionLocal()
    cat = _cat_code("authors")
    p, c = _make_paper(session, cat, "p")
    try:
        # inserted out of order to prove ordering comes from author_order, not insertion order
        _add_author(session, p.id, "Carol Third", 3)
        _add_author(session, p.id, "Alice First", 1)
        _add_author(session, p.id, "Bob Second", 2)
        _make_embedding(session, p.id, E0)

        with patch.object(s, "encode_query", return_value=E0):
            results = s.search_papers("q", top_k=10, category=cat)

        assert len(results) == 1
        assert results[0]["authors"] == ["Alice First", "Bob Second", "Carol Third"]
        print("PASS: authors returned in author_order, independent of insertion order")
    finally:
        _cleanup(session, (p, c))
        session.close()


def test_authors_fetched_in_one_batched_query():
    session = SessionLocal()
    cat = _cat_code("batch")
    papers = []
    try:
        for i in range(4):
            p, c = _make_paper(session, cat, f"p{i}")
            _add_author(session, p.id, f"Author {i}", 1)
            _make_embedding(session, p.id, E0)
            papers.append((p, c))

        with patch.object(s, "encode_query", return_value=E0), patch.object(
            s, "fetch_authors_batched", wraps=s.fetch_authors_batched
        ) as fake_fetch:
            results = s.search_papers("q", top_k=10, category=cat)

        assert len(results) == 4
        assert fake_fetch.call_count == 1, "authors must be fetched in exactly one batched call, not one per result"
        print("PASS: authors for all results fetched in exactly one batched query")
    finally:
        _cleanup(session, *papers)
        session.close()


if __name__ == "__main__":
    test_empty_query_raises()
    test_invalid_top_k_raises()
    test_invalid_year_types_raise()
    test_invalid_year_range_raises()
    test_invalid_min_similarity_raises()
    test_similarity_ranking_with_controlled_vectors()
    test_top_k_limit()
    test_category_filter_isolates_results()
    test_year_from_only_filter()
    test_year_to_only_filter()
    test_combined_year_range_filter()
    test_min_similarity_filter()
    test_inactive_model_version_excluded()
    test_failed_and_pending_embeddings_excluded()
    test_noncanonical_papers_excluded()
    test_no_results_case_returns_empty_list()
    test_ordered_authors_returned_correctly()
    test_authors_fetched_in_one_batched_query()
    print("\nALL TESTS PASSED")
