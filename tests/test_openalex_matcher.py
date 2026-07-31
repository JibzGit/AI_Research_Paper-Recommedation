"""Validates the OpenAlex title-query wildcard fix: `?`/`*` characters are
stripped from the search query before it's sent to OpenAlex, preventing the
HTTP 400 "Wildcards (* or ?) require exact (no-stem) search" error found on
1601.00720 and 2607.24662. Never modifies the paper's stored title -- only
the query text sent to the search endpoint. No pytest dependency, no real
network calls or database writes (pacing is mocked). Run directly:

    python3 tests/test_openalex_matcher.py
"""
from unittest.mock import MagicMock, patch

from research_platform.enrichment import openalex_client as oc
from research_platform.enrichment import openalex_matcher as om


class _FakePaper:
    def __init__(self, title: str, doi: str | None = None, arxiv_id: str = "0000.00000"):
        self.title = title
        self.doi = doi
        self.arxiv_id = arxiv_id


def _fake_response(status: int, text: str = "{}", json_data: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = text
    response.json.return_value = json_data if json_data is not None else {}
    return response


def test_sanitize_strips_question_mark():
    assert om._sanitize_search_query("How do neurons operate?") == "How do neurons operate"
    print("PASS: '?' stripped")


def test_sanitize_strips_asterisk():
    assert om._sanitize_search_query("Attention* is all *you* need") == "Attention is all you need"
    print("PASS: '*' stripped")


def test_sanitize_collapses_extra_spaces():
    result = om._sanitize_search_query("What is this?   A study  of *stars*")
    assert "  " not in result
    assert result == "What is this A study of stars"
    print("PASS: extra spaces from cleaning collapsed")


def test_sanitize_does_not_mutate_caller_string():
    original = "Is this real?"
    om._sanitize_search_query(original)
    assert original == "Is this real?"
    print("PASS: sanitizer does not mutate its input")


def test_wildcard_title_no_longer_raises_permanent_error():
    """Simulates OpenAlex's real behavior: 400 if the query contains a raw
    wildcard, 200 otherwise. Confirms match_paper on a wildcard-containing
    title no longer surfaces as OpenAlexPermanentError / FAILED."""

    def fake_http_get(url, params):
        query = params.get("search", "")
        if "?" in query or "*" in query:
            return _fake_response(
                400,
                text=(
                    '{"error":"Invalid query parameters error.","message":'
                    '"Wildcards (* or ?) require exact (no-stem) search..."}'
                ),
            )
        return _fake_response(200, json_data={"results": []})

    fake_pacing = MagicMock()
    fake_pacing.wait_for_slot.return_value = 0.0

    paper = _FakePaper(
        title="How do neurons operate on sparse distributed representations? A mathematical theory",
        arxiv_id="1601.00720",
    )

    with patch.object(oc, "_http_get", side_effect=fake_http_get), patch.object(oc, "pacing", fake_pacing):
        try:
            result = om.match_paper(MagicMock(), paper, author_names=[], publication_year=2016)
        except oc.OpenAlexPermanentError:
            result = None

    assert result is not None, "match_paper raised OpenAlexPermanentError -- wildcard fix did not work"
    assert result["match_status"] != "FAILED"
    print("PASS: wildcard '?' title no longer raises OpenAlexPermanentError; match_status =", result["match_status"])


def test_wildcard_asterisk_title_no_longer_raises_permanent_error():
    def fake_http_get(url, params):
        query = params.get("search", "")
        if "?" in query or "*" in query:
            return _fake_response(400, text='{"error":"Invalid query parameters error."}')
        return _fake_response(200, json_data={"results": []})

    fake_pacing = MagicMock()
    fake_pacing.wait_for_slot.return_value = 0.0

    paper = _FakePaper(title="A Study of Attention* Mechanisms *In* Transformers", arxiv_id="2607.24662")

    with patch.object(oc, "_http_get", side_effect=fake_http_get), patch.object(oc, "pacing", fake_pacing):
        try:
            result = om.match_paper(MagicMock(), paper, author_names=[], publication_year=2026)
        except oc.OpenAlexPermanentError:
            result = None

    assert result is not None, "match_paper raised OpenAlexPermanentError -- wildcard fix did not work"
    assert result["match_status"] != "FAILED"
    print("PASS: wildcard '*' title no longer raises OpenAlexPermanentError; match_status =", result["match_status"])


def test_doi_first_logic_still_preserved():
    """The sanitization change must not affect the DOI-first tier."""
    call_log = []

    def fake_http_get(url, params):
        call_log.append(url)
        if "doi:" in url:
            return _fake_response(200, json_data={"id": "https://openalex.org/W1", "title": "Matched via DOI"})
        return _fake_response(200, json_data={"results": []})

    fake_pacing = MagicMock()
    fake_pacing.wait_for_slot.return_value = 0.0

    paper = _FakePaper(title="Some title?", doi="10.1234/test-doi")

    with patch.object(oc, "_http_get", side_effect=fake_http_get), patch.object(oc, "pacing", fake_pacing):
        result = om.match_paper(MagicMock(), paper, author_names=[], publication_year=2020)

    assert result["match_status"] == "MATCHED"
    assert result["match_method"] == "exact_doi"
    assert len(call_log) == 1, "DOI match should short-circuit before any title search call"
    print("PASS: DOI-first matching still short-circuits correctly, unaffected by the sanitization change")


if __name__ == "__main__":
    test_sanitize_strips_question_mark()
    test_sanitize_strips_asterisk()
    test_sanitize_collapses_extra_spaces()
    test_sanitize_does_not_mutate_caller_string()
    test_wildcard_title_no_longer_raises_permanent_error()
    test_wildcard_asterisk_title_no_longer_raises_permanent_error()
    test_doi_first_logic_still_preserved()
    print("\nALL TESTS PASSED")
