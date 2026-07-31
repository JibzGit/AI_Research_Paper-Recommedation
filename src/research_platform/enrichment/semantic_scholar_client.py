import requests

from research_platform.config import (
    SEMANTIC_SCHOLAR_429_BASELINE_SECONDS,
    SEMANTIC_SCHOLAR_API_KEY,
    SEMANTIC_SCHOLAR_BASE_DELAY_SECONDS,
    SEMANTIC_SCHOLAR_JITTER_MAX_SECONDS,
    SEMANTIC_SCHOLAR_MAX_COOLDOWN_SECONDS,
    SEMANTIC_SCHOLAR_MAX_RETRIES,
    SEMANTIC_SCHOLAR_TEMPORARY_ERROR_BASELINE_SECONDS,
)
from research_platform.ingestion import pacing

API_URL = "https://api.semanticscholar.org/graph/v1/paper"
USER_AGENT = "research-platform-dev (mailto:jibinsolomon370@gmail.com)"
SOURCE = "semantic_scholar"

FIELDS = (
    "paperId,externalIds,title,abstract,year,publicationDate,venue,citationCount,"
    "authors,authors.name,authors.authorId,authors.affiliations,"
    "references.paperId,references.externalIds,references.title,references.year"
)

# Semantic Scholar's documented limit is 1 request/second cumulative across
# ALL endpoints for a given key (or the shared unauthenticated pool). A
# single source-keyed pacing state (source='semantic_scholar') is used for
# every endpoint below -- there is deliberately no per-endpoint pacing
# state, and the base delay (1.1s, > the 1 req/s limit) is enforced
# regardless of whether a key is configured. An API key raises the rate
# ceiling on Semantic Scholar's side; it does not change how cautiously
# this client paces its own requests.
_RETRYABLE_SERVER_ERRORS = {500, 502, 503, 504}


class SemanticScholarClientError(Exception):
    pass


class SemanticScholarPermanentError(SemanticScholarClientError):
    """A request that will never succeed by retrying (e.g. HTTP 400)."""


class SemanticScholarTemporaryError(SemanticScholarClientError):
    """A request that failed repeatedly after exhausting the retry budget."""


def api_key_configured() -> bool:
    return SEMANTIC_SCHOLAR_API_KEY is not None


def _headers() -> dict:
    headers = {"User-Agent": USER_AGENT}
    if SEMANTIC_SCHOLAR_API_KEY:
        # Case-sensitive header name per Semantic Scholar's API. Never place
        # the key in the URL, query params, or request body.
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    return headers


def _http_get(url: str, params: dict | None = None) -> requests.Response:
    return requests.get(url, params=params, headers=_headers(), timeout=30)


def _request(
    session,
    url: str,
    params: dict | None = None,
    max_retries: int = SEMANTIC_SCHOLAR_MAX_RETRIES,
    treat_404_as_none: bool = False,
) -> dict | None:
    attempt = 0
    while True:
        pacing.wait_for_slot(session, SOURCE)

        try:
            response = _http_get(url, params)
        except (requests.Timeout, requests.ConnectionError) as exc:
            attempt += 1
            pacing.record_temporary_failure(
                session, SOURCE,
                baseline_seconds=SEMANTIC_SCHOLAR_TEMPORARY_ERROR_BASELINE_SECONDS,
                max_cooldown=SEMANTIC_SCHOLAR_MAX_COOLDOWN_SECONDS,
                jitter_max=SEMANTIC_SCHOLAR_JITTER_MAX_SECONDS,
            )
            if attempt >= max_retries:
                # Never include request details (which could carry the key
                # via headers) in the exception message -- only the
                # exception type/text from the underlying library.
                raise SemanticScholarTemporaryError(
                    f"exhausted {max_retries} retries after connection error: {exc}"
                ) from exc
            continue

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError as exc:
                attempt += 1
                pacing.record_temporary_failure(
                    session, SOURCE,
                    baseline_seconds=SEMANTIC_SCHOLAR_TEMPORARY_ERROR_BASELINE_SECONDS,
                    max_cooldown=SEMANTIC_SCHOLAR_MAX_COOLDOWN_SECONDS,
                    jitter_max=SEMANTIC_SCHOLAR_JITTER_MAX_SECONDS,
                )
                if attempt >= max_retries:
                    raise SemanticScholarTemporaryError(
                        f"exhausted {max_retries} retries after malformed JSON response: {exc}"
                    ) from exc
                continue
            pacing.record_success(
                session, SOURCE,
                base_delay=SEMANTIC_SCHOLAR_BASE_DELAY_SECONDS,
                jitter_max=SEMANTIC_SCHOLAR_JITTER_MAX_SECONDS,
            )
            return data

        if response.status_code == 404 and treat_404_as_none:
            pacing.record_success(
                session, SOURCE,
                base_delay=SEMANTIC_SCHOLAR_BASE_DELAY_SECONDS,
                jitter_max=SEMANTIC_SCHOLAR_JITTER_MAX_SECONDS,
            )
            return None

        if response.status_code == 429:
            attempt += 1
            pacing.record_rate_limited(
                session, SOURCE, response.headers.get("Retry-After"),
                baseline_seconds=SEMANTIC_SCHOLAR_429_BASELINE_SECONDS,
                max_cooldown=SEMANTIC_SCHOLAR_MAX_COOLDOWN_SECONDS,
                jitter_max=SEMANTIC_SCHOLAR_JITTER_MAX_SECONDS,
            )
            if attempt >= max_retries:
                raise SemanticScholarTemporaryError(f"exhausted {max_retries} retries after HTTP 429")
            continue

        if response.status_code in _RETRYABLE_SERVER_ERRORS:
            attempt += 1
            pacing.record_temporary_failure(
                session, SOURCE,
                baseline_seconds=SEMANTIC_SCHOLAR_TEMPORARY_ERROR_BASELINE_SECONDS,
                max_cooldown=SEMANTIC_SCHOLAR_MAX_COOLDOWN_SECONDS,
                jitter_max=SEMANTIC_SCHOLAR_JITTER_MAX_SECONDS,
            )
            if attempt >= max_retries:
                raise SemanticScholarTemporaryError(
                    f"exhausted {max_retries} retries after HTTP {response.status_code}"
                )
            continue

        pacing.record_permanent_error(session, SOURCE, base_delay=SEMANTIC_SCHOLAR_BASE_DELAY_SECONDS)
        raise SemanticScholarPermanentError(
            f"Semantic Scholar API returned HTTP {response.status_code}: {response.text[:300]!r}"
        )


def get_paper_by_doi(session, doi: str) -> dict | None:
    url = f"{API_URL}/DOI:{doi}"
    return _request(session, url, params={"fields": FIELDS}, treat_404_as_none=True)


def get_paper_by_s2_id(session, s2_id: str) -> dict | None:
    url = f"{API_URL}/{s2_id}"
    return _request(session, url, params={"fields": FIELDS}, treat_404_as_none=True)


def get_paper_by_arxiv_id(session, arxiv_id: str) -> dict | None:
    """Confirmed empirically to work: S2's Graph API treats ARXIV: as a
    first-class external-ID prefix, unlike OpenAlex."""
    url = f"{API_URL}/ARXIV:{arxiv_id}"
    return _request(session, url, params={"fields": FIELDS}, treat_404_as_none=True)


def search_papers(session, query: str, limit: int = 5) -> list[dict]:
    params = {"query": query, "fields": FIELDS, "limit": limit}
    data = _request(session, f"{API_URL}/search", params=params)
    return data.get("data", []) if data else []
