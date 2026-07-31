from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_platform import config
from research_platform.db.models import Author, Category, Paper, PaperAuthor, PaperEmbedding, PaperVersion
from research_platform.db.session import SessionLocal
from research_platform.embeddings.model import encode_query

MIN_TOP_K = 1
MAX_TOP_K = 100


def _is_plain_int(value) -> bool:
    """bool is a subclass of int in Python -- True/False must not silently
    pass an isinstance(x, int) check."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_query(query: str) -> None:
    if query is None or not query.strip():
        raise ValueError("query must not be empty")


def validate_common_filters(
    top_k: int,
    year_from: int | None,
    year_to: int | None,
    min_similarity: float | None,
) -> None:
    """Shared by search_papers() and similar_papers() -- everything except
    the query-specific check, since similar_papers() has no query string."""
    if not _is_plain_int(top_k) or not (MIN_TOP_K <= top_k <= MAX_TOP_K):
        raise ValueError(f"top_k must be an integer from {MIN_TOP_K} to {MAX_TOP_K}; got {top_k!r}")

    if year_from is not None and not _is_plain_int(year_from):
        raise ValueError(f"year_from must be an integer; got {year_from!r}")
    if year_to is not None and not _is_plain_int(year_to):
        raise ValueError(f"year_to must be an integer; got {year_to!r}")
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError(f"year_from ({year_from}) must not be greater than year_to ({year_to})")

    if min_similarity is not None:
        if isinstance(min_similarity, bool) or not isinstance(min_similarity, (int, float)):
            raise ValueError(f"min_similarity must be a number between -1 and 1; got {min_similarity!r}")
        if not (-1 <= min_similarity <= 1):
            raise ValueError(f"min_similarity must be between -1 and 1; got {min_similarity!r}")


def publication_date_subquery():
    """Returns (v1_versions_subquery, publication_date_expr) -- the same
    "v1 submission date, falling back to first_observed_at" convention used
    throughout the enrichment jobs (see semantic_scholar_enrichment_job's
    _get_publication_year). Shared by search_papers() and similar_papers()
    so both apply identical year-filter/publication-date semantics without
    duplicating the JOIN."""
    v1_versions = (
        select(PaperVersion.paper_id.label("paper_id"), PaperVersion.submitted_at.label("submitted_at"))
        .where(PaperVersion.version_number == 1)
        .subquery("v1_versions")
    )
    publication_date_expr = func.coalesce(v1_versions.c.submitted_at, Paper.first_observed_at)
    return v1_versions, publication_date_expr


def rows_to_results(session: Session, rows) -> list[dict]:
    """Shared result-formatting: batched author fetch + the common output
    shape (paper_id, arxiv_id, title, abstract, authors, primary_category,
    publication_date, similarity_score). `rows` must be rows selected with
    exactly the columns built by search_papers()/similar_papers() below."""
    paper_ids = [row.paper_id for row in rows]
    authors_by_paper = fetch_authors_batched(session, paper_ids)

    results = []
    for row in rows:
        results.append(
            {
                "paper_id": str(row.paper_id),
                "arxiv_id": row.arxiv_id,
                "title": row.title,
                "abstract": row.abstract,
                "authors": authors_by_paper.get(row.paper_id, []),
                "primary_category": row.category_display_name or row.category_code,
                "publication_date": row.publication_date,
                "similarity_score": float(row.similarity_score),
            }
        )
    return results


def fetch_authors_batched(session: Session, paper_ids: list) -> dict:
    """One query for every result's authors, ordered by author_order --
    never one query per result."""
    if not paper_ids:
        return {}
    rows = session.execute(
        select(PaperAuthor.paper_id, Author.display_name)
        .join(Author, Author.id == PaperAuthor.author_id)
        .where(PaperAuthor.paper_id.in_(paper_ids))
        .order_by(PaperAuthor.paper_id, PaperAuthor.author_order)
    ).all()
    authors_by_paper: dict = {paper_id: [] for paper_id in paper_ids}
    for paper_id, display_name in rows:
        authors_by_paper[paper_id].append(display_name)
    return authors_by_paper


def search_papers(
    query: str,
    top_k: int = 10,
    category: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    min_similarity: float | None = None,
) -> list[dict]:
    """Exact (sequential-scan) cosine similarity search over the current
    169-paper corpus. Never generates or modifies embeddings, never touches
    `papers`/OpenAlex/Semantic Scholar/citation/metric/queue data -- purely
    read-only. Restricted to embedding_status='SUCCEEDED', the currently
    configured (embedding_model, model_version), and is_canonical papers
    only, so a stale/inactive model version or an unsuccessful/non-canonical
    row can never surface in results.
    """
    _validate_query(query)
    validate_common_filters(top_k, year_from, year_to, min_similarity)
    config.validate_embedding_config()

    query_vector = encode_query(query)

    session = SessionLocal()
    try:
        v1_versions, publication_date_expr = publication_date_subquery()
        distance_expr = PaperEmbedding.embedding.cosine_distance(query_vector)
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
            )
        )

        if category:
            stmt = stmt.where(Category.code == category)
        if year_from is not None:
            stmt = stmt.where(func.extract("year", publication_date_expr) >= year_from)
        if year_to is not None:
            stmt = stmt.where(func.extract("year", publication_date_expr) <= year_to)
        if min_similarity is not None:
            # Applied in SQL (not a post-hoc Python filter) so LIMIT top_k
            # selects the top-k among rows that actually clear the
            # threshold, rather than top-k-then-filter potentially
            # returning fewer than top_k when more qualifying rows exist.
            stmt = stmt.where(similarity_expr >= min_similarity)

        stmt = stmt.order_by(distance_expr.asc()).limit(top_k)

        rows = session.execute(stmt).all()
        return rows_to_results(session, rows)
    finally:
        session.close()
