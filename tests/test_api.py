"""Validates the FastAPI route layer: status-code mapping, JSON response
shape, that routes call search_papers()/similar_papers() exactly once with
the right args, and that FastAPI-level parameter validation (422) never
even reaches those functions. Uses FastAPI's TestClient (in-process, no
real server/socket).

Design note on "mocked": these tests mock search_papers()/similar_papers()
themselves (imported into routes/papers.py's namespace) so no real model
call or DB query happens here at all -- this file is testing routing/
schema/status-code wiring, not the underlying search logic (already
covered by test_semantic_search.py / test_similar_papers.py). The one live,
fully-unmocked integration test lives in tests/test_api_live.py.

No pytest dependency. Run directly:

    python3 tests/test_api.py
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from research_platform.api.app import app
from research_platform.api.routes import papers as papers_module
from research_platform.embeddings.recommend import PaperNotFoundError

client = TestClient(app)


def _fake_result(arxiv_id="1601.00001", title="Fake Paper", similarity=0.9):
    return {
        "paper_id": str(uuid.uuid4()),
        "arxiv_id": arxiv_id,
        "title": title,
        "abstract": "A fake abstract for testing.",
        "authors": ["Alice First", "Bob Second"],
        "primary_category": "cs.LG",
        "publication_date": datetime(2016, 1, 5, tzinfo=timezone.utc),
        "similarity_score": similarity,
    }


# --- health ---------------------------------------------------------------

def test_health_endpoint():
    from research_platform.api.routes import health as health_module
    with patch.object(health_module, "check_database_connected", return_value=True):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}
    print("PASS: /health returns 200 with the exact expected body when the DB is reachable")


def test_health_endpoint_db_down():
    from research_platform.api.routes import health as health_module
    with patch.object(health_module, "check_database_connected", return_value=False):
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "disconnected"}
    print("PASS: /health returns 503 with a degraded body when the DB check fails")


def test_openapi_documents_200_and_503_for_health():
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/health"]["get"]["responses"]
    assert set(responses.keys()) == {"200", "503"}, "must document exactly 200 and 503, nothing else"
    for code in ("200", "503"):
        schema = responses[code]["content"]["application/json"]["schema"]
        assert schema["$ref"].split("/")[-1] == "HealthResponse"
    print("PASS: /openapi.json documents 200 and 503 for /health, both referencing HealthResponse")


def test_openapi_does_not_document_404_for_health():
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/health"]["get"]["responses"]
    assert "404" not in responses, "/health can never return 404 and must not document one"
    print("PASS: /health does not document a 404 response")


def test_health_runtime_200_unchanged_after_metadata_change():
    from research_platform.api.routes import health as health_module
    with patch.object(health_module, "check_database_connected", return_value=True):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}
    print("PASS: the healthy runtime response is byte-identical to before the metadata change")


def test_health_runtime_503_unchanged_after_metadata_change():
    from research_platform.api.routes import health as health_module
    with patch.object(health_module, "check_database_connected", return_value=False):
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "disconnected"}
    print("PASS: the database-down runtime response is byte-identical to before the metadata change")


# --- search -----------------------------------------------------------------

def test_search_success():
    fake_results = [_fake_result("1601.00001", "Paper A", 0.9), _fake_result("1601.00002", "Paper B", 0.8)]
    with patch.object(papers_module, "search_papers", return_value=fake_results) as fake_search:
        response = client.get("/api/v1/papers/search", params={"query": "graph neural networks", "top_k": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "graph neural networks"
    assert body["count"] == 2
    assert len(body["results"]) == 2
    assert fake_search.call_count == 1
    _, kwargs = fake_search.call_args
    assert kwargs["query"] == "graph neural networks"
    assert kwargs["top_k"] == 5
    print("PASS: successful search returns 200, correct shape, search_papers() called exactly once with parsed args")


def test_search_with_all_optional_filters():
    with patch.object(papers_module, "search_papers", return_value=[]) as fake_search:
        response = client.get(
            "/api/v1/papers/search",
            params={
                "query": "nlp",
                "top_k": 7,
                "category": "cs.CL",
                "year_from": 2015,
                "year_to": 2020,
                "min_similarity": 0.5,
            },
        )
    assert response.status_code == 200
    assert fake_search.call_count == 1
    _, kwargs = fake_search.call_args
    assert kwargs["category"] == "cs.CL"
    assert kwargs["year_from"] == 2015 and isinstance(kwargs["year_from"], int)
    assert kwargs["year_to"] == 2020 and isinstance(kwargs["year_to"], int)
    assert kwargs["min_similarity"] == 0.5
    print("PASS: all optional filters are parsed to the correct types and forwarded to search_papers()")


def test_search_empty_query_returns_400():
    with patch.object(papers_module, "search_papers", side_effect=ValueError("query must not be empty")) as fake_search:
        response = client.get("/api/v1/papers/search", params={"query": "   "})
    assert response.status_code == 400
    assert "query" in response.json()["detail"].lower()
    assert fake_search.call_count == 1, "whitespace-only query must reach search_papers(), not be rejected by FastAPI"
    print("PASS: whitespace-only query reaches search_papers(), whose ValueError maps to 400")


def test_search_missing_query_returns_422():
    with patch.object(papers_module, "search_papers") as fake_search:
        response = client.get("/api/v1/papers/search")  # no query param at all
    assert response.status_code == 422
    assert fake_search.call_count == 0
    print("PASS: a completely missing required query param is rejected by FastAPI (422), never reaches search_papers()")


def test_search_invalid_top_k_returns_422():
    with patch.object(papers_module, "search_papers") as fake_search:
        for bad_top_k in (0, -1, 101):
            response = client.get("/api/v1/papers/search", params={"query": "x", "top_k": bad_top_k})
            assert response.status_code == 422, f"top_k={bad_top_k} should be 422"
    assert fake_search.call_count == 0, "out-of-range top_k must never reach search_papers()"
    print("PASS: out-of-range top_k is rejected before the route runs (422), search_papers() never called")


def test_search_no_results_returns_200_empty_list():
    with patch.object(papers_module, "search_papers", return_value=[]):
        response = client.get("/api/v1/papers/search", params={"query": "an extremely unlikely query"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["results"] == []
    print("PASS: zero results is a 200 with an empty list, not an error")


def test_search_with_filters_no_matches_returns_200_empty_list():
    """Same as above but with filters applied -- a valid, filtered search
    that matches nothing is still an ordinary empty result, never a 404:
    search_papers() has no runtime path that raises PaperNotFoundError."""
    with patch.object(papers_module, "search_papers", return_value=[]) as fake_search:
        response = client.get(
            "/api/v1/papers/search",
            params={"query": "graph neural networks", "category": "cs.NONEXISTENT", "year_from": 2020},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["results"] == []
    assert fake_search.call_count == 1
    print("PASS: a valid filtered search matching nothing returns 200 with an empty list, not an error")


def test_search_invalid_year_type_returns_422():
    with patch.object(papers_module, "search_papers") as fake_search:
        response = client.get("/api/v1/papers/search", params={"query": "x", "year_from": "not-a-year"})
    assert response.status_code == 422
    assert fake_search.call_count == 0
    print("PASS: a non-integer year_from is rejected by FastAPI (422), never reaches search_papers()")


def test_search_invalid_min_similarity_returns_422():
    with patch.object(papers_module, "search_papers") as fake_search:
        for bad in (1.5, -1.5):
            response = client.get("/api/v1/papers/search", params={"query": "x", "min_similarity": bad})
            assert response.status_code == 422, f"min_similarity={bad} should be 422"
    assert fake_search.call_count == 0
    print("PASS: min_similarity outside [-1, 1] is rejected by FastAPI (422), never reaches search_papers()")


def test_search_openapi_does_not_document_404():
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/api/v1/papers/search"]["get"]["responses"]
    assert "404" not in responses, "/papers/search can never raise PaperNotFoundError and must not document 404"
    print("PASS: /papers/search does not document a 404 response")


# --- paper detail --------------------------------------------------------------

def _fake_paper_detail(paper_id=None, embedding_available=True):
    return {
        "paper_id": str(paper_id or uuid.uuid4()),
        "arxiv_id": "1601.00001",
        "title": "Fake Paper",
        "abstract": "A fake abstract for testing.",
        "authors": ["Alice First", "Bob Second"],
        "primary_category": "cs.LG",
        "publication_date": datetime(2016, 1, 5, tzinfo=timezone.utc),
        "current_version_number": 2,
        "embedding_available": embedding_available,
    }


def test_paper_detail_success():
    paper_id = uuid.uuid4()
    fake_detail = _fake_paper_detail(paper_id)
    with patch.object(papers_module, "get_paper_by_id", return_value=fake_detail) as fake_fn:
        response = client.get(f"/api/v1/papers/{paper_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["paper_id"] == str(paper_id)
    assert body["embedding_available"] is True
    assert fake_fn.call_count == 1
    _, kwargs = fake_fn.call_args
    args = fake_fn.call_args.args
    assert (args and args[0] == str(paper_id)) or kwargs.get("paper_id") == str(paper_id)
    print("PASS: GET /papers/{paper_id} returns 200 with full detail, query function called exactly once")


def test_paper_detail_not_found_returns_404():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "get_paper_by_id", side_effect=PaperNotFoundError(f"paper not found: {paper_id}")):
        response = client.get(f"/api/v1/papers/{paper_id}")
    assert response.status_code == 404
    assert str(paper_id) in response.json()["detail"]
    print("PASS: PaperNotFoundError on /papers/{paper_id} maps to 404")


def test_paper_detail_non_canonical_returns_400():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "get_paper_by_id", side_effect=ValueError(f"paper is not canonical: {paper_id}")):
        response = client.get(f"/api/v1/papers/{paper_id}")
    assert response.status_code == 400
    print("PASS: a non-canonical paper maps to 400 via a plain ValueError, not 404")


def test_paper_detail_malformed_uuid_returns_422():
    with patch.object(papers_module, "get_paper_by_id") as fake_fn:
        response = client.get("/api/v1/papers/not-a-uuid")
    assert response.status_code == 422
    assert fake_fn.call_count == 0
    print("PASS: a malformed path UUID on /papers/{paper_id} is rejected by FastAPI (422), never reaches get_paper_by_id()")


def test_paper_detail_response_shape():
    with patch.object(papers_module, "get_paper_by_id", return_value=_fake_paper_detail()):
        response = client.get(f"/api/v1/papers/{uuid.uuid4()}")
    body = response.json()
    assert set(body.keys()) == {
        "paper_id", "arxiv_id", "title", "abstract", "authors",
        "primary_category", "publication_date", "current_version_number", "embedding_available",
    }
    print("PASS: PaperDetail has exactly the expected fields, no similarity_score or membership_probability")


def test_search_not_shadowed_by_paper_detail_route():
    """The critical ordering check: /search is a literal segment with the
    exact same shape as /{paper_id} (one path segment) -- if declared after
    /{paper_id}, "search" would match the dynamic route first and fail UUID
    coercion (422) instead of ever reaching the real search handler."""
    with patch.object(papers_module, "search_papers", return_value=[]) as fake_search, \
         patch.object(papers_module, "get_paper_by_id") as fake_detail:
        response = client.get("/api/v1/papers/search", params={"query": "x"})
    assert response.status_code == 200
    assert fake_search.call_count == 1
    assert fake_detail.call_count == 0, "/papers/search must never be routed to the /{paper_id} handler"
    print("PASS: /papers/search is matched by its own route, not swallowed by /papers/{paper_id}")


def test_paper_detail_openapi_documents_404():
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/api/v1/papers/{paper_id}"]["get"]["responses"]
    assert "404" in responses
    content = responses["404"]["content"]["application/json"]["schema"]
    assert content["$ref"].split("/")[-1] == "ErrorResponse"
    print("PASS: /openapi.json documents a 404 (ErrorResponse) for /papers/{paper_id}")


# --- similar ------------------------------------------------------------------

def test_similar_success():
    paper_id = uuid.uuid4()
    fake_results = [_fake_result("1601.00003", "Similar Paper", 0.85)]
    with patch.object(papers_module, "similar_papers", return_value=fake_results) as fake_similar:
        response = client.get(f"/api/v1/papers/{paper_id}/similar", params={"top_k": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["source_paper_id"] == str(paper_id)
    assert body["count"] == 1
    assert fake_similar.call_count == 1
    _, kwargs = fake_similar.call_args
    assert kwargs["paper_id"] == str(paper_id)
    assert kwargs["top_k"] == 3
    print("PASS: successful similar-paper request returns 200, correct shape, similar_papers() called exactly once")


def test_similar_with_optional_filters():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "similar_papers", return_value=[]) as fake_similar:
        response = client.get(
            f"/api/v1/papers/{paper_id}/similar",
            params={"category": "cs.CV", "year_from": 2018, "min_similarity": 0.4},
        )
    assert response.status_code == 200
    _, kwargs = fake_similar.call_args
    assert kwargs["category"] == "cs.CV"
    assert kwargs["year_from"] == 2018
    assert kwargs["min_similarity"] == 0.4
    print("PASS: optional filters forwarded correctly to similar_papers()")


def test_similar_invalid_year_range_returns_400():
    paper_id = uuid.uuid4()
    with patch.object(
        papers_module, "similar_papers",
        side_effect=ValueError("year_from (2022) must not be greater than year_to (2018)"),
    ) as fake_similar:
        response = client.get(f"/api/v1/papers/{paper_id}/similar", params={"year_from": 2022, "year_to": 2018})
    assert response.status_code == 400
    assert fake_similar.call_count == 1
    print("PASS: year_from > year_to reaches similar_papers(), whose ValueError maps to 400")


def test_similar_malformed_uuid_returns_422():
    with patch.object(papers_module, "similar_papers") as fake_similar:
        response = client.get("/api/v1/papers/not-a-uuid/similar")
    assert response.status_code == 422
    assert fake_similar.call_count == 0
    print("PASS: a malformed path UUID is rejected by FastAPI (422), never reaches similar_papers()")


def test_similar_paper_not_found_returns_404():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "similar_papers", side_effect=PaperNotFoundError(f"paper not found: {paper_id}")):
        response = client.get(f"/api/v1/papers/{paper_id}/similar")
    assert response.status_code == 404
    assert str(paper_id) in response.json()["detail"]
    print("PASS: PaperNotFoundError maps to 404 (via exact type, not message string-matching)")


def test_similar_non_canonical_or_unembedded_returns_400():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "similar_papers", side_effect=ValueError("selected paper is not canonical: x")):
        response = client.get(f"/api/v1/papers/{paper_id}/similar")
    assert response.status_code == 400
    print("PASS: a plain ValueError (non-canonical / no active embedding) maps to 400, not 404")


def test_similar_no_results_returns_200_empty_list():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "similar_papers", return_value=[]):
        response = client.get(f"/api/v1/papers/{paper_id}/similar")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["results"] == []
    print("PASS: zero similar-paper results is a 200 with an empty list, not an error")


def test_similar_with_filters_no_matches_returns_200_empty_list():
    """Same as above but with filters applied and forwarded -- mirrors
    test_search_with_filters_no_matches_returns_200_empty_list. A valid,
    filtered similar-papers request that matches nothing is still an
    ordinary empty result, never a 404."""
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "similar_papers", return_value=[]) as fake_similar:
        response = client.get(
            f"/api/v1/papers/{paper_id}/similar",
            params={"category": "cs.NONEXISTENT", "year_from": 2020},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["results"] == []
    assert fake_similar.call_count == 1
    print("PASS: a valid filtered similar-papers request matching nothing returns 200 with an empty list")


def test_similar_invalid_top_k_returns_422():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "similar_papers") as fake_similar:
        for bad_top_k in (0, -1, 101):
            response = client.get(f"/api/v1/papers/{paper_id}/similar", params={"top_k": bad_top_k})
            assert response.status_code == 422, f"top_k={bad_top_k} should be 422"
    assert fake_similar.call_count == 0, "out-of-range top_k must never reach similar_papers()"
    print("PASS: out-of-range top_k is rejected before the route runs (422), similar_papers() never called")


def test_similar_invalid_min_similarity_returns_422():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "similar_papers") as fake_similar:
        for bad in (1.5, -1.5):
            response = client.get(f"/api/v1/papers/{paper_id}/similar", params={"min_similarity": bad})
            assert response.status_code == 422, f"min_similarity={bad} should be 422"
    assert fake_similar.call_count == 0
    print("PASS: min_similarity outside [-1, 1] is rejected by FastAPI (422), never reaches similar_papers()")


def test_similar_invalid_year_type_returns_422():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "similar_papers") as fake_similar:
        response = client.get(f"/api/v1/papers/{paper_id}/similar", params={"year_from": "not-a-year"})
    assert response.status_code == 422
    assert fake_similar.call_count == 0
    print("PASS: a non-integer year_from is rejected by FastAPI (422), never reaches similar_papers()")


# --- response shape ----------------------------------------------------------

def test_correct_json_response_shape():
    fake_results = [_fake_result()]
    with patch.object(papers_module, "search_papers", return_value=fake_results):
        response = client.get("/api/v1/papers/search", params={"query": "x"})
    body = response.json()
    assert set(body.keys()) == {"query", "count", "results"}
    result_keys = set(body["results"][0].keys())
    assert result_keys == {
        "paper_id", "arxiv_id", "title", "abstract", "authors",
        "primary_category", "publication_date", "similarity_score",
    }
    print("PASS: response JSON has exactly the fields defined by SearchResponse/PaperResult, no more, no less")


# --- OpenAPI 404 metadata -------------------------------------------------

def test_openapi_documents_404_for_similar_only():
    spec = client.get("/openapi.json").json()

    similar_responses = spec["paths"]["/api/v1/papers/{paper_id}/similar"]["get"]["responses"]
    assert "404" in similar_responses
    content = similar_responses["404"]["content"]["application/json"]["schema"]
    assert content["$ref"].split("/")[-1] == "ErrorResponse"

    search_responses = spec["paths"]["/api/v1/papers/search"]["get"]["responses"]
    assert "404" not in search_responses, "/papers/search can never raise PaperNotFoundError, must not document 404"
    print("PASS: /openapi.json documents 404 (ErrorResponse) only for /papers/{paper_id}/similar, not /papers/search")


def test_runtime_404_behavior_unchanged_after_metadata_change():
    paper_id = uuid.uuid4()
    with patch.object(papers_module, "similar_papers", side_effect=PaperNotFoundError(f"paper not found: {paper_id}")):
        response = client.get(f"/api/v1/papers/{paper_id}/similar")
    assert response.status_code == 404
    assert response.json() == {"detail": f"paper not found: {paper_id}"}
    print("PASS: runtime 404 status code and body are byte-identical to before the metadata change")


if __name__ == "__main__":
    test_health_endpoint()
    test_health_endpoint_db_down()
    test_openapi_documents_200_and_503_for_health()
    test_openapi_does_not_document_404_for_health()
    test_health_runtime_200_unchanged_after_metadata_change()
    test_health_runtime_503_unchanged_after_metadata_change()
    test_search_success()
    test_search_with_all_optional_filters()
    test_search_empty_query_returns_400()
    test_search_missing_query_returns_422()
    test_search_invalid_top_k_returns_422()
    test_search_no_results_returns_200_empty_list()
    test_search_with_filters_no_matches_returns_200_empty_list()
    test_search_invalid_year_type_returns_422()
    test_search_invalid_min_similarity_returns_422()
    test_search_openapi_does_not_document_404()
    test_paper_detail_success()
    test_paper_detail_not_found_returns_404()
    test_paper_detail_non_canonical_returns_400()
    test_paper_detail_malformed_uuid_returns_422()
    test_paper_detail_response_shape()
    test_search_not_shadowed_by_paper_detail_route()
    test_paper_detail_openapi_documents_404()
    test_similar_success()
    test_similar_with_optional_filters()
    test_similar_invalid_year_range_returns_400()
    test_similar_malformed_uuid_returns_422()
    test_similar_paper_not_found_returns_404()
    test_similar_non_canonical_or_unembedded_returns_400()
    test_similar_no_results_returns_200_empty_list()
    test_similar_with_filters_no_matches_returns_200_empty_list()
    test_similar_invalid_top_k_returns_422()
    test_similar_invalid_min_similarity_returns_422()
    test_similar_invalid_year_type_returns_422()
    test_correct_json_response_shape()
    test_openapi_documents_404_for_similar_only()
    test_runtime_404_behavior_unchanged_after_metadata_change()
    print("\nALL TESTS PASSED")
