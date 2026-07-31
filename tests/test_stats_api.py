"""Validates GET /api/v1/stats/overview: route-layer status/shape via
mocking, and research_platform.stats.get_platform_overview() for real
against the local dev database -- both the normal (a real SUCCEEDED run
exists) and "no successful run" cases. The "no run" case is exercised via
mocking get_latest_successful_run() rather than deleting the real
ClusteringRun row, which would be destructive.

No pytest dependency. Requires the local dev database to be running. Never
writes to any table. Run directly:

    python3 tests/test_stats_api.py
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from research_platform import stats as stats_module
from research_platform.api.app import app
from research_platform.api.routes import stats as stats_route_module

client = TestClient(app)


# --- route layer (mocked) --------------------------------------------------

def test_overview_route_returns_mocked_shape():
    fake_result = {
        "total_canonical_papers": 200,
        "embedded_papers": 190,
        "approved_clusters": 12,
        "clustered_papers": 160,
        "noise_papers": 30,
        "latest_clustering_run_id": "11111111-1111-1111-1111-111111111111",
        "database_status": "connected",
    }
    with patch.object(stats_route_module, "get_platform_overview", return_value=fake_result) as fake_fn:
        response = client.get("/api/v1/stats/overview")
    assert response.status_code == 200
    assert response.json() == fake_result
    assert fake_fn.call_count == 1
    print("PASS: GET /stats/overview returns 200 with the query function's shape, called exactly once")


def test_overview_route_passes_through_no_run_nulls():
    fake_result = {
        "total_canonical_papers": 5,
        "embedded_papers": 0,
        "approved_clusters": 0,
        "clustered_papers": 0,
        "noise_papers": 0,
        "latest_clustering_run_id": None,
        "database_status": "connected",
    }
    with patch.object(stats_route_module, "get_platform_overview", return_value=fake_result):
        response = client.get("/api/v1/stats/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["latest_clustering_run_id"] is None
    assert body["approved_clusters"] == 0
    assert body["clustered_papers"] == 0
    assert body["noise_papers"] == 0
    print("PASS: a null latest_clustering_run_id and zeroed run-scoped counts pass through as 200, not an error")


def test_overview_openapi_does_not_document_404():
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/api/v1/stats/overview"]["get"]["responses"]
    assert "404" not in responses, "/stats/overview has no genuine 404 path and must not document one"
    print("PASS: /stats/overview does not document a 404 response")


# --- query layer (real DB) -------------------------------------------------

def test_overview_real_values_match_known_corpus():
    result = stats_module.get_platform_overview()
    assert result["total_canonical_papers"] == 169
    assert result["embedded_papers"] == 169
    assert result["approved_clusters"] == 10
    assert result["clustered_papers"] == 148
    assert result["noise_papers"] == 21
    assert result["latest_clustering_run_id"] == "084a1215-53be-4644-86e5-6f8a84b5422f"
    assert result["database_status"] == "connected"
    print("PASS: get_platform_overview() matches the known real 169-paper corpus (10 clusters, 148 clustered, 21 noise)")


def test_overview_no_successful_run_zeroes_run_scoped_fields_only():
    """Mocked at the get_latest_successful_run() call site inside
    stats.py, not by touching the real ClusteringRun row -- confirms
    total_canonical_papers/embedded_papers stay real DB values while the
    run-scoped fields zero/null out safely."""
    with patch.object(stats_module, "get_latest_successful_run", return_value=None):
        result = stats_module.get_platform_overview()
    assert result["total_canonical_papers"] == 169
    assert result["embedded_papers"] == 169
    assert result["approved_clusters"] == 0
    assert result["clustered_papers"] == 0
    assert result["noise_papers"] == 0
    assert result["latest_clustering_run_id"] is None
    assert result["database_status"] == "connected"
    print("PASS: no successful run zeroes/nulls only the run-scoped fields; corpus-wide counts stay real")


if __name__ == "__main__":
    test_overview_route_returns_mocked_shape()
    test_overview_route_passes_through_no_run_nulls()
    test_overview_openapi_does_not_document_404()
    test_overview_real_values_match_known_corpus()
    test_overview_no_successful_run_zeroes_run_scoped_fields_only()
    print("\nALL TESTS PASSED")
