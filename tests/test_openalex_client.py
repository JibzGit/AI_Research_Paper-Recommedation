"""Validates OpenAlex API-key handling: attached to every request path,
never leaked in logs/exceptions, and required before any execution is
attempted. No pytest dependency -- run directly:

    python3 tests/test_openalex_client.py

This mirrors the project's existing validation-script pattern rather than
introducing new tooling. Never prints the key itself, only booleans/facts
about it. Deliberately fully side-effect-free: both the network layer
(_http_get) and the pacing layer are mocked, so these tests make zero real
HTTP calls and zero database writes (including pacing bookkeeping) -- no
use-a-real-session-and-let-pacing-touch-the-DB shortcuts, given how close
in time this runs to the OpenAlex budget-exhaustion incident.
"""
from unittest.mock import MagicMock, patch

from research_platform import config
from research_platform.enrichment import openalex_client as oc


def _fake_response(status: int, text: str = "{}", headers: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = text
    response.headers = headers or {}
    response.json.return_value = {}
    return response


def _no_op_pacing():
    """A stand-in for the pacing module with every function as a no-op, so
    these tests never touch api_request_states."""
    fake = MagicMock()
    fake.wait_for_slot.return_value = 0.0
    fake.record_success.return_value = None
    fake.record_permanent_error.return_value = None
    fake.record_temporary_failure.return_value = None
    fake.record_rate_limited.return_value = None
    return fake


def test_key_attached_to_every_request_path():
    captured_calls = []

    def fake_http_get(url, params):
        captured_calls.append({"url": url, "params": dict(params)})
        return _fake_response(200, text="{}")

    session = MagicMock()  # never touched: pacing is mocked, no DB access occurs
    with patch.object(oc, "_http_get", side_effect=fake_http_get), patch.object(oc, "pacing", _no_op_pacing()):
        oc.get_work_by_doi(session, "10.1234/test-doi")
        oc.get_work_by_id(session, "W123456789")
        oc.search_works(session, "test query")
        oc.get_rate_limit_status(session)

    assert len(captured_calls) == 4, f"expected 4 calls, got {len(captured_calls)}"
    for call in captured_calls:
        assert call["params"].get("api_key") == config.OPENALEX_API_KEY, (
            f"api_key missing or wrong on call to {call['url']}"
        )
    print(
        "PASS: api_key attached to all 4 request paths "
        "(DOI lookup, work-ID lookup, search, rate-limit) -- value not printed, zero DB writes"
    )


def test_key_not_in_exception_messages():
    def fake_http_get(url, params):
        return _fake_response(400, text='{"error":"bad request"}')

    session = MagicMock()
    raised_message = None
    with patch.object(oc, "_http_get", side_effect=fake_http_get), patch.object(oc, "pacing", _no_op_pacing()):
        try:
            oc.get_work_by_doi(session, "10.1234/test-doi")
        except oc.OpenAlexPermanentError as exc:
            raised_message = str(exc)

    assert raised_message is not None, "expected OpenAlexPermanentError to be raised"
    assert config.OPENALEX_API_KEY not in raised_message
    print("PASS: exception message does not contain the API key")


def test_missing_key_fails_fast_with_clear_message():
    session = MagicMock()
    raised_message = None
    call_attempted = False

    def fake_http_get(url, params):
        nonlocal call_attempted
        call_attempted = True
        return _fake_response(200, text="{}")

    with (
        patch.object(oc, "OPENALEX_API_KEY", None),
        patch.object(oc, "_http_get", side_effect=fake_http_get),
        patch.object(oc, "pacing", _no_op_pacing()),
    ):
        try:
            oc.get_work_by_doi(session, "10.1234/test-doi")
        except oc.OpenAlexMissingApiKeyError as exc:
            raised_message = str(exc)

    assert raised_message is not None, "expected OpenAlexMissingApiKeyError to be raised"
    assert not call_attempted, "no network call should be attempted when the key is missing"
    assert "API key" in raised_message or "api key" in raised_message.lower() or "OPENALEX_API_KEY" in raised_message
    print("PASS: missing key fails fast with a clear message, before any network call or pacing write")


if __name__ == "__main__":
    test_key_attached_to_every_request_path()
    test_key_not_in_exception_messages()
    test_missing_key_fails_fast_with_clear_message()
    print("\nALL TESTS PASSED")
