"""Validates GET /api/v1/categories: route-layer status/shape via mocking,
and research_platform.papers.queries.list_categories() for real against the
local dev database.

No pytest dependency. Requires the local dev database to be running. Never
writes to any table. Run directly:

    python3 tests/test_categories_api.py
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_platform.api.app import app
from research_platform.api.routes import categories as categories_route_module
from research_platform.db.models import Category, Paper
from research_platform.db.session import SessionLocal
from research_platform.papers import queries as papers_queries_module

client = TestClient(app)


# --- route layer (mocked) --------------------------------------------------

def test_categories_route_returns_mocked_shape():
    fake_items = [
        {"code": "cs.CV", "display_name": "Computer Vision", "paper_count": 52},
        {"code": "cs.LG", "display_name": "Machine Learning", "paper_count": 26},
    ]
    with patch.object(categories_route_module, "list_categories", return_value=fake_items) as fake_fn:
        response = client.get("/api/v1/categories")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["categories"] == fake_items
    assert fake_fn.call_count == 1
    print("PASS: GET /categories returns 200 with the expected shape, query function called exactly once")


def test_categories_route_preserves_order():
    fake_items = [
        {"code": "cs.CV", "display_name": "cs.CV", "paper_count": 52},
        {"code": "cs.CL", "display_name": "cs.CL", "paper_count": 20},
        {"code": "cs.AI", "display_name": "cs.AI", "paper_count": 5},
    ]
    with patch.object(categories_route_module, "list_categories", return_value=fake_items):
        response = client.get("/api/v1/categories")
    counts = [c["paper_count"] for c in response.json()["categories"]]
    assert counts == [52, 20, 5], "the route must not re-order what the query function returns"
    print("PASS: route preserves the query function's paper_count-descending order")


def test_categories_route_empty_list_returns_200():
    with patch.object(categories_route_module, "list_categories", return_value=[]) as fake_fn:
        response = client.get("/api/v1/categories")
    assert response.status_code == 200
    assert response.json() == {"count": 0, "categories": []}
    assert fake_fn.call_count == 1
    print("PASS: zero categories is a 200 with an empty list, not an error")


def test_categories_openapi_does_not_document_404():
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/api/v1/categories"]["get"]["responses"]
    assert "404" not in responses, "/categories has no genuine 404 path and must not document one"
    print("PASS: /categories does not document a 404 response")


# --- query layer (real DB) -------------------------------------------------

def test_categories_real_ordering_and_counts():
    items = papers_queries_module.list_categories()
    assert len(items) > 0
    counts = [c["paper_count"] for c in items]
    assert counts == sorted(counts, reverse=True), "must be ordered by paper_count descending"

    # within any run of equal paper_count, code must be ascending
    i = 0
    while i < len(items):
        j = i
        while j < len(items) and items[j]["paper_count"] == items[i]["paper_count"]:
            j += 1
        codes = [items[k]["code"] for k in range(i, j)]
        assert codes == sorted(codes), "ties must break by code ascending"
        i = j

    total = sum(c["paper_count"] for c in items)
    assert total == 169, "sum of per-category canonical paper counts must equal the known 169-paper corpus"
    print(f"PASS: list_categories() returns {len(items)} real categories, correctly ordered, summing to 169 canonical papers")


def test_categories_only_counts_canonical_papers():
    """Synthetic non-canonical paper under a new category must not appear
    or be counted -- cleaned up immediately after."""
    session = SessionLocal()
    category = Category(
        taxonomy_source="zztest-categories", code=f"zztest.cat.{uuid.uuid4().hex[:8]}", display_name="Test Category",
    )
    session.add(category)
    session.flush()
    paper = Paper(
        arxiv_id=f"zztest-categories.{uuid.uuid4().hex[:8]}", doi=None, normalized_title="t", title="T",
        abstract="A", primary_category_id=category.id, first_observed_source="test",
        first_observed_at=datetime.now(timezone.utc), current_version_number=1, is_canonical=False,
    )
    session.add(paper)
    session.commit()

    try:
        items = papers_queries_module.list_categories()
        codes = {c["code"] for c in items}
        assert category.code not in codes, "a category whose only paper is non-canonical must not appear"
        print("PASS: a category with only a non-canonical paper is excluded from list_categories()")
    finally:
        session.execute(delete(Paper).where(Paper.id == paper.id))
        session.execute(delete(Category).where(Category.id == category.id))
        session.commit()
        session.close()


if __name__ == "__main__":
    test_categories_route_returns_mocked_shape()
    test_categories_route_preserves_order()
    test_categories_route_empty_list_returns_200()
    test_categories_openapi_does_not_document_404()
    test_categories_real_ordering_and_counts()
    test_categories_only_counts_canonical_papers()
    print("\nALL TESTS PASSED")
