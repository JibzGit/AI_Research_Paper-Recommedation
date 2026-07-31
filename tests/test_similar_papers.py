"""Validates similar_papers(): reuses an already-stored embedding (never
generates a new one), self-exclusion applied before LIMIT, input/paper
validation, filters, exclusion of inactive model versions / non-SUCCEEDED
rows / non-canonical papers (both as the selected paper and as candidates),
empty-result handling, and batched author fetching.

Same design note as test_semantic_search.py: the logic under test IS the
database query, so these run for real against the local dev database using
synthetic papers/categories scoped to a unique per-test category code and
fully cleaned up afterward. No model call is mocked here because
similar_papers() never calls the model at all -- it reuses the selected
paper's already-stored vector, which is exactly the behavior being tested.

No pytest dependency. Requires the local dev database to be running. Does
NOT download or call the real embedding model, and NEVER writes to
paper_embeddings for a real corpus paper. Run directly:

    python3 tests/test_similar_papers.py
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import delete, select

from research_platform import config
from research_platform.db.models import Author, Category, Paper, PaperAuthor, PaperEmbedding, PaperVersion
from research_platform.db.session import SessionLocal
from research_platform.embeddings import recommend as r
from research_platform.embeddings import search as search_module

TOL = 1e-4


def _vec(active_dims: dict) -> list:
    v = [0.0] * config.EMBEDDING_DIMENSION
    for idx, val in active_dims.items():
        v[idx] = val
    return v


E0 = _vec({0: 1.0})
E1 = _vec({1: 1.0})  # orthogonal to E0 -- similarity 0.0
MIX = _vec({0: 0.6, 1: 0.8})  # similarity 0.6 against E0


def _cat_code(label: str) -> str:
    return f"zztest-recommend.{label}.{uuid.uuid4().hex[:8]}"


def _make_paper(session, category_code, label, title="Test Title", abstract="Test abstract.",
                 is_canonical=True, submitted_at=None):
    suffix = uuid.uuid4().hex[:8]
    category = session.execute(select(Category).where(Category.code == category_code)).scalar_one_or_none()
    if category is None:
        category = Category(taxonomy_source="zztest-recommend", code=category_code, display_name=category_code)
        session.add(category)
        session.flush()
    paper = Paper(
        arxiv_id=f"zztest-recommend.{label}.{suffix}",
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
    seen = set()
    for _, category in paper_category_pairs:
        if category.id not in seen:
            session.execute(delete(Category).where(Category.id == category.id))
            seen.add(category.id)
    session.commit()


# --- validation -----------------------------------------------------------

def test_missing_paper_raises():
    try:
        r.similar_papers(str(uuid.uuid4()))
        raised = False
    except r.PaperNotFoundError as exc:
        raised = True
        message = str(exc)
    assert raised
    assert "not found" in message.lower()
    print("PASS: a paper_id with no matching paper raises PaperNotFoundError (a ValueError subclass)")


def test_invalid_paper_id_raises():
    for bad in (None, "", "not-a-uuid", 12345):
        try:
            r.similar_papers(bad)
            raised = False
        except ValueError:
            raised = True
        assert raised, f"expected ValueError for paper_id={bad!r}"
    print("PASS: invalid/empty/non-UUID paper_id raises a clear ValueError")


def test_noncanonical_selected_paper_raises():
    session = SessionLocal()
    cat = _cat_code("selnoncanon")
    p, c = _make_paper(session, cat, "p", is_canonical=False)
    try:
        _make_embedding(session, p.id, E0)
        try:
            r.similar_papers(str(p.id))
            raised = False
        except ValueError as exc:
            raised = True
            message = str(exc)
        assert raised
        assert "canonical" in message.lower()
        print("PASS: a non-canonical selected paper raises a clear ValueError")
    finally:
        _cleanup(session, (p, c))
        session.close()


def test_selected_paper_without_active_embedding_raises():
    session = SessionLocal()
    cat = _cat_code("selnoemb")
    p, c = _make_paper(session, cat, "p")
    try:
        # no embedding row at all
        try:
            r.similar_papers(str(p.id))
            raised = False
        except ValueError as exc:
            raised = True
            message = str(exc)
        assert raised
        assert "embedding" in message.lower()

        # only a FAILED row -- still not an "active successful embedding"
        _make_embedding(session, p.id, None, status="FAILED")
        try:
            r.similar_papers(str(p.id))
            raised = False
        except ValueError:
            raised = True
        assert raised
        print("PASS: a selected paper with no SUCCEEDED embedding raises a clear ValueError")
    finally:
        _cleanup(session, (p, c))
        session.close()


def test_invalid_common_filters_raise():
    session = SessionLocal()
    cat = _cat_code("badfilters")
    p, c = _make_paper(session, cat, "p")
    try:
        _make_embedding(session, p.id, E0)
        for kwargs in (
            {"top_k": 0}, {"top_k": 101}, {"year_from": "2020"},
            {"year_from": 2022, "year_to": 2018}, {"min_similarity": 1.5},
        ):
            try:
                r.similar_papers(str(p.id), **kwargs)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"expected ValueError for {kwargs}"
        print("PASS: invalid top_k/year/min_similarity all raise ValueError (shared validation reused)")
    finally:
        _cleanup(session, (p, c))
        session.close()


# --- ranking / exclusion / filters ----------------------------------------

def test_controlled_vector_ranking_and_self_exclusion():
    session = SessionLocal()
    cat = _cat_code("rank")
    selected, cat_sel = _make_paper(session, cat, "selected", title="Selected Paper")
    high, c1 = _make_paper(session, cat, "high", title="High Similarity")
    mid, c2 = _make_paper(session, cat, "mid", title="Mid Similarity")
    low, c3 = _make_paper(session, cat, "low", title="Low Similarity")
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, high.id, E0)    # identical vector -> similarity 1.0
        _make_embedding(session, mid.id, MIX)    # similarity 0.6
        _make_embedding(session, low.id, E1)     # similarity 0.0

        results = r.similar_papers(str(selected.id), top_k=10, category=cat)

        arxiv_ids = [res["arxiv_id"] for res in results]
        assert selected.arxiv_id not in arxiv_ids, "the selected paper must never recommend itself"
        assert arxiv_ids == [high.arxiv_id, mid.arxiv_id, low.arxiv_id]
        assert abs(results[0]["similarity_score"] - 1.0) < TOL
        assert abs(results[1]["similarity_score"] - 0.6) < TOL
        assert abs(results[2]["similarity_score"] - 0.0) < TOL
        print("PASS: correct controlled-vector ranking, selected paper excluded from its own results")
    finally:
        _cleanup(session, (selected, cat_sel), (high, c1), (mid, c2), (low, c3))
        session.close()


def test_top_k_applied_after_self_exclusion():
    session = SessionLocal()
    cat = _cat_code("topk")
    selected, cat_sel = _make_paper(session, cat, "selected")
    candidates = []
    try:
        _make_embedding(session, selected.id, E0)
        for i, dim_val in enumerate([1.0, 0.9, 0.8, 0.7, 0.6]):
            p, c = _make_paper(session, cat, f"cand{i}")
            vec = _vec({0: dim_val, 1: (1 - dim_val ** 2) ** 0.5})
            _make_embedding(session, p.id, vec)
            candidates.append((p, c))

        results = r.similar_papers(str(selected.id), top_k=3, category=cat)

        assert len(results) == 3, "top_k=3 must return 3 candidates, not counting the selected paper itself"
        assert all(res["arxiv_id"] != selected.arxiv_id for res in results)
        print("PASS: top_k is applied to candidates only, after the selected paper is excluded")
    finally:
        _cleanup(session, (selected, cat_sel), *candidates)
        session.close()


def test_category_filter():
    session = SessionLocal()
    cat = _cat_code("catmain")
    other_cat = _cat_code("catother")
    selected, cat_sel = _make_paper(session, cat, "selected")
    in_cat, c1 = _make_paper(session, cat, "in")
    out_cat, c2 = _make_paper(session, other_cat, "out")
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, in_cat.id, E0)
        _make_embedding(session, out_cat.id, E0)

        results = r.similar_papers(str(selected.id), top_k=10, category=cat)

        arxiv_ids = [res["arxiv_id"] for res in results]
        assert in_cat.arxiv_id in arxiv_ids
        assert out_cat.arxiv_id not in arxiv_ids
        print("PASS: category filter restricts candidates to the selected paper's category filter value")
    finally:
        _cleanup(session, (selected, cat_sel), (in_cat, c1), (out_cat, c2))
        session.close()


def test_year_from_only_filter():
    session = SessionLocal()
    cat = _cat_code("yfrom")
    selected, cat_sel = _make_paper(session, cat, "selected")
    old, c1 = _make_paper(session, cat, "old", submitted_at=datetime(2015, 1, 1, tzinfo=timezone.utc))
    new, c2 = _make_paper(session, cat, "new", submitted_at=datetime(2022, 1, 1, tzinfo=timezone.utc))
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, old.id, E0)
        _make_embedding(session, new.id, E0)

        results = r.similar_papers(str(selected.id), top_k=10, category=cat, year_from=2020)
        arxiv_ids = [res["arxiv_id"] for res in results]
        assert new.arxiv_id in arxiv_ids
        assert old.arxiv_id not in arxiv_ids
        print("PASS: year_from-only filter excludes older candidates")
    finally:
        _cleanup(session, (selected, cat_sel), (old, c1), (new, c2))
        session.close()


def test_year_to_only_filter():
    session = SessionLocal()
    cat = _cat_code("yto")
    selected, cat_sel = _make_paper(session, cat, "selected")
    old, c1 = _make_paper(session, cat, "old", submitted_at=datetime(2015, 1, 1, tzinfo=timezone.utc))
    new, c2 = _make_paper(session, cat, "new", submitted_at=datetime(2022, 1, 1, tzinfo=timezone.utc))
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, old.id, E0)
        _make_embedding(session, new.id, E0)

        results = r.similar_papers(str(selected.id), top_k=10, category=cat, year_to=2018)
        arxiv_ids = [res["arxiv_id"] for res in results]
        assert old.arxiv_id in arxiv_ids
        assert new.arxiv_id not in arxiv_ids
        print("PASS: year_to-only filter excludes newer candidates")
    finally:
        _cleanup(session, (selected, cat_sel), (old, c1), (new, c2))
        session.close()


def test_combined_year_range_filter():
    session = SessionLocal()
    cat = _cat_code("yrange")
    selected, cat_sel = _make_paper(session, cat, "selected")
    early, c1 = _make_paper(session, cat, "early", submitted_at=datetime(2012, 1, 1, tzinfo=timezone.utc))
    mid, c2 = _make_paper(session, cat, "mid", submitted_at=datetime(2018, 1, 1, tzinfo=timezone.utc))
    late, c3 = _make_paper(session, cat, "late", submitted_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    try:
        _make_embedding(session, selected.id, E0)
        for p in (early, mid, late):
            _make_embedding(session, p.id, E0)

        results = r.similar_papers(str(selected.id), top_k=10, category=cat, year_from=2016, year_to=2020)
        assert [res["arxiv_id"] for res in results] == [mid.arxiv_id]
        print("PASS: combined year_from/year_to keeps only in-range candidates")
    finally:
        _cleanup(session, (selected, cat_sel), (early, c1), (mid, c2), (late, c3))
        session.close()


def test_min_similarity_filter():
    session = SessionLocal()
    cat = _cat_code("minsim")
    selected, cat_sel = _make_paper(session, cat, "selected")
    high, c1 = _make_paper(session, cat, "high")
    mid, c2 = _make_paper(session, cat, "mid")
    low, c3 = _make_paper(session, cat, "low")
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, high.id, E0)   # similarity 1.0
        _make_embedding(session, mid.id, MIX)   # similarity 0.6
        _make_embedding(session, low.id, E1)    # similarity 0.0

        results = r.similar_papers(str(selected.id), top_k=10, category=cat, min_similarity=0.5)
        arxiv_ids = {res["arxiv_id"] for res in results}
        assert arxiv_ids == {high.arxiv_id, mid.arxiv_id}
        print("PASS: min_similarity filter excludes low-similarity candidates")
    finally:
        _cleanup(session, (selected, cat_sel), (high, c1), (mid, c2), (low, c3))
        session.close()


def test_inactive_model_version_candidates_excluded():
    session = SessionLocal()
    cat = _cat_code("oldver")
    selected, cat_sel = _make_paper(session, cat, "selected")
    candidate, c1 = _make_paper(session, cat, "candidate")
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, candidate.id, E0, model_version="0" * 40)  # stale version only

        results = r.similar_papers(str(selected.id), top_k=10, category=cat)
        assert results == [], "a candidate with only a stale/inactive model version must never appear"
        print("PASS: candidate embeddings under an inactive model version are excluded")
    finally:
        _cleanup(session, (selected, cat_sel), (candidate, c1))
        session.close()


def test_failed_and_pending_candidates_excluded():
    session = SessionLocal()
    cat = _cat_code("badstatus")
    selected, cat_sel = _make_paper(session, cat, "selected")
    failed, c1 = _make_paper(session, cat, "failed")
    pending, c2 = _make_paper(session, cat, "pending")
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, failed.id, None, status="FAILED")
        _make_embedding(session, pending.id, None, status="PENDING")

        results = r.similar_papers(str(selected.id), top_k=10, category=cat)
        assert results == []
        print("PASS: FAILED and PENDING candidate embeddings never appear (and cause no error)")
    finally:
        _cleanup(session, (selected, cat_sel), (failed, c1), (pending, c2))
        session.close()


def test_noncanonical_candidates_excluded():
    session = SessionLocal()
    cat = _cat_code("candnoncanon")
    selected, cat_sel = _make_paper(session, cat, "selected")
    noncanon, c1 = _make_paper(session, cat, "noncanon", is_canonical=False)
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, noncanon.id, E0)

        results = r.similar_papers(str(selected.id), top_k=10, category=cat)
        assert results == [], "a non-canonical candidate must never appear, even with a valid embedding"
        print("PASS: non-canonical candidates are excluded")
    finally:
        _cleanup(session, (selected, cat_sel), (noncanon, c1))
        session.close()


def test_empty_result_when_filters_remove_all_candidates():
    session = SessionLocal()
    cat = _cat_code("emptyres")
    selected, cat_sel = _make_paper(session, cat, "selected")
    only_candidate, c1 = _make_paper(session, cat, "only")
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, only_candidate.id, E0)

        # a category that legitimately has zero papers registered under it
        results = r.similar_papers(str(selected.id), top_k=10, category=_cat_code("nonexistent"))
        assert results == [], "valid filters matching nothing must return an empty list, not an error"
        print("PASS: filters that remove every candidate return an empty list")
    finally:
        _cleanup(session, (selected, cat_sel), (only_candidate, c1))
        session.close()


def test_ordered_authors_returned_correctly():
    session = SessionLocal()
    cat = _cat_code("authors")
    selected, cat_sel = _make_paper(session, cat, "selected")
    candidate, c1 = _make_paper(session, cat, "candidate")
    try:
        _make_embedding(session, selected.id, E0)
        _make_embedding(session, candidate.id, E0)
        _add_author(session, candidate.id, "Carol Third", 3)
        _add_author(session, candidate.id, "Alice First", 1)
        _add_author(session, candidate.id, "Bob Second", 2)

        results = r.similar_papers(str(selected.id), top_k=10, category=cat)
        assert len(results) == 1
        assert results[0]["authors"] == ["Alice First", "Bob Second", "Carol Third"]
        print("PASS: authors returned in author_order, independent of insertion order")
    finally:
        _cleanup(session, (selected, cat_sel), (candidate, c1))
        session.close()


def test_authors_fetched_in_one_batched_query():
    session = SessionLocal()
    cat = _cat_code("batch")
    selected, cat_sel = _make_paper(session, cat, "selected")
    candidates = []
    try:
        _make_embedding(session, selected.id, E0)
        for i in range(4):
            p, c = _make_paper(session, cat, f"cand{i}")
            _add_author(session, p.id, f"Author {i}", 1)
            _make_embedding(session, p.id, E0)
            candidates.append((p, c))

        with patch.object(
            search_module, "fetch_authors_batched", wraps=search_module.fetch_authors_batched
        ) as fake_fetch:
            results = r.similar_papers(str(selected.id), top_k=10, category=cat)

        assert len(results) == 4
        assert fake_fetch.call_count == 1, "authors must be fetched in exactly one batched call, not one per result"
        print("PASS: authors for all recommendations fetched in exactly one batched query")
    finally:
        _cleanup(session, (selected, cat_sel), *candidates)
        session.close()


if __name__ == "__main__":
    test_missing_paper_raises()
    test_invalid_paper_id_raises()
    test_noncanonical_selected_paper_raises()
    test_selected_paper_without_active_embedding_raises()
    test_invalid_common_filters_raise()
    test_controlled_vector_ranking_and_self_exclusion()
    test_top_k_applied_after_self_exclusion()
    test_category_filter()
    test_year_from_only_filter()
    test_year_to_only_filter()
    test_combined_year_range_filter()
    test_min_similarity_filter()
    test_inactive_model_version_candidates_excluded()
    test_failed_and_pending_candidates_excluded()
    test_noncanonical_candidates_excluded()
    test_empty_result_when_filters_remove_all_candidates()
    test_ordered_authors_returned_correctly()
    test_authors_fetched_in_one_batched_query()
    print("\nALL TESTS PASSED")
