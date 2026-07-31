"""Live integration test: nothing mocked, real database, real completed
clustering run (084a1215-53be-4644-86e5-6f8a84b5422f, 10 approved clusters,
148 clustered + 21 noise). Exercises the whole stack end to end through
FastAPI's TestClient. Read-only: never writes to any table, never calls
Anthropic/arXiv/OpenAlex/Semantic Scholar.

Run directly:

    python3 tests/test_cluster_api_live.py
"""
from fastapi.testclient import TestClient

from research_platform.api.app import app

client = TestClient(app)

REAL_RUN_ID = "084a1215-53be-4644-86e5-6f8a84b5422f"


def test_live_list_clusters_returns_exactly_10():
    response = client.get("/api/v1/clusters")
    assert response.status_code == 200
    body = response.json()
    assert body["clustering_run_id"] == REAL_RUN_ID
    assert body["count"] == 10
    assert len(body["clusters"]) == 10
    print("PASS: GET /clusters returns exactly the 10 real approved clusters")


def test_live_cluster_paper_counts_sum_to_148():
    response = client.get("/api/v1/clusters")
    body = response.json()
    total = sum(c["paper_count"] for c in body["clusters"])
    assert total == 148
    sizes = [c["paper_count"] for c in body["clusters"]]
    assert sizes == sorted(sizes, reverse=True), "clusters must be sorted by paper_count descending"
    print(f"PASS: paper counts across all 10 clusters sum to {total} (148 expected), sorted descending")


def test_live_cluster_2_detail():
    response = client.get("/api/v1/clusters/2")
    assert response.status_code == 200
    body = response.json()
    assert body["cluster_name"] == "Visual Recognition, Segmentation, and Localization"
    assert body["paper_count"] == 25
    assert body["reviewed_by"] == "Jibin Solomon"
    assert body["reviewed_at"] is not None
    assert len(body["evidence"]) == 3
    assert "label_confidence" in body and "confidence" not in body
    print(f"PASS: GET /clusters/2 returns the correct approved label ({body['cluster_name']!r})")


