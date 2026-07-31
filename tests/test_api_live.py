"""Live integration test: nothing mocked, real embedding model, real
pgvector query, real 169-paper corpus, through the full HTTP layer
(FastAPI TestClient -> routes/papers.py -> search_papers()/similar_papers()
-> real DB). This is the only test that exercises the whole stack end to
end, catching integration-boundary bugs (param name mismatches, schema
field drift against the real dict shape) the mocked tests can't see by
construction. Read-only: never writes to any table.

Requires the local dev database to be running and the pinned embedding
model available (already downloaded from earlier work). Run directly:

    python3 tests/test_api_live.py
"""
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from research_platform.api.app import app
from research_platform.db.models import Paper
from research_platform.db.session import SessionLocal

client = TestClient(app)


def test_live_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}
    print("PASS: /health is genuinely healthy against the real running database")


def test_live_search():
    response = client.get("/api/v1/papers/search", params={"query": "graph neural networks", "top_k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 5
    assert len(body["results"]) == 5

    scores = [r["similarity_score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True), "results must be ordered highest-to-lowest similarity"

    for r in body["results"]:
        assert r["title"]
        assert r["abstract"]
        assert r["arxiv_id"]
        assert isinstance(r["authors"], list)

    print(f"PASS: live search returned 5 real, correctly-ranked results; top hit: {body['results'][0]['title']!r}")


def test_live_paper_detail():
    session = SessionLocal()
    known = session.execute(select(Paper).where(Paper.arxiv_id == "1601.01280")).scalar_one()
    known_id, known_title = str(known.id), known.title
    session.close()

    response = client.get(f"/api/v1/papers/{known_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["paper_id"] == known_id
    assert body["title"] == known_title
    assert body["arxiv_id"] == "1601.01280"
    assert isinstance(body["authors"], list) and body["authors"]
    assert body["embedding_available"] is True
    print(f"PASS: live paper detail for {known_title!r} returns 200 with embedding_available=True")


def test_live_paper_detail_not_found():
    response = client.get("/api/v1/papers/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    print("PASS: a real but nonexistent paper_id on /papers/{paper_id} returns 404 through the full stack")


def test_live_similar():
    session = SessionLocal()
    known = session.execute(select(Paper).where(Paper.arxiv_id == "1601.01280")).scalar_one()
    known_id, known_title = str(known.id), known.title
    session.close()

    response = client.get(f"/api/v1/papers/{known_id}/similar", params={"top_k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["source_paper_id"] == known_id
    assert body["count"] == 5

    arxiv_ids = [r["arxiv_id"] for r in body["results"]]
    assert "1601.01280" not in arxiv_ids, "the selected paper must never recommend itself, end to end through HTTP"

    scores = [r["similarity_score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)

    print(f"PASS: live similar-papers for {known_title!r} returned 5 results, self excluded, correctly ranked")


def test_live_similar_with_filters_no_matches_returns_200_empty_list():
    """A real, valid filter (a category code matching no real papers)
    against a real embedded paper -- confirms zero matches is genuinely a
    200-empty-list outcome in the live DB, not just a mocked assumption.
    Mirrors test_live_noise_zero_match_category_returns_200_empty_list."""
    session = SessionLocal()
    known = session.execute(select(Paper).where(Paper.arxiv_id == "1601.01280")).scalar_one()
    known_id = str(known.id)
    session.close()

    response = client.get(f"/api/v1/papers/{known_id}/similar", params={"category": "zz.NONEXISTENT"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["results"] == []
    print("PASS: a real category filter matching zero candidates returns 200 with an empty list, through the full stack")


def test_live_paper_not_found():
    response = client.get("/api/v1/papers/00000000-0000-0000-0000-000000000000/similar")
    assert response.status_code == 404
    print("PASS: a real but nonexistent UUID returns 404 through the full stack")


def test_no_database_writes_occurred():
    session = SessionLocal()

    def scalar(sql):
        return session.execute(text(sql)).scalar()

    assert scalar("SELECT COUNT(*) FROM papers") == 169
    assert scalar("SELECT COUNT(*) FROM paper_embeddings") == 169
    assert scalar("SELECT COUNT(*) FROM paper_embeddings WHERE embedding_status='SUCCEEDED'") == 169
    assert scalar("SELECT COUNT(*) FROM paper_enrichment_matches WHERE source='openalex'") == 169
    assert scalar("SELECT COUNT(*) FROM paper_enrichment_matches WHERE source='semantic_scholar'") == 67
    assert scalar("SELECT COUNT(*) FROM paper_references") == 5116
    assert scalar("SELECT COUNT(*) FROM paper_metric_snapshots") == 169
    assert scalar("SELECT COUNT(*) FROM enrichment_queue") == 67
    dups = session.execute(text(
        "SELECT paper_id, embedding_model, model_version, COUNT(*) c FROM paper_embeddings "
        "GROUP BY paper_id, embedding_model, model_version HAVING COUNT(*) > 1"
    )).fetchall()
    assert dups == []
    session.close()
    print("PASS: all live requests above left every table's counts exactly unchanged, zero duplicates")


if __name__ == "__main__":
    test_live_health()
    test_live_search()
    test_live_paper_detail()
    test_live_paper_detail_not_found()
    test_live_similar()
    test_live_similar_with_filters_no_matches_returns_200_empty_list()
    test_live_paper_not_found()
    test_no_database_writes_occurred()
    print("\nALL LIVE TESTS PASSED")
