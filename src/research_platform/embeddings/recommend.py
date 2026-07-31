import uuid

from sqlalchemy import func, select

from research_platform import config
from research_platform.db.models import Category, Paper, PaperEmbedding
from research_platform.db.session import SessionLocal
from research_platform.embeddings.search import (
    publication_date_subquery,
    rows_to_results,
    validate_common_filters,
)


class PaperNotFoundError(ValueError):
    """Raised only when paper_id doesn't match any paper at all. A plain
    ValueError subclass so any existing caller catching ValueError still
    catches this -- but distinct enough that the API layer can map it to
    404 specifically, without string-matching the message (a non-canonical
    paper or a paper with no active embedding both exist and stay a plain
    ValueError -> 400, since the resource itself is real)."""


def _coerce_paper_id(paper_id) -> uuid.UUID:
    if paper_id is None:
        raise ValueError("paper_id must be provided")
    if isinstance(paper_id, uuid.UUID):
        return paper_id
    try:
        return uuid.UUID(str(paper_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"paper_id must be a valid UUID; got {paper_id!r}") from exc


def similar_papers(
    paper_id,
    top_k: int = 10,
    category: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    min_similarity: float | None = None,
) -> list[dict]:
    """Recommends papers similar to an already-embedded canonical paper,
    reusing its existing stored embedding -- never generates a new one.
    Exact (sequential-scan) cosine similarity, same approach as
    search_papers(), reusing its filter validation / publication-date /
    result-formatting helpers rather than duplicating them (loosely coupled
    via a plain one-directional import -- search.py has no knowledge of
    this module). No citation, popularity, recency, personalization, or
    clustering signal is blended in; ranking is pure embedding similarity.
    """
    paper_uuid = _coerce_paper_id(paper_id)
    validate_common_filters(top_k, year_from, year_to, min_similarity)
    config.validate_embedding_config()

    session = SessionLocal()
    try:
        paper = session.get(Paper, paper_uuid)
        if paper is None:
            raise PaperNotFoundError(f"paper not found: {paper_id}")
        if not paper.is_canonical:
            raise ValueError(f"selected paper is not canonical: {paper_id}")

        selected_embedding = session.execute(
            select(PaperEmbedding.embedding).where(
                PaperEmbedding.paper_id == paper_uuid,
                PaperEmbedding.embedding_status == "SUCCEEDED",
                PaperEmbedding.embedding_model == config.EMBEDDING_MODEL_NAME,
                PaperEmbedding.model_version == config.EMBEDDING_MODEL_REVISION,
            )
        ).scalar_one_or_none()
        if selected_embedding is None:
            raise ValueError(
                "selected paper has no active successful embedding for "
                f"{config.EMBEDDING_MODEL_NAME}@{config.EMBEDDING_MODEL_REVISION}: {paper_id}"
            )

        v1_versions, publication_date_expr = publication_date_subquery()
        distance_expr = PaperEmbedding.embedding.cosine_distance(selected_embedding)
        similarity_expr = (1 - distance_expr).label("similarity_score")

        stmt = (
            select(
                Paper.id.label("paper_id"),
                Paper.arxiv_id,
                Paper.title,
                Paper.abstract,
                Category.code.label("category_code"),
                Category.display_name.label("category_display_name"),
                publication_date_expr.label("publication_date"),
                similarity_expr,
            )
            .select_from(PaperEmbedding)
            .join(Paper, Paper.id == PaperEmbedding.paper_id)
            .join(Category, Category.id == Paper.primary_category_id)
            .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
            .where(
                PaperEmbedding.embedding_status == "SUCCEEDED",
                PaperEmbedding.embedding_model == config.EMBEDDING_MODEL_NAME,
                PaperEmbedding.model_version == config.EMBEDDING_MODEL_REVISION,
                Paper.is_canonical.is_(True),
                Paper.id != paper_uuid,  # self-exclusion, applied in SQL before LIMIT
            )
        )

        if category:
            stmt = stmt.where(Category.code == category)
        if year_from is not None:
            stmt = stmt.where(func.extract("year", publication_date_expr) >= year_from)
        if year_to is not None:
            stmt = stmt.where(func.extract("year", publication_date_expr) <= year_to)
        if min_similarity is not None:
            stmt = stmt.where(similarity_expr >= min_similarity)

        stmt = stmt.order_by(distance_expr.asc()).limit(top_k)

        rows = session.execute(stmt).all()
        return rows_to_results(session, rows)
    finally:
        session.close()
