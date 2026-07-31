"""Validates CORS configuration: the configured frontend origin receives the
appropriate CORS headers, an unapproved origin does not, credentials are
never allowed (so CORS_ALLOWED_ORIGINS could never be misconfigured into an
unsafe wildcard-plus-credentials combination), and adding the middleware
changes nothing about existing request/response behavior.

No pytest dependency. Run directly:

    python3 tests/test_cors.py
"""
from fastapi.testclient import TestClient

from research_platform import config
from research_platform.api.app import app

client = TestClient(app)

CONFIGURED_ORIGIN = "http://localhost:5173"
UNAPPROVED_ORIGIN = "http://evil.example.com"


def test_configured_origin_receives_allow_origin_header():
    response = client.get("/health", headers={"Origin": CONFIGURED_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == CONFIGURED_ORIGIN
    print("PASS: the configured frontend origin receives Access-Control-Allow-Origin")


def test_unapproved_origin_does_not_receive_allow_origin_header():
    response = client.get("/health", headers={"Origin": UNAPPROVED_ORIGIN})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    print("PASS: an unapproved origin does not receive Access-Control-Allow-Origin")


def test_preflight_for_configured_origin_allows_get():
    response = client.options(
        "/health",
        headers={"Origin": CONFIGURED_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == CONFIGURED_ORIGIN
    assert "GET" in response.headers.get("access-control-allow-methods", "")
    print("PASS: preflight for the configured origin allows GET")


def test_preflight_for_unapproved_origin_does_not_allow_it():
    response = client.options(
        "/health",
        headers={"Origin": UNAPPROVED_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers
    print("PASS: preflight for an unapproved origin does not receive Access-Control-Allow-Origin")


def test_credentials_never_allowed():
    response = client.get("/health", headers={"Origin": CONFIGURED_ORIGIN})
    assert "access-control-allow-credentials" not in response.headers
    print("PASS: Access-Control-Allow-Credentials is never sent")


def test_configured_origins_never_contain_wildcard():
    assert "*" not in config.CORS_ALLOWED_ORIGINS
    print("PASS: CORS_ALLOWED_ORIGINS never contains a wildcard")


def test_existing_response_body_unchanged_without_origin_header():
    """A same-origin/non-browser request (no Origin header) behaves exactly
    as it did before CORSMiddleware was added -- no CORS headers, unchanged
    status code and body."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}
    assert "access-control-allow-origin" not in response.headers
    print("PASS: a request with no Origin header is byte-identical to before CORS was added")


def test_existing_endpoints_still_reachable_with_configured_origin():
    response = client.get(
        "/api/v1/clusters", headers={"Origin": CONFIGURED_ORIGIN},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == CONFIGURED_ORIGIN
    print("PASS: an existing API endpoint remains fully functional with CORS headers attached")


if __name__ == "__main__":
    test_configured_origin_receives_allow_origin_header()
    test_unapproved_origin_does_not_receive_allow_origin_header()
    test_preflight_for_configured_origin_allows_get()
    test_preflight_for_unapproved_origin_does_not_allow_it()
    test_credentials_never_allowed()
    test_configured_origins_never_contain_wildcard()
    test_existing_response_body_unchanged_without_origin_header()
    test_existing_endpoints_still_reachable_with_configured_origin()
    print("\nALL TESTS PASSED")