def test_live_cluster_2_papers_returns_25():
    response = client.get("/api/v1/clusters/2/papers", params={"limit": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["cluster_id"] == 2
    assert body["total"] == 25
    assert len(body["papers"]) == 25
    probs = [p["membership_probability"] for p in body["papers"]]
    assert probs == sorted(probs, reverse=True), "papers must be ordered by membership_probability descending"
    assert all(p["is_noise"] is False for p in body["papers"])
    print("PASS: GET /clusters/2/papers returns 25 papers, correctly ordered by membership_probability descending")


def test_live_cluster_2_pagination():
    page1 = client.get("/api/v1/clusters/2/papers", params={"limit": 10, "offset": 0}).json()
    page2 = client.get("/api/v1/clusters/2/papers", params={"limit": 10, "offset": 10}).json()
    assert len(page1["papers"]) == 10
    assert len(page2["papers"]) == 10
    ids1 = {p["paper_id"] for p in page1["papers"]}
    ids2 = {p["paper_id"] for p in page2["papers"]}
    assert ids1.isdisjoint(ids2), "pages must not overlap"
    print("PASS: pagination across cluster 2's papers produces disjoint, correctly-sized pages")


def test_live_noise_returns_21():
    response = client.get("/api/v1/clusters/noise", params={"limit": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 21
    assert len(body["papers"]) == 21
    for p in body["papers"]:
        assert p["is_noise"] is True
        assert p["membership_probability"] == 0.0
    print("PASS: GET /clusters/noise returns exactly 21 papers, all is_noise=True with membership_probability=0.0")


def test_live_noise_zero_match_category_returns_200_empty_list():
    """A real, valid filter (a category code that matches no real papers)
    against the real 21 noise papers -- confirms this is genuinely a
    200-empty-list outcome in the live DB, not just a mocked assumption."""
    response = client.get("/api/v1/clusters/noise", params={"category": "zz.NONEXISTENT"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["papers"] == []
    print("PASS: a real category filter matching zero noise papers returns 200 with an empty list")


def test_live_noise_invalid_limit_returns_422():
    response = client.get("/api/v1/clusters/noise", params={"limit": 0})
    assert response.status_code == 422
    print("PASS: GET /clusters/noise rejects limit=0 with 422 through the full stack")


def test_live_noise_does_not_document_404():
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/api/v1/clusters/noise"]["get"]["responses"]
    assert "404" not in responses
    print("PASS: /clusters/noise does not document a 404 response")


def test_live_noise_papers_have_no_cluster_id_in_db():
    """cluster_id isn't part of the API response schema (noise papers have
    none), so this checks the underlying invariant directly against the DB
    rather than the HTTP response."""
    from sqlalchemy import text
    from research_platform.db.session import SessionLocal

    session = SessionLocal()
    rows = session.execute(text(
        "SELECT cluster_id FROM paper_cluster_assignments "
        "WHERE clustering_run_id = :rid AND is_noise = true"
    ), {"rid": REAL_RUN_ID}).fetchall()
    session.close()
    assert len(rows) == 21
    assert all(r[0] is None for r in rows)
    print("PASS: all 21 noise assignment rows have cluster_id = NULL in the database")


def test_live_nonexistent_cluster_returns_404():
    response = client.get("/api/v1/clusters/999")
    assert response.status_code == 404
    print("PASS: a real but nonexistent cluster_id returns 404 through the full stack")


def test_live_nonexistent_cluster_papers_returns_404():
    """Same real-data check as above, but for the sibling /papers endpoint
    -- previously only exercised via mocking, never against the real DB
    through the full HTTP stack."""
    response = client.get("/api/v1/clusters/999/papers")
    assert response.status_code == 404
    print("PASS: a real but nonexistent cluster_id's papers endpoint returns 404 through the full stack")


def test_no_database_writes_occurred():
    from sqlalchemy import text
    from research_platform.db.session import SessionLocal

    session = SessionLocal()

    def scalar(sql):
        return session.execute(text(sql)).scalar()

    assert scalar("SELECT COUNT(*) FROM papers") == 169
    assert scalar("SELECT COUNT(*) FROM paper_embeddings") == 169
    assert scalar("SELECT COUNT(*) FROM paper_embeddings WHERE embedding_status='SUCCEEDED'") == 169
    assert scalar("SELECT COUNT(*) FROM clustering_runs") == 1
    assert scalar("SELECT COUNT(*) FROM paper_cluster_assignments") == 169
    assert scalar("SELECT COUNT(*) FROM cluster_labels") == 10
    assert scalar("SELECT COUNT(*) FROM cluster_labels WHERE review_status='APPROVED'") == 10
    assert scalar("SELECT COUNT(*) FROM paper_enrichment_matches WHERE source='openalex'") == 169
    assert scalar("SELECT COUNT(*) FROM paper_enrichment_matches WHERE source='semantic_scholar'") == 67
    assert scalar("SELECT COUNT(*) FROM paper_references") == 5116
    assert scalar("SELECT COUNT(*) FROM paper_metric_snapshots") == 169
    assert scalar("SELECT COUNT(*) FROM enrichment_queue") == 67
    session.close()
    print("PASS: all live requests above left every table's counts exactly unchanged")


if __name__ == "__main__":
    test_live_list_clusters_returns_exactly_10()
    test_live_cluster_paper_counts_sum_to_148()
    test_live_cluster_2_detail()
    test_live_cluster_2_papers_returns_25()
    test_live_cluster_2_pagination()
    test_live_noise_returns_21()
    test_live_noise_papers_have_no_cluster_id_in_db()
    test_live_noise_zero_match_category_returns_200_empty_list()
    test_live_noise_invalid_limit_returns_422()
    test_live_noise_does_not_document_404()
    test_live_nonexistent_cluster_returns_404()
    test_live_nonexistent_cluster_papers_returns_404()
    test_no_database_writes_occurred()
    print("\nALL LIVE TESTS PASSED")
