"""Validates the trend API route layer (GET /api/v1/trends/*) end to end
via FastAPI's TestClient against the real, persisted official trend run:
response shapes, status-code mapping (200/404/422/503), the three
documented real classifications (Cluster 0/4/5), null growth_rate
serialization, OpenAPI schema accuracy, that no current-trend wording ever
appears, that the historical-cohort warning is present, and that hitting
every endpoint several times never recalculates anything or writes a row
anywhere in the database.

No pytest dependency. Requires the local dev database running with the
official trend run persisted. Never writes to any table. Run directly:

    python3 tests/test_trend_api_routes.py
"""
import json
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from research_platform.api.app import app
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
from research_platform.trends import api_queries

client = TestClient(app)

ALL_TABLES = [
    Paper, PaperEmbedding, ClusteringRun, ClusterLabel, PaperClusterAssignment, PaperMetricSnapshot,
    TrendAnalysisRun, TrendEntitySnapshot, TrendScore, TrendEvidencePaper,
]

BANNED_PHRASES = ("trending now", "latest ai trends", "current momentum", "year-over-year", "continuous historical trend")


def _all_table_counts() -> dict:
    session = SessionLocal()
    try:
        return {model.__tablename__: session.execute(select(func.count()).select_from(model)).scalar_one() for model in ALL_TABLES}
    finally:
        session.close()


