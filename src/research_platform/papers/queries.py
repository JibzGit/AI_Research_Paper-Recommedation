import uuid

from sqlalchemy import func, select

from research_platform import config
from research_platform.db.models import Category, Paper, PaperEmbedding
from research_platform.db.session import SessionLocal
from research_platform.embeddings.recommend import PaperNotFoundError
from research_platform.embeddings.search import fetch_authors_batched, publication_date_subquery


def _coerce_paper_id(paper_id) -> uuid.UUID:
    if paper_id is None:
        raise ValueError("paper_id must be provided")
    if isinstance(paper_id, uuid.UUID):
        return paper_id
    try:
        return uuid.UUID(str(paper_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"paper_id must be a valid UUID; got {paper_id!r}") from exc


def get_paper_by_id(paper_id) -> dict:
    """Read-only single-paper lookup, keyed on Paper.id. Raises
    PaperNotFoundError (-> 404) only when no paper row exists at all -- the
    same exception type embeddings.recommend.similar_papers() uses, so both
    endpoints map "genuinely doesn't exist" to 404 through one shared
    handler. A paper that exists but is_canonical=False raises a plain
    ValueError (-> 400), deliberately mirroring similar_papers()'s existing
    "selected paper is not canonical" rule: the resource is real, so it is
    never a 404, but it is also not a normal browsable/linkable paper in
    this API's model. embedding_available reflects the same "active
    successful embedding" definition (current EMBEDDING_MODEL_NAME/
    EMBEDDING_MODEL_REVISION, status SUCCEEDED) that similar_papers() uses
    to decide whether a selected paper can produce recommendations at all --
    it's the frontend's signal for whether "Find Similar" would work."""
    paper_uuid = _coerce_paper_id(paper_id)

    session = SessionLocal()
    try:
        paper = session.get(Paper, paper_uuid)
        if paper is None:
            raise PaperNotFoundError(f"paper not found: {paper_id}")
        if not paper.is_canonical:
            raise ValueError(f"paper is not canonical: {paper_id}")

        v1_versions, publication_date_expr = publication_date_subquery()
        row = session.execute(
            select(
                Category.code.label("category_code"),
                Category.display_name.label("category_display_name"),
                publication_date_expr.label("publication_date"),
            )
            .select_from(Paper)
            .join(Category, Category.id == Paper.primary_category_id)
            .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
            .where(Paper.id == paper_uuid)
        ).one()

        authors_by_paper = fetch_authors_batched(session, [paper_uuid])

        embedding_available = session.execute(
            select(func.count()).select_from(PaperEmbedding).where(
                PaperEmbedding.paper_id == paper_uuid,
                PaperEmbedding.embedding_status == "SUCCEEDED",
                PaperEmbedding.embedding_model == config.EMBEDDING_MODEL_NAME,
                PaperEmbedding.model_version == config.EMBEDDING_MODEL_REVISION,
            )
        ).scalar_one() > 0

        return {
            "paper_id": str(paper.id),
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": authors_by_paper.get(paper_uuid, []),
            "primary_category": row.category_display_name or row.category_code,
            "publication_date": row.publication_date,
            "current_version_number": paper.current_version_number,
            "embedding_available": embedding_available,
        }
    finally:
        session.close()


def list_categories() -> list[dict]:
    """Read-only. One row per category with at least one canonical paper,
    ordered by paper_count descending then code ascending -- categories with
    zero canonical papers are omitted (this lists what's actually available
    in the corpus, not the full categories table). Grouped by Category.id
    rather than by code alone: the categories table's uniqueness is scoped
    to (taxonomy_source, code), so two rows could in principle share the
    same code text under different sources."""
    session = SessionLocal()
    try:
        rows = session.execute(
            select(
                Category.code,
                Category.display_name,
                func.count(Paper.id).label("paper_count"),
            )
            .join(Paper, Paper.primary_category_id == Category.id)
            .where(Paper.is_canonical.is_(True))
            .group_by(Category.id, Category.code, Category.display_name)
            .order_by(func.count(Paper.id).desc(), Category.code.asc())
        ).all()
        return [
            {"code": r.code, "display_name": r.display_name or r.code, "paper_count": r.paper_count}
            for r in rows
        ]
    finally:
        session.close()
