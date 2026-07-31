from pydantic import BaseModel

from research_platform.api.schemas.paper import PaperResult


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[PaperResult]


class SimilarPapersResponse(BaseModel):
    source_paper_id: str
    count: int
    results: list[PaperResult]
