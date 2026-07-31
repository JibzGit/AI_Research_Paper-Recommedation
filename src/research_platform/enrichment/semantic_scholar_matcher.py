from research_platform.enrichment.semantic_scholar_client import (
    SemanticScholarTemporaryError,
    get_paper_by_arxiv_id,
    get_paper_by_doi,
    get_paper_by_s2_id,
    search_papers,
)
from research_platform.ingestion.normalize import normalize_title

MATCHING_RULE_VERSION = "semantic_scholar_matcher_v1"

TITLE_EXACT_YEAR_TOLERANCE = 1
TITLE_CANDIDATE_MIN_TOKEN_OVERLAP = 0.8
TITLE_AMBIGUOUS_MIN_TOKEN_OVERLAP = 0.5


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


def _s2_surnames(paper: dict) -> set[str]:
    names = [a.get("name", "") for a in (paper.get("authors") or [])]
    return _surnames(names)


def _score_candidate(our_normalized_title: str, our_year: int | None, our_surnames: set[str], candidate: dict) -> dict:
    candidate_title = candidate.get("title") or ""
    norm_candidate_title = normalize_title(candidate_title) if candidate_title else ""
    title_overlap = _token_overlap(our_normalized_title, norm_candidate_title)
    exact_title = bool(norm_candidate_title) and our_normalized_title == norm_candidate_title

    candidate_year = candidate.get("year")
    year_match = (
        our_year is not None
        and candidate_year is not None
        and abs(candidate_year - our_year) <= TITLE_EXACT_YEAR_TOLERANCE
    )

    author_overlap = our_surnames & _s2_surnames(candidate)

    return {
        "s2_paper_id": candidate.get("paperId"),
        "title": candidate_title,
        "title_overlap": round(title_overlap, 3),
        "exact_title": exact_title,
        "candidate_year": candidate_year,
        "year_match": year_match,
        "author_overlap_count": len(author_overlap),
        "author_overlap_surnames": sorted(author_overlap),
    }


def _result(match_status, match_method=None, confidence=None, paper=None, evidence=None):
    return {
        "match_status": match_status,
        "match_method": match_method,
        "confidence": confidence,
        "matched_paper": paper,
        "matched_external_id": paper.get("paperId") if paper else None,
        "evidence": evidence or {},
        "matching_rule_version": MATCHING_RULE_VERSION,
    }


def match_paper(
    session, paper, author_names: list[str], publication_year: int | None, known_s2_id: str | None = None
) -> dict:
    """Strict-order matching: exact DOI -> exact known S2 ID -> exact
    arXiv-ID lookup (confirmed working against the live API, unlike
    OpenAlex) -> cautious title/year/author candidate search ->
    AMBIGUOUS/NOT_FOUND. Never auto-merges on title similarity alone."""
    our_surnames = _surnames(author_names)
    our_normalized_title = normalize_title(paper.title)
    evidence: dict = {}

    if paper.doi:
        try:
            result = get_paper_by_doi(session, paper.doi)
        except SemanticScholarTemporaryError as exc:
            return _result("FAILED", evidence={"stage": "doi_lookup", "error": str(exc)})
        evidence["doi_lookup"] = {"doi": paper.doi, "found": result is not None}
        if result:
            return _result("MATCHED", "exact_doi", 1.0, result, evidence)

    if known_s2_id:
        try:
            result = get_paper_by_s2_id(session, known_s2_id)
        except SemanticScholarTemporaryError as exc:
            return _result("FAILED", evidence={**evidence, "stage": "known_id_lookup", "error": str(exc)})
        evidence["known_id_lookup"] = {"s2_id": known_s2_id, "found": result is not None}
        if result:
            return _result("MATCHED", "exact_known_s2_id", 1.0, result, evidence)

    if paper.arxiv_id:
        try:
            result = get_paper_by_arxiv_id(session, paper.arxiv_id)
        except SemanticScholarTemporaryError as exc:
            return _result("FAILED", evidence={**evidence, "stage": "arxiv_id_lookup", "error": str(exc)})
        evidence["arxiv_id_lookup"] = {"arxiv_id": paper.arxiv_id, "found": result is not None}
        if result:
            return _result("MATCHED", "exact_arxiv_id", 0.95, result, evidence)

    try:
        title_candidates = search_papers(session, paper.title, limit=5)
    except SemanticScholarTemporaryError as exc:
        return _result("FAILED", evidence={**evidence, "stage": "title_search", "error": str(exc)})
    scored_title = [
        _score_candidate(our_normalized_title, publication_year, our_surnames, c) for c in title_candidates
    ]
    evidence["title_search"] = {"query": paper.title, "candidates": scored_title}

    strong_title = [
        s for s in scored_title
        if (s["exact_title"] or s["title_overlap"] >= TITLE_CANDIDATE_MIN_TOKEN_OVERLAP)
        and (s["year_match"] or s["author_overlap_count"] >= 1)
    ]
    moderate_title = [s for s in scored_title if s["title_overlap"] >= TITLE_AMBIGUOUS_MIN_TOKEN_OVERLAP]

    if len(strong_title) == 1:
        result = next(c for c in title_candidates if c.get("paperId") == strong_title[0]["s2_paper_id"])
        confidence = 0.85 if strong_title[0]["exact_title"] else 0.7
        return _result("MATCHED", "title_candidate", confidence, result, evidence)

    if len(strong_title) > 1 or moderate_title:
        return _result("AMBIGUOUS", evidence=evidence)

    return _result("NOT_FOUND", evidence=evidence)
