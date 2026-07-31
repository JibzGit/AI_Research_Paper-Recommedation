from datetime import datetime

from pydantic import BaseModel


class PaperResult(BaseModel):
    """One ranked result, shared by /search and /{paper_id}/similar. Field
    names/types map 1:1 onto the dicts search_papers()/similar_papers()
    already return."""

    paper_id: str
    arxiv_id: str | None
    title: str
    abstract: str
    authors: list[str]
    primary_category: str
    publication_date: datetime | None
    similarity_score: float


class PaperDetail(BaseModel):
    """GET /papers/{paper_id}. Distinct from PaperResult -- this is a direct
    single-paper lookup, not a ranked search/similarity result, so it has no
    similarity_score and instead carries current_version_number and
    embedding_available (whether similar_papers() could use this paper as a
    source right now)."""

    paper_id: str
    arxiv_id: str | None
    title: str
    abstract: str
    authors: list[str]
    primary_category: str
    publication_date: datetime | None
    current_version_number: int
    embedding_available: bool
