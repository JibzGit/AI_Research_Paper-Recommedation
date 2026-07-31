from xml.etree import ElementTree as ET

import requests

from research_platform.config import ARXIV_MAX_RETRIES
from research_platform.ingestion import pacing

ATOM_NS = "{http://www.w3.org/2005/Atom}"
OPENSEARCH_NS = "{http://a9.com/-/spec/opensearch/1.1/}"

API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = "research-platform-dev (contact: jibinsolomon370@gmail.com)"
SOURCE = "arxiv"

# HTTP status codes treated as temporary/retryable (excluding 429, handled separately)
_RETRYABLE_SERVER_ERRORS = {500, 502, 503, 504}


class ArxivClientError(Exception):
    pass


class ArxivPermanentError(ArxivClientError):
    """A request that will never succeed by retrying (e.g. HTTP 400 malformed query)."""


class ArxivTemporaryError(ArxivClientError):
    """A request that failed repeatedly after exhausting the configured retry budget."""


def _http_get(params: dict) -> requests.Response:
    """Thin, easily-monkeypatched wrapper around the actual network call."""
    return requests.get(API_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)


def _request(session, params: dict, max_retries: int = ARXIV_MAX_RETRIES) -> ET.Element:
    attempt = 0
    while True:
        pacing.wait_for_slot(session, SOURCE)

        try:
            response = _http_get(params)
        except (requests.Timeout, requests.ConnectionError) as exc:
            attempt += 1
            pacing.record_temporary_failure(session, SOURCE)
            if attempt >= max_retries:
                raise ArxivTemporaryError(
                    f"exhausted {max_retries} retries after connection error: {exc}"
                ) from exc
            continue

        if response.status_code == 200:
            pacing.record_success(session, SOURCE)
            return ET.fromstring(response.text)

        if response.status_code == 429:
            attempt += 1
            pacing.record_rate_limited(session, SOURCE, response.headers.get("Retry-After"))
            if attempt >= max_retries:
                raise ArxivTemporaryError(f"exhausted {max_retries} retries after HTTP 429")
            continue

        if response.status_code in _RETRYABLE_SERVER_ERRORS:
            attempt += 1
            pacing.record_temporary_failure(session, SOURCE)
            if attempt >= max_retries:
                raise ArxivTemporaryError(
                    f"exhausted {max_retries} retries after HTTP {response.status_code}"
                )
            continue

        # Permanent error (e.g. 400): do not retry.
        pacing.record_permanent_error(session, SOURCE)
        raise ArxivPermanentError(f"arXiv API returned HTTP {response.status_code}: {response.text[:300]!r}")


def build_category_query(categories: list[str]) -> str:
    return "(" + " OR ".join(f"cat:{c}" for c in categories) + ")"


def build_date_range_query(categories: list[str], window_start, window_end) -> str:
    """window_start/window_end are timezone-aware datetimes. arXiv's
    submittedDate range filter uses UTC, second-precision, no separators."""
    fmt = "%Y%m%d%H%M%S"
    date_clause = f"submittedDate:[{window_start.strftime(fmt)} TO {window_end.strftime(fmt)}]"
    return f"{build_category_query(categories)} AND {date_clause}"


def fetch_by_categories(session, categories: list[str], max_results: int, start: int = 0) -> list[ET.Element]:
    root = _request(
        session,
        {
            "search_query": build_category_query(categories),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": start,
            "max_results": max_results,
        },
    )
    return root.findall(f"{ATOM_NS}entry")


def fetch_by_search_query(session, search_query: str, max_results: int, start: int = 0) -> list[ET.Element]:
    root = _request(
        session,
        {
            "search_query": search_query,
            "sortBy": "submittedDate",
            "sortOrder": "ascending",
            "start": start,
            "max_results": max_results,
        },
    )
    return root.findall(f"{ATOM_NS}entry")


def fetch_by_id(session, arxiv_id: str) -> ET.Element | None:
    root = _request(session, {"id_list": arxiv_id})
    entries = root.findall(f"{ATOM_NS}entry")
    return entries[0] if entries else None


def preflight_count(session, search_query: str) -> int:
    """Minimum-size request (max_results=1) used only to read
    opensearch:totalResults during plan-only window sizing. Does not count
    against the paper-processing quota."""
    root = _request(session, {"search_query": search_query, "start": 0, "max_results": 1})
    node = root.find(f"{OPENSEARCH_NS}totalResults")
    return int(node.text) if node is not None and node.text else 0
