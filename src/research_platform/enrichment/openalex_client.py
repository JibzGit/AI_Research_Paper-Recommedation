import requests

from research_platform.config import ARXIV_MAX_RETRIES, OPENALEX_API_KEY
from research_platform.ingestion import pacing

API_URL = "https://api.openalex.org/works"
RATE_LIMIT_URL = "https://api.openalex.org/rate-limit"
USER_AGENT = "research-platform-dev (mailto:jibinsolomon370@gmail.com)"
SOURCE = "openalex"

_RETRYABLE_SERVER_ERRORS = {500, 502, 503, 504}


class OpenAlexClientError(Exception):
    pass


class OpenAlexPermanentError(OpenAlexClientError):
    """A request that will never succeed by retrying (e.g. HTTP 400)."""


class OpenAlexTemporaryError(OpenAlexClientError):
    """A request that failed repeatedly after exhausting the retry budget."""


class OpenAlexMissingApiKeyError(OpenAlexClientError):
    """Raised immediately, before any network call, when OPENALEX_API_KEY
    is not configured. Added after the 2026-07-29 incident where sustained
    unauthenticated use silently exhausted OpenAlex's daily credit budget --
    OpenAlex execution must never be attempted without a key."""


def api_key_configured() -> bool:
    return OPENALEX_API_KEY is not None


def _http_get(url: str, params: dict) -> requests.Response:
    return requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)


def _request(
    session,
    url: str,
    params: dict | None = None,
    max_retries: int = ARXIV_MAX_RETRIES,
    treat_404_as_none: bool = False,
) -> dict | None:
    if not OPENALEX_API_KEY:
        raise OpenAlexMissingApiKeyError(
            "OPENALEX_API_KEY is not configured. Set it in .env before running OpenAlex "
            "enrichment -- unauthenticated OpenAlex execution is refused, not attempted."
        )

    # Every OpenAlex request path funnels through here, so the key is
    # attached uniformly regardless of which public function is called --
    # DOI lookup, work-ID lookup, search, or the rate-limit endpoint.
    request_params = dict(params or {})
    request_params["api_key"] = OPENALEX_API_KEY

    attempt = 0
    while True:
        pacing.wait_for_slot(session, SOURCE)

        try:
            response = _http_get(url, request_params)
        except (requests.Timeout, requests.ConnectionError) as exc:
            attempt += 1
            pacing.record_temporary_failure(session, SOURCE)
            if attempt >= max_retries:
                raise OpenAlexTemporaryError(
                    f"exhausted {max_retries} retries after connection error: {exc}"
                ) from exc
            continue

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError as exc:
                attempt += 1
                pacing.record_temporary_failure(session, SOURCE)
                if attempt >= max_retries:
                    raise OpenAlexTemporaryError(
                        f"exhausted {max_retries} retries after malformed JSON response: {exc}"
                    ) from exc
                continue
            pacing.record_success(session, SOURCE)
            return data

        if response.status_code == 404 and treat_404_as_none:
            pacing.record_success(session, SOURCE)
            return None

        if response.status_code == 429:
            attempt += 1
            pacing.record_rate_limited(session, SOURCE, response.headers.get("Retry-After"))
            if attempt >= max_retries:
                raise OpenAlexTemporaryError(f"exhausted {max_retries} retries after HTTP 429")
            continue

        if response.status_code in _RETRYABLE_SERVER_ERRORS:
            attempt += 1
            pacing.record_temporary_failure(session, SOURCE)
            if attempt >= max_retries:
                raise OpenAlexTemporaryError(
                    f"exhausted {max_retries} retries after HTTP {response.status_code}"
                )
            continue

        # Permanent error (e.g. 400): do not retry. response.text is the
        # server's response body only -- never our own request params, so
        # the key cannot leak into this message.
        pacing.record_permanent_error(session, SOURCE)
        raise OpenAlexPermanentError(
            f"OpenAlex API returned HTTP {response.status_code}: {response.text[:300]!r}"
        )


def get_work_by_doi(session, doi: str) -> dict | None:
    """Direct lookup, OpenAlex's most reliable match path. Returns None
    (not an error) if the DOI isn't in OpenAlex's index."""
    url = f"{API_URL}/doi:{doi}"
    return _request(session, url, treat_404_as_none=True)


def get_work_by_id(session, openalex_id: str) -> dict | None:
    """Direct lookup by OpenAlex's own work ID (e.g. 'W2626778328')."""
    url = f"{API_URL}/{openalex_id}"
    return _request(session, url, treat_404_as_none=True)


def search_works(session, query: str, per_page: int = 5) -> list[dict]:
    """General relevance search, used for title-candidate matching. Empty
    list means no candidates, not an error."""
    params = {"search": query, "per_page": per_page}
    data = _request(session, API_URL, params=params)
    return data.get("results", []) if data else []


def get_rate_limit_status(session) -> dict | None:
    """Requires OPENALEX_API_KEY (the endpoint itself 401s without one --
    confirmed during the 2026-07-29 diagnostic). Returns the account's
    daily budget/usage/reset info.

    OpenAlex's own response body includes a masked echo of the key (e.g.
    "ke5...Cu8") under the "api_key" field -- discovered the hard way when
    an earlier caller printed the raw response unredacted. That field is
    stripped here unconditionally so no caller can leak it again, even a
    masked fragment."""
    data = _request(session, RATE_LIMIT_URL)
    if data and "api_key" in data:
        data = {k: v for k, v in data.items() if k != "api_key"}
    return data
