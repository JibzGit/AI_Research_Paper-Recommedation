import uuid

from fastapi import APIRouter, Query

from research_platform.api.schemas.errors import ErrorResponse
from research_platform.api.schemas.paper import PaperDetail
from research_platform.api.schemas.search import SearchResponse, SimilarPapersResponse
from research_platform.embeddings.recommend import similar_papers
from research_platform.embeddings.search import search_papers
from research_platform.papers.queries import get_paper_by_id

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("/search", response_model=SearchResponse)
def search(
    query: str = Query(...),
    top_k: int = Query(10, ge=1, le=100),
    category: str | None = Query(None),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
    min_similarity: float | None = Query(None, ge=-1, le=1),
) -> SearchResponse:
    """No SQL, no model call, no business validation here -- everything
    below Query()'s own type/range constraints (empty/whitespace-only
    query, year_from > year_to) is handled by search_papers() itself and
    surfaces as a ValueError, mapped to 400 by the registered handler."""
    results = search_papers(
        query=query,
        top_k=top_k,
        category=category,
        year_from=year_from,
        year_to=year_to,
        min_similarity=min_similarity,
    )
    return SearchResponse(query=query, count=len(results), results=results)


@router.get(
    "/{paper_id}",
    response_model=PaperDetail,
    responses={404: {"description": "Paper not found", "model": ErrorResponse}},
)
def paper_detail(paper_id: uuid.UUID) -> PaperDetail:
    """Declared AFTER /search: a path param without an explicit :type
    converter in the path string (e.g. "{paper_id}") matches ANY string at
    the routing level -- "search" would otherwise match this route first
    and fail UUID coercion (422) before ever reaching the real /search
    handler, the same class of ordering hazard as /clusters/noise vs
    /clusters/{cluster_id}. Shape doesn't collide with /{paper_id}/similar
    (different segment count), so this route's position relative to that
    one doesn't matter."""
    result = get_paper_by_id(str(paper_id))
    return PaperDetail(**result)


@router.get(
    "/{paper_id}/similar",
    response_model=SimilarPapersResponse,
    responses={404: {"description": "Paper not found", "model": ErrorResponse}},
)
def similar(
    paper_id: uuid.UUID,
    top_k: int = Query(10, ge=1, le=100),
    category: str | None = Query(None),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
    min_similarity: float | None = Query(None, ge=-1, le=1),
) -> SimilarPapersResponse:
    """paper_id: uuid.UUID as the path type means a malformed UUID never
    reaches this function body -- FastAPI rejects it with 422 first."""
    results = similar_papers(
        paper_id=str(paper_id),
        top_k=top_k,
        category=category,
        year_from=year_from,
        year_to=year_to,
        min_similarity=min_similarity,
    )
    return SimilarPapersResponse(source_paper_id=str(paper_id), count=len(results), results=results)
