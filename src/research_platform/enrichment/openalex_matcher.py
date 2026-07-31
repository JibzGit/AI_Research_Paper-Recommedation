import re

from research_platform.enrichment.openalex_client import OpenAlexTemporaryError, get_work_by_doi, search_works
from research_platform.ingestion.normalize import normalize_title

MATCHING_RULE_VERSION = "openalex_matcher_v2"

TITLE_EXACT_YEAR_TOLERANCE = 1
TITLE_CANDIDATE_MIN_TOKEN_OVERLAP = 0.8
TITLE_AMBIGUOUS_MIN_TOKEN_OVERLAP = 0.5

_SEARCH_WILDCARD_CHARS_RE = re.compile(r"[?*]")
_WHITESPACE_RE = re.compile(r"\s+")


def _sanitize_search_query(title: str) -> str:
    """OpenAlex's default (stemmed) search endpoint rejects literal `?`/`*`
    characters as unescaped wildcards (HTTP 400 'Wildcards require exact
    search') -- found on 1601.00720 and 2607.24662. Strips them from the
    query text sent to OpenAlex only; never touches the paper's stored
    title (used elsewhere for scoring/display via normalize_title)."""
    cleaned = _SEARCH_WILDCARD_CHARS_RE.sub("", title)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def _token_overlap(a: str, b: str) -> float:
    tokens_a, tokens_b = set(a.split()), set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _surnames(names: list[str]) -> set[str]:
    result = set()
    for name in names:
        parts = name.strip().split()
        if parts:
            result.add(parts[-1].lower())
    return result


def _openalex_surnames(work: dict) -> set[str]:
    names = [a.get("author", {}).get("display_name", "") for a in work.get("authorships", [])]
    return _surnames(names)


def _score_candidate(our_normalized_title: str, our_year: int | None, our_surnames: set[str], candidate: dict) -> dict:
    candidate_title = candidate.get("title") or ""
    norm_candidate_title = normalize_title(candidate_title) if candidate_title else ""
    title_overlap = _token_overlap(our_normalized_title, norm_candidate_title)
    exact_title = bool(norm_candidate_title) and our_normalized_title == norm_candidate_title

    candidate_year = candidate.get("publication_year")
    year_match = (
        our_year is not None
        and candidate_year is not None
        and abs(candidate_year - our_year) <= TITLE_EXACT_YEAR_TOLERANCE
    )

    author_overlap = our_surnames & _openalex_surnames(candidate)

    return {
        "openalex_id": candidate.get("id"),
        "title": candidate_title,
        "title_overlap": round(title_overlap, 3),
        "exact_title": exact_title,
        "candidate_year": candidate_year,
        "year_match": year_match,
        "author_overlap_count": len(author_overlap),
        "author_overlap_surnames": sorted(author_overlap),
    }


def _result(match_status, match_method=None, confidence=None, work=None, evidence=None):
    return {
        "match_status": match_status,
        "match_method": match_method,
        "confidence": confidence,
        "matched_work": work,
        "matched_external_id": work.get("id") if work else None,
        "evidence": evidence or {},
        "matching_rule_version": MATCHING_RULE_VERSION,
    }


def match_paper(session, paper, author_names: list[str], publication_year: int | None) -> dict:
    """Strict-order matching: exact DOI -> cautious title/year/author
    candidate search -> AMBIGUOUS/NOT_FOUND. Never auto-merges on title
    similarity alone -- every acceptance requires a corroborating year or
    author-overlap signal in addition to a strong title match, except
    exact DOI (authoritative on its own).

    A dedicated "arXiv-ID fallback" tier was designed and tested against
    the live API before this was written, and dropped: OpenAlex's `ids`
    field has no arXiv-specific slot, searching by the raw arXiv-ID string
    returns irrelevant full-text-relevance noise (verified), and a
    landing_page_url filter attempt returned zero results (verified). DOI
    and title/year/author candidate matching are the two tiers that
    actually carry signal; this is an empirical finding, not an oversight.
    """
    our_surnames = _surnames(author_names)
    our_normalized_title = normalize_title(paper.title)
    evidence: dict = {}

    if paper.doi:
        try:
            work = get_work_by_doi(session, paper.doi)
        except OpenAlexTemporaryError as exc:
            return _result("FAILED", evidence={"stage": "doi_lookup", "error": str(exc)})
        evidence["doi_lookup"] = {"doi": paper.doi, "found": work is not None}
        if work:
            return _result("MATCHED", "exact_doi", 1.0, work, evidence)

    search_query = _sanitize_search_query(paper.title)
    try:
        title_candidates = search_works(session, search_query, per_page=5)
    except OpenAlexTemporaryError as exc:
        return _result("FAILED", evidence={**evidence, "stage": "title_search", "error": str(exc)})
    scored_title = [
        _score_candidate(our_normalized_title, publication_year, our_surnames, c) for c in title_candidates
    ]
    evidence["title_search"] = {"query": search_query, "original_title": paper.title, "candidates": scored_title}

    strong_title = [
        s for s in scored_title
        if (s["exact_title"] or s["title_overlap"] >= TITLE_CANDIDATE_MIN_TOKEN_OVERLAP)
        and (s["year_match"] or s["author_overlap_count"] >= 1)
    ]
    moderate_title = [s for s in scored_title if s["title_overlap"] >= TITLE_AMBIGUOUS_MIN_TOKEN_OVERLAP]

    if len(strong_title) == 1:
        work = next(c for c in title_candidates if c.get("id") == strong_title[0]["openalex_id"])
        confidence = 0.85 if strong_title[0]["exact_title"] else 0.7
        return _result("MATCHED", "title_candidate", confidence, work, evidence)

    if len(strong_title) > 1 or moderate_title:
        return _result("AMBIGUOUS", evidence=evidence)

    return _result("NOT_FOUND", evidence=evidence)