def test_overview_route_200_shape_and_wording():
    r = client.get("/api/v1/trends/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["trend_context"]["effective_trend_mode"] == "historical"
    assert body["trend_context"]["trend_mode_label"] == "Historical Cohort Comparison"
    assert "Historical Cohort Comparison" in body["message"]
    assert "Comparison cohort" in body["message"]
    assert "Recent cohort" in body["message"]
    assert body["cluster_summary"]["total_entities"] == 10
    assert body["category_summary"]["total_entities"] == 30
    print("PASS: GET /trends/overview returns 200 with the correct shape and historical-cohort wording")


def test_overview_route_503_when_no_successful_run():
    with patch.object(api_queries, "resolve_trend_run", side_effect=api_queries.TrendResultsUnavailableError("no successful trend analysis run is available yet")):
        r = client.get("/api/v1/trends/overview")
    assert r.status_code == 503
    assert "detail" in r.json()
    print("PASS: GET /trends/overview returns 503 (not 404) when no successful run exists")


def test_overview_route_404_unknown_explicit_run_id():
    r = client.get(f"/api/v1/trends/overview?run_id={uuid.uuid4()}")
    assert r.status_code == 404
    print("PASS: GET /trends/overview?run_id=<unknown> returns 404")


def test_clusters_route_pagination_and_filtering():
    r = client.get("/api/v1/trends/clusters?limit=3&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 10
    assert len(body["results"]) == 3
    assert body["limit"] == 3 and body["offset"] == 0

    r = client.get("/api/v1/trends/clusters?classification=Cooling&limit=100")
    body = r.json()
    assert body["total"] == 8
    assert all(item["score"]["trend_classification"] == "Cooling" for item in body["results"])
    print("PASS: GET /trends/clusters supports pagination and classification filtering")


def test_categories_route():
    r = client.get("/api/v1/trends/categories?limit=100")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 30
    print("PASS: GET /trends/categories returns all 30 real categories")


def test_documented_cluster_classifications():
    expected = {"0": "Emerging", "4": "Cooling", "5": "Stable"}
    for cluster_id, classification in expected.items():
        r = client.get(f"/api/v1/trends/cluster/{cluster_id}")
        assert r.status_code == 200
        body = r.json()
        actual = body["result"]["score"]["trend_classification"]
        assert actual == classification, f"cluster {cluster_id}: expected {classification}, got {actual}"
    print("PASS: GET /trends/cluster/{0,4,5} return exactly Emerging/Cooling/Stable as documented")


def test_entity_detail_evidence_split_by_role():
    r = client.get("/api/v1/trends/cluster/5")
    body = r.json()
    assert len(body["recent_period_evidence"]) > 0
    assert len(body["comparison_period_evidence"]) > 0
    assert all(item["role"] == "recent_period" for item in body["recent_period_evidence"])
    assert all(item["role"] == "comparison_period" for item in body["comparison_period_evidence"])
    print("PASS: GET /trends/cluster/5 splits evidence into recent_period_evidence and comparison_period_evidence correctly")


def test_invalid_entity_type_returns_422():
    r = client.get("/api/v1/trends/paper/123")
    assert r.status_code == 422
    print("PASS: an unsupported entity_type ('paper') returns 422 via FastAPI's own Literal validation")


def test_missing_entity_returns_404():
    r = client.get("/api/v1/trends/cluster/999")
    assert r.status_code == 404
    print("PASS: a nonexistent cluster_id returns 404")


def test_emerging_cooling_stable_routes():
    r = client.get("/api/v1/trends/emerging")
    body = r.json()
    assert body["total"] >= 1
    assert all(item["score"]["trend_classification"] == "Emerging" for item in body["results"])

    r = client.get("/api/v1/trends/cooling?entity_type=cluster")
    body = r.json()
    assert body["total"] == 8
    assert all(item["entity_type"] == "cluster" for item in body["results"])

    r = client.get("/api/v1/trends/stable")
    body = r.json()
    assert any(item["entity_id"] == "5" and item["entity_type"] == "cluster" for item in body["results"])
    print("PASS: /trends/emerging, /trends/cooling (entity_type-filtered), and /trends/stable all behave correctly")


def test_null_growth_rate_serializes_as_json_null():
    r = client.get("/api/v1/trends/cluster/0")
    assert r.json()["result"]["metrics"]["growth_rate"] is None
    raw = r.text
    parsed = json.loads(raw)
    assert parsed["result"]["metrics"]["growth_rate"] is None
    assert '"growth_rate":null' in raw.replace(" ", "") or '"growth_rate": null' in raw
    print("PASS: Cluster 0's undefined growth_rate serializes as JSON null, never 0 or omitted")


def test_no_current_trend_wording_anywhere():
    responses = [
        client.get("/api/v1/trends/overview"),
        client.get("/api/v1/trends/clusters?limit=100"),
        client.get("/api/v1/trends/categories?limit=100"),
        client.get("/api/v1/trends/cluster/5"),
        client.get("/api/v1/trends/emerging"),
        client.get("/api/v1/trends/cooling"),
        client.get("/api/v1/trends/stable"),
    ]
    for r in responses:
        lowered = r.text.lower()
        for banned in BANNED_PHRASES:
            assert banned not in lowered, f'banned phrase "{banned}" found in {r.request.url}'
    print("PASS: none of the seven trend endpoints ever emit current-trend/continuous-trend wording")


def test_openapi_schema_accuracy():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    expected_paths = {
        "/api/v1/trends/overview", "/api/v1/trends/clusters", "/api/v1/trends/categories",
        "/api/v1/trends/emerging", "/api/v1/trends/cooling", "/api/v1/trends/stable",
        "/api/v1/trends/{entity_type}/{entity_id}",
    }
    assert expected_paths <= set(schema["paths"].keys())

    expected_schemas = {
        "TrendContext", "TrendMetrics", "TrendScore", "TrendEvidencePaper", "TrendEvidenceSummary",
        "TrendResult", "EntityTypeSummary", "TrendOverviewResponse", "TrendListResponse", "TrendDetailResponse",
    }
    assert expected_schemas <= set(schema["components"]["schemas"].keys())

    overview_responses = schema["paths"]["/api/v1/trends/overview"]["get"]["responses"]
    assert "200" in overview_responses
    assert "503" in overview_responses

    detail_responses = schema["paths"]["/api/v1/trends/{entity_type}/{entity_id}"]["get"]["responses"]
    assert "404" in detail_responses
    assert "422" in detail_responses, "FastAPI auto-documents 422 for any route with request validation"
    print("PASS: /openapi.json includes all trend paths, all trend schemas, and the documented 404/422/503 responses")


def test_read_only_no_writes_across_repeated_requests():
    before = _all_table_counts()
    for _ in range(3):
        client.get("/api/v1/trends/overview")
        client.get("/api/v1/trends/clusters?limit=100")
        client.get("/api/v1/trends/categories?limit=100")
        client.get("/api/v1/trends/cluster/5")
        client.get("/api/v1/trends/emerging")
        client.get("/api/v1/trends/cooling")
        client.get("/api/v1/trends/stable")
        client.get("/api/v1/trends/cluster/999")  # 404 path too
    after = _all_table_counts()
    assert before == after, f"a trend GET endpoint modified table row counts: before={before} after={after}"
    print("PASS: repeatedly hitting every trend endpoint (including error paths) never changes any table's row count -- fully read-only, no recalculation persisted")


if __name__ == "__main__":
    test_overview_route_200_shape_and_wording()
    test_overview_route_503_when_no_successful_run()
    test_overview_route_404_unknown_explicit_run_id()
    test_clusters_route_pagination_and_filtering()
    test_categories_route()
    test_documented_cluster_classifications()
    test_entity_detail_evidence_split_by_role()
    test_invalid_entity_type_returns_422()
    test_missing_entity_returns_404()
    test_emerging_cooling_stable_routes()
    test_null_growth_rate_serializes_as_json_null()
    test_no_current_trend_wording_anywhere()
    test_openapi_schema_accuracy()
    test_read_only_no_writes_across_repeated_requests()
    print("\nALL TESTS PASSED")
