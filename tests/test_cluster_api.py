"""Validates the cluster-API route layer: status-code mapping, JSON
response shape, route ordering (/noise vs /{cluster_id}), pagination/
filter forwarding, FastAPI-level 422s never reaching the query layer, and
that read-only query functions are called exactly once per request. Uses
FastAPI's TestClient (in-process, no real server/socket).

Design note on "mocked": most tests here mock the query functions in
clustering/queries.py (imported into routes/clusters.py's namespace) --
there is no model/LLM call anywhere in this feature, so mocking exists
purely to test routing/schema/status-code wiring in isolation, matching
test_api.py's pattern for papers/search. One test (unapproved-label
exclusion) instead exercises queries.py for real against synthetic DB rows,
since that behavior IS the SQL filter being tested, not something a mock
could verify. The live, fully-unmocked integration tests against the real
clustering run live in tests/test_cluster_api_live.py.

No pytest dependency. Requires the local dev database to be running. Does
NOT call Anthropic, arXiv, OpenAlex, or Semantic Scholar, and NEVER
modifies clustering assignments, embeddings, or papers. Run directly:

    python3 tests/test_cluster_api.py
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete

from research_platform.api.app import app
from research_platform.api.routes import clusters as clusters_module
from research_platform.clustering.queries import ClusterNotFoundError
from research_platform.db.models import Category, ClusterLabel, ClusteringRun, Paper, PaperClusterAssignment
from research_platform.db.session import SessionLocal

client = TestClient(app)


def _fake_cluster_summary(cluster_id=2, paper_count=25):
    return {
        "cluster_id": cluster_id,
        "cluster_name": "Fake Cluster",
        "short_description": "A fake cluster for route testing.",
        "paper_count": paper_count,
        "label_confidence": 0.8,
        "top_keywords": ["fake", "test"],
        "dominant_category": "cs.LG",
        "average_membership_probability": 0.9,
        "clustering_run_id": str(uuid.uuid4()),
    }


def _fake_cluster_detail(cluster_id=2):
    return {
        "cluster_id": cluster_id,
        "cluster_name": "Fake Cluster",
        "short_description": "A fake cluster for route testing.",
        "paper_count": 25,
        "label_confidence": 0.8,
        "keywords": ["fake", "test"],
        "evidence": [{"paper_id": str(uuid.uuid4()), "reason": "fake reason"}],
        "category_distribution": [{"category": "cs.LG", "count": 20, "percent": 80.0}],
        "average_membership_probability": 0.9,
        "representative_papers": [{"paper_id": str(uuid.uuid4()), "arxiv_id": "1601.00001", "title": "Fake Paper"}],
        "clustering_run_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc),
        "reviewed_by": "Jibin Solomon",
        "reviewed_at": datetime.now(timezone.utc),
    }


def _fake_paper(membership_probability=0.9, is_noise=False):
    return {
        "paper_id": str(uuid.uuid4()),
        "arxiv_id": "1601.00001",
        "title": "Fake Paper",
        "abstract": "A fake abstract.",
        "authors": ["Alice First"],
        "primary_category": "cs.LG",
        "publication_date": datetime(2016, 1, 5, tzinfo=timezone.utc),
        "membership_probability": membership_probability,
        "is_noise": is_noise,
    }


# --- GET /clusters -----------------------------------------------------------

def test_list_clusters_success():
    fake_result = {
        "clustering_run_id": str(uuid.uuid4()),
        "count": 2,
        "clusters": [_fake_cluster_summary(2, 25), _fake_cluster_summary(9, 25)],
    }
    with patch.object(clusters_module, "list_approved_clusters", return_value=fake_result) as fake_fn:
        response = client.get("/api/v1/clusters")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert len(body["clusters"]) == 2
    assert fake_fn.call_count == 1
    print("PASS: GET /clusters returns 200 with the expected shape, query function called exactly once")


def test_list_clusters_preserves_order():
    fake_result = {
        "clustering_run_id": str(uuid.uuid4()),
        "count": 3,
        "clusters": [_fake_cluster_summary(2, 25), _fake_cluster_summary(5, 22), _fake_cluster_summary(1, 19)],
    }
    with patch.object(clusters_module, "list_approved_clusters", return_value=fake_result):
        response = client.get("/api/v1/clusters")
    sizes = [c["paper_count"] for c in response.json()["clusters"]]
    assert sizes == [25, 22, 19], "the route must not re-order what the query function returns"
    print("PASS: route preserves the query function's paper_count-descending order")


def test_list_clusters_no_successful_run_returns_200_empty():
    """list_approved_clusters() never raises -- when get_latest_successful_run()
    finds no SUCCEEDED run at all, it returns clustering_run_id=None with an
    empty clusters list, not a 404. Only reachable via mocking: deleting every
    real ClusteringRun row to exercise this for real would be destructive."""
    fake_result = {"clustering_run_id": None, "count": 0, "clusters": []}
    with patch.object(clusters_module, "list_approved_clusters", return_value=fake_result) as fake_fn:
        response = client.get("/api/v1/clusters")
    assert response.status_code == 200
    body = response.json()
    assert body == {"clustering_run_id": None, "count": 0, "clusters": []}
    assert fake_fn.call_count == 1
    print("PASS: no successful clustering run returns 200 with clustering_run_id=None and an empty clusters list")


# --- GET /clusters/{id} -------------------------------------------------------

def test_get_cluster_success():
    with patch.object(clusters_module, "get_cluster_detail", return_value=_fake_cluster_detail(2)) as fake_fn:
        response = client.get("/api/v1/clusters/2")
    assert response.status_code == 200
    body = response.json()
    assert body["cluster_id"] == 2
    assert body["reviewed_by"] == "Jibin Solomon"
    assert fake_fn.call_count == 1
    fake_fn.assert_called_with(2)
    print("PASS: GET /clusters/{id} returns 200 with full detail, query function called exactly once")


def test_get_cluster_not_found_returns_404():
    with patch.object(clusters_module, "get_cluster_detail", side_effect=ClusterNotFoundError("no such cluster")):
        response = client.get("/api/v1/clusters/999")
    assert response.status_code == 404
    print("PASS: a nonexistent cluster returns 404 via ClusterNotFoundError")


def test_invalid_cluster_id_type_returns_422():
    with patch.object(clusters_module, "get_cluster_detail") as fake_fn:
        response = client.get("/api/v1/clusters/not-an-int")
    assert response.status_code == 422
    assert fake_fn.call_count == 0
    print("PASS: a non-integer cluster_id is rejected by FastAPI (422), never reaches the query function")


def test_papers_invalid_cluster_id_type_returns_422():
    """Same check as above, but for the sibling /papers endpoint -- was
    previously untested even though it shares the same path-parameter
    declaration (cluster_id: int)."""
    with patch.object(clusters_module, "get_cluster_papers") as fake_fn:
        response = client.get("/api/v1/clusters/not-an-int/papers")
    assert response.status_code == 422
    assert fake_fn.call_count == 0
    print("PASS: a non-integer cluster_id on /clusters/{id}/papers is rejected by FastAPI (422), never reaches the query function")


# --- GET /clusters/{id}/papers -------------------------------------------------

def test_cluster_papers_pagination():
    fake_result = {"cluster_id": 2, "total": 25, "limit": 5, "offset": 10, "papers": [_fake_paper()]}
    with patch.object(clusters_module, "get_cluster_papers", return_value=fake_result) as fake_fn:
        response = client.get("/api/v1/clusters/2/papers", params={"limit": 5, "offset": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 25 and body["limit"] == 5 and body["offset"] == 10
    assert fake_fn.call_count == 1
    _, kwargs = fake_fn.call_args
    assert kwargs["limit"] == 5 and kwargs["offset"] == 10
    print("PASS: limit/offset are parsed and forwarded correctly to get_cluster_papers()")


def test_cluster_papers_category_filter():
    fake_result = {"cluster_id": 2, "total": 0, "limit": 20, "offset": 0, "papers": []}
    with patch.object(clusters_module, "get_cluster_papers", return_value=fake_result) as fake_fn:
        client.get("/api/v1/clusters/2/papers", params={"category": "cs.CV"})
    _, kwargs = fake_fn.call_args
    assert kwargs["category"] == "cs.CV"
    print("PASS: category filter forwarded to get_cluster_papers()")


def test_cluster_papers_min_membership_filter():
    fake_result = {"cluster_id": 2, "total": 0, "limit": 20, "offset": 0, "papers": []}
    with patch.object(clusters_module, "get_cluster_papers", return_value=fake_result) as fake_fn:
        client.get("/api/v1/clusters/2/papers", params={"min_membership_probability": 0.7})
    _, kwargs = fake_fn.call_args
    assert kwargs["min_membership_probability"] == 0.7
    print("PASS: min_membership_probability filter forwarded to get_cluster_papers()")


def test_cluster_papers_invalid_limit_returns_422():
    with patch.object(clusters_module, "get_cluster_papers") as fake_fn:
        for bad_limit in (0, -1, 101):
            response = client.get("/api/v1/clusters/2/papers", params={"limit": bad_limit})
            assert response.status_code == 422, f"limit={bad_limit} should be 422"
    assert fake_fn.call_count == 0
    print("PASS: limit outside [1, 100] is rejected before the route runs (422)")


def test_cluster_papers_invalid_offset_returns_422():
    with patch.object(clusters_module, "get_cluster_papers") as fake_fn:
        response = client.get("/api/v1/clusters/2/papers", params={"offset": -1})
    assert response.status_code == 422
    assert fake_fn.call_count == 0
    print("PASS: negative offset is rejected before the route runs (422)")


def test_cluster_papers_invalid_min_membership_returns_422():
    with patch.object(clusters_module, "get_cluster_papers") as fake_fn:
        for bad in (-0.1, 1.1):
            response = client.get("/api/v1/clusters/2/papers", params={"min_membership_probability": bad})
            assert response.status_code == 422, f"min_membership_probability={bad} should be 422"
    assert fake_fn.call_count == 0
    print("PASS: min_membership_probability outside [0, 1] is rejected before the route runs (422)")


# --- GET /clusters/noise -------------------------------------------------------

def test_noise_papers_returns_only_noise():
    fake_result = {
        "clustering_run_id": str(uuid.uuid4()),
        "total": 21,
        "limit": 20,
        "offset": 0,
        "papers": [_fake_paper(membership_probability=0.0, is_noise=True) for _ in range(20)],
    }
    with patch.object(clusters_module, "get_noise_papers", return_value=fake_result) as fake_fn:
        response = client.get("/api/v1/clusters/noise")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 21
    assert all(p["is_noise"] is True and p["membership_probability"] == 0.0 for p in body["papers"])
    assert fake_fn.call_count == 1
    print("PASS: GET /clusters/noise returns only is_noise=True papers with membership_probability=0.0")


def test_noise_route_not_shadowed_by_cluster_id_route():
    with patch.object(clusters_module, "get_noise_papers", return_value={
        "clustering_run_id": None, "total": 0, "limit": 20, "offset": 0, "papers": [],
    }) as fake_noise, patch.object(clusters_module, "get_cluster_detail") as fake_detail:
        response = client.get("/api/v1/clusters/noise")
    assert response.status_code == 200
    assert fake_noise.call_count == 1
    assert fake_detail.call_count == 0, "/clusters/noise must never be routed to the /{cluster_id} handler"
    print("PASS: /clusters/noise is matched by its own route, not swallowed by /clusters/{cluster_id}")


def test_noise_papers_zero_matches_returns_200_empty_list():
    """get_noise_papers() has no runtime path that raises ClusterNotFoundError
    -- a valid filter matching nothing is just an ordinary empty result,
    not an error. This is the concrete behavior behind not documenting 404."""
    fake_result = {
        "clustering_run_id": str(uuid.uuid4()),
        "total": 0,
        "limit": 20,
        "offset": 0,
        "papers": [],
    }
    with patch.object(clusters_module, "get_noise_papers", return_value=fake_result) as fake_fn:
        response = client.get("/api/v1/clusters/noise", params={"category": "cs.NONEXISTENT"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["papers"] == []
    assert fake_fn.call_count == 1
    print("PASS: a valid filter matching zero noise papers returns 200 with an empty list, not an error")


def test_noise_papers_invalid_limit_returns_422():
    with patch.object(clusters_module, "get_noise_papers") as fake_fn:
        for bad_limit in (0, -1, 101):
            response = client.get("/api/v1/clusters/noise", params={"limit": bad_limit})
            assert response.status_code == 422, f"limit={bad_limit} should be 422"
    assert fake_fn.call_count == 0
    print("PASS: /clusters/noise rejects out-of-range limit with 422, never reaches get_noise_papers()")


def test_noise_papers_invalid_offset_returns_422():
    with patch.object(clusters_module, "get_noise_papers") as fake_fn:
        response = client.get("/api/v1/clusters/noise", params={"offset": -1})
    assert response.status_code == 422
    assert fake_fn.call_count == 0
    print("PASS: /clusters/noise rejects negative offset with 422, never reaches get_noise_papers()")


# --- response shape ------------------------------------------------------------

def test_cluster_list_response_shape():
    fake_result = {"clustering_run_id": str(uuid.uuid4()), "count": 1, "clusters": [_fake_cluster_summary()]}
    with patch.object(clusters_module, "list_approved_clusters", return_value=fake_result):
        response = client.get("/api/v1/clusters")
    body = response.json()
    assert set(body.keys()) == {"clustering_run_id", "count", "clusters"}
    assert set(body["clusters"][0].keys()) == {
        "cluster_id", "cluster_name", "short_description", "paper_count", "label_confidence",
        "top_keywords", "dominant_category", "average_membership_probability", "clustering_run_id",
    }
    print("PASS: ClusterListResponse/ClusterSummary have exactly the expected fields")


def test_cluster_detail_response_shape():
    with patch.object(clusters_module, "get_cluster_detail", return_value=_fake_cluster_detail()):
        response = client.get("/api/v1/clusters/2")
    body = response.json()
    assert set(body.keys()) == {
        "cluster_id", "cluster_name", "short_description", "paper_count", "label_confidence",
        "keywords", "evidence", "category_distribution", "average_membership_probability",
        "representative_papers", "clustering_run_id", "created_at", "reviewed_by", "reviewed_at",
    }
    print("PASS: ClusterDetail has exactly the expected fields (label_confidence, never 'confidence')")


def test_cluster_papers_response_shape():
    fake_result = {"cluster_id": 2, "total": 1, "limit": 20, "offset": 0, "papers": [_fake_paper()]}
    with patch.object(clusters_module, "get_cluster_papers", return_value=fake_result):
        response = client.get("/api/v1/clusters/2/papers")
    body = response.json()
    assert set(body.keys()) == {"cluster_id", "total", "limit", "offset", "papers"}
    assert set(body["papers"][0].keys()) == {
        "paper_id", "arxiv_id", "title", "abstract", "authors",
        "primary_category", "publication_date", "membership_probability", "is_noise",
    }
    print("PASS: ClusterPapersResponse matches the exact shape specified, membership_probability never called 'confidence'")


# --- unapproved label exclusion (real DB, synthetic rows, no mocking) ----------

def test_unapproved_label_excluded_from_list_and_detail():
    """This behavior IS the SQL filter (review_status='APPROVED') -- there's
    nothing to mock, it's a pure read. A synthetic run with a LATER
    completed_at than the real run temporarily becomes "latest", exercising
    get_latest_successful_run() too; cleaned up immediately after."""
    session = SessionLocal()
    category = Category(taxonomy_source="zztest-cluster-api", code=f"zztest.capi.{uuid.uuid4().hex[:8]}", display_name="Test")
    session.add(category)
    session.flush()
    paper = Paper(
        arxiv_id=f"zztest-cluster-api.{uuid.uuid4().hex[:8]}", doi=None, normalized_title="t", title="T",
        abstract="A", primary_category_id=category.id, first_observed_source="test",
        first_observed_at=datetime.now(timezone.utc), current_version_number=1, is_canonical=True,
    )
    session.add(paper)
    session.flush()

    run = ClusteringRun(
        embedding_model="test", embedding_model_version="test", algorithm_parameters={}, random_seed=1,
        paper_count=1, cluster_count=1, noise_count=0, status="SUCCEEDED",
        created_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()

    session.add(PaperClusterAssignment(
        clustering_run_id=run.id, paper_id=paper.id, cluster_id=0, membership_probability=0.9,
        is_noise=False, umap_coordinates=[0.0] * 5, created_at=datetime.now(timezone.utc),
    ))
    label = ClusterLabel(
        clustering_run_id=run.id, cluster_id=0, cluster_name="Unapproved Test Cluster",
        short_description="Should never appear.", keywords=["x"], confidence=0.5, evidence=[],
        provider="anthropic", model="test-model", model_version="test-model", prompt_version="v1",
        input_hash="x", temperature=0.0, generation_status="SUCCEEDED", review_status="PENDING_REVIEW",
    )
    session.add(label)
    session.commit()

    try:
        from research_platform.clustering.queries import get_cluster_detail, get_cluster_papers, list_approved_clusters

        result = list_approved_clusters()
        assert result["clustering_run_id"] == str(run.id), "the synthetic run should be picked up as latest"
        assert result["clusters"] == [], "a PENDING_REVIEW label must never appear in the approved list"

        try:
            get_cluster_detail(0)
            raised = False
        except ClusterNotFoundError:
            raised = True
        assert raised, "get_cluster_detail must raise ClusterNotFoundError for an unapproved label"

        try:
            get_cluster_papers(0)
            raised = False
        except ClusterNotFoundError:
            raised = True
        assert raised, "get_cluster_papers must raise ClusterNotFoundError for an unapproved label too -- same rule, sibling endpoint"

        print("PASS: an unapproved (PENDING_REVIEW) label is excluded from list, detail, AND papers queries")
    finally:
        session.execute(delete(PaperClusterAssignment).where(PaperClusterAssignment.clustering_run_id == run.id))
        session.execute(delete(ClusterLabel).where(ClusterLabel.clustering_run_id == run.id))
        session.execute(delete(ClusteringRun).where(ClusteringRun.id == run.id))
        session.execute(delete(Paper).where(Paper.id == paper.id))
        session.execute(delete(Category).where(Category.id == category.id))
        session.commit()
        session.close()


def test_cluster_from_an_older_non_latest_run_returns_404():
    """Distinct from "nonexistent cluster": cluster_id=99 genuinely exists
    in the database, with a real APPROVED label -- just scoped to an OLDER
    run, not the current latest one. get_cluster_detail() must not find it,
    because it always resolves the latest SUCCEEDED run first and scopes
    the label lookup to that run_id. completed_at is set safely in the past
    (2020) so the real run remains "latest" throughout -- no interference
    with concurrent state, unlike the PENDING_REVIEW test above which
    deliberately makes its synthetic run the latest one."""
    session = SessionLocal()
    category = Category(taxonomy_source="zztest-cluster-api", code=f"zztest.capi.{uuid.uuid4().hex[:8]}", display_name="Test")
    session.add(category)
    session.flush()
    paper = Paper(
        arxiv_id=f"zztest-cluster-api.{uuid.uuid4().hex[:8]}", doi=None, normalized_title="t", title="T",
        abstract="A", primary_category_id=category.id, first_observed_source="test",
        first_observed_at=datetime.now(timezone.utc), current_version_number=1, is_canonical=True,
    )
    session.add(paper)
    session.flush()

    old_run = ClusteringRun(
        embedding_model="test", embedding_model_version="test", algorithm_parameters={}, random_seed=1,
        paper_count=1, cluster_count=1, noise_count=0, status="SUCCEEDED",
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc), completed_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    session.add(old_run)
    session.flush()

    OLD_RUN_CLUSTER_ID = 99  # guaranteed not to exist in the real latest run (which only has 0-9)
    session.add(PaperClusterAssignment(
        clustering_run_id=old_run.id, paper_id=paper.id, cluster_id=OLD_RUN_CLUSTER_ID, membership_probability=0.9,
        is_noise=False, umap_coordinates=[0.0] * 5, created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    ))
    label = ClusterLabel(
        clustering_run_id=old_run.id, cluster_id=OLD_RUN_CLUSTER_ID, cluster_name="Old Run Test Cluster",
        short_description="Genuinely approved, but in an old run.", keywords=["x"], confidence=0.9, evidence=[],
        provider="anthropic", model="test-model", model_version="test-model", prompt_version="v1",
        input_hash="x", temperature=0.0, generation_status="SUCCEEDED", review_status="APPROVED",
    )
    session.add(label)
    session.commit()

    try:
        from research_platform.clustering.queries import get_cluster_detail, get_cluster_papers, get_latest_successful_run

        latest = get_latest_successful_run(session)
        assert str(latest.id) != str(old_run.id), "the real run must still be resolved as latest, not the old synthetic one"

        try:
            get_cluster_detail(OLD_RUN_CLUSTER_ID)
            raised = False
        except ClusterNotFoundError:
            raised = True
        assert raised, (
            "a cluster that only exists in an older (non-latest) run, even with a genuinely APPROVED "
            "label, must 404 -- it is not part of the latest successful run"
        )

        try:
            get_cluster_papers(OLD_RUN_CLUSTER_ID)
            raised = False
        except ClusterNotFoundError:
            raised = True
        assert raised, "get_cluster_papers must apply the same latest-run scoping as get_cluster_detail"

        print("PASS: a cluster belonging only to an older, non-latest run returns 404 for both detail AND papers queries")
    finally:
        session.execute(delete(PaperClusterAssignment).where(PaperClusterAssignment.clustering_run_id == old_run.id))
        session.execute(delete(ClusterLabel).where(ClusterLabel.clustering_run_id == old_run.id))
        session.execute(delete(ClusteringRun).where(ClusteringRun.id == old_run.id))
        session.execute(delete(Paper).where(Paper.id == paper.id))
        session.execute(delete(Category).where(Category.id == category.id))
        session.commit()
        session.close()


# --- OpenAPI 404 metadata -------------------------------------------------

def test_openapi_documents_404_for_cluster_detail_and_papers():
    spec = client.get("/openapi.json").json()
    for path in ("/api/v1/clusters/{cluster_id}", "/api/v1/clusters/{cluster_id}/papers"):
        responses = spec["paths"][path]["get"]["responses"]
        assert "404" in responses, f"{path} must document a 404 response"
        content = responses["404"]["content"]["application/json"]["schema"]
        ref_name = content["$ref"].split("/")[-1] if "$ref" in content else None
        assert ref_name == "ErrorResponse", f"{path}'s 404 must reference the ErrorResponse schema, got {ref_name!r}"
    print("PASS: /openapi.json documents a 404 (ErrorResponse) for both /clusters/{cluster_id} and /clusters/{cluster_id}/papers")


def test_openapi_error_response_schema_matches_runtime_shape():
    spec = client.get("/openapi.json").json()
    error_schema = spec["components"]["schemas"]["ErrorResponse"]
    assert set(error_schema["properties"].keys()) == {"detail"}
    assert error_schema["properties"]["detail"]["type"] == "string"
    print("PASS: ErrorResponse schema is exactly {detail: string}, matching what the exception handlers actually return")


def test_openapi_does_not_document_404_for_list_and_noise():
    spec = client.get("/openapi.json").json()
    for path in ("/api/v1/clusters", "/api/v1/clusters/noise"):
        responses = spec["paths"][path]["get"]["responses"]
        assert "404" not in responses, f"{path} must NOT document a 404 response"
    print("PASS: /clusters and /clusters/noise do not document a 404 response, as instructed")


def test_runtime_404_behavior_unchanged_after_metadata_change():
    """The exact same runtime checks from test_get_cluster_not_found_returns_404
    and the live 404 test, rerun here to confirm adding response metadata
    changed nothing about actual exception-handling behavior."""
    with patch.object(clusters_module, "get_cluster_detail", side_effect=ClusterNotFoundError("no such cluster")):
        response = client.get("/api/v1/clusters/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "no such cluster"}

    with patch.object(clusters_module, "get_cluster_papers", side_effect=ClusterNotFoundError("no such cluster")):
        response2 = client.get("/api/v1/clusters/999/papers")
    assert response2.status_code == 404
    assert response2.json() == {"detail": "no such cluster"}
    print("PASS: runtime 404 status code and body are byte-identical to before the metadata change, for both routes")


if __name__ == "__main__":
    test_list_clusters_success()
    test_list_clusters_preserves_order()
    test_list_clusters_no_successful_run_returns_200_empty()
    test_get_cluster_success()
    test_get_cluster_not_found_returns_404()
    test_invalid_cluster_id_type_returns_422()
    test_papers_invalid_cluster_id_type_returns_422()
    test_cluster_papers_pagination()
    test_cluster_papers_category_filter()
    test_cluster_papers_min_membership_filter()
    test_cluster_papers_invalid_limit_returns_422()
    test_cluster_papers_invalid_offset_returns_422()
    test_cluster_papers_invalid_min_membership_returns_422()
    test_noise_papers_returns_only_noise()
    test_noise_route_not_shadowed_by_cluster_id_route()
    test_noise_papers_zero_matches_returns_200_empty_list()
    test_noise_papers_invalid_limit_returns_422()
    test_noise_papers_invalid_offset_returns_422()
    test_cluster_list_response_shape()
    test_cluster_detail_response_shape()
    test_cluster_papers_response_shape()
    test_unapproved_label_excluded_from_list_and_detail()
    test_cluster_from_an_older_non_latest_run_returns_404()
    test_openapi_documents_404_for_cluster_detail_and_papers()
    test_openapi_error_response_schema_matches_runtime_shape()
    test_openapi_does_not_document_404_for_list_and_noise()
    test_runtime_404_behavior_unchanged_after_metadata_change()
    print("\nALL TESTS PASSED")
