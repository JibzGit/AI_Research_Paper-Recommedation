from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from research_platform import config
from research_platform.db.models import Category, Paper, PaperEmbedding
from research_platform.db.session import SessionLocal
from research_platform.embeddings.canonical_text import CanonicalTextResult, build_canonical_text
from research_platform.embeddings.model import encode_documents
from research_platform.ingestion.run_tracker import IngestionRunTracker

SOURCE = "embedding"


def _get_primary_category_display(session, paper: Paper) -> str | None:
    category = session.get(Category, paper.primary_category_id)
    if category is None:
        return None
    return category.display_name or category.code


def select_eligible_papers(
    session,
    limit: int | None = None,
    paper_ids: list | None = None,
    arxiv_ids: list | None = None,
) -> list[Paper]:
    """Canonical papers only (never merged/non-canonical rows). Ordered by
    first_observed_at so an unfiltered run and a --limit-only rerun select
    the same deterministic slice."""
    stmt = select(Paper).where(Paper.is_canonical.is_(True))
    if paper_ids and arxiv_ids:
        stmt = stmt.where(Paper.id.in_(paper_ids) | Paper.arxiv_id.in_(arxiv_ids))
    elif paper_ids:
        stmt = stmt.where(Paper.id.in_(paper_ids))
    elif arxiv_ids:
        stmt = stmt.where(Paper.arxiv_id.in_(arxiv_ids))
    stmt = stmt.order_by(Paper.first_observed_at.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())


def _existing_embedding(session, paper_id) -> PaperEmbedding | None:
    return session.execute(
        select(PaperEmbedding).where(
            PaperEmbedding.paper_id == paper_id,
            PaperEmbedding.embedding_model == config.EMBEDDING_MODEL_NAME,
            PaperEmbedding.model_version == config.EMBEDDING_MODEL_REVISION,
        )
    ).scalar_one_or_none()


def _upsert_embedding_row(
    session,
    paper_id,
    canonical: CanonicalTextResult,
    embedding: list[float] | None,
    status: str,
    failure_reason: str | None,
) -> None:
    """Upserts on the same (paper_id, embedding_model, model_version) unique
    constraint the migration created, so this can never produce a duplicate
    row regardless of the caller's insert-vs-update decision above -- the
    DB constraint is the actual source of truth for uniqueness, this is
    just choosing the right values to write.

    generated_at reflects the last successful generation for the CURRENT
    source_text_hash only: a failed (re)generation clears it (and clears
    embedding) rather than leaving a stale value/vector from a previous,
    now-superseded piece of text -- FAILED rows are never read by search
    (which always filters embedding_status='SUCCEEDED'), but leaving a
    mismatched vector around would be a landmine for any future code path
    that forgets that filter.
    """
    now = datetime.now(timezone.utc)
    values = dict(
        paper_id=paper_id,
        embedding_model=config.EMBEDDING_MODEL_NAME,
        model_version=config.EMBEDDING_MODEL_REVISION,
        embedding_dimension=config.EMBEDDING_DIMENSION,
        embedding=embedding,
        source_text_hash=canonical.source_text_hash,
        embedding_status=status,
        failure_reason=failure_reason,
        generated_at=now if status == "SUCCEEDED" else None,
    )
    stmt = pg_insert(PaperEmbedding).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["paper_id", "embedding_model", "model_version"],
        set_={
            "embedding_dimension": stmt.excluded.embedding_dimension,
            "embedding": stmt.excluded.embedding,
            "source_text_hash": stmt.excluded.source_text_hash,
            "embedding_status": stmt.excluded.embedding_status,
            "failure_reason": stmt.excluded.failure_reason,
            "generated_at": stmt.excluded.generated_at,
            "updated_at": now,
        },
    )
    session.execute(stmt)


def _process_one_paper(session, tracker, paper: Paper) -> dict:
    """Isolates failures per paper: any exception here is caught, logged to
    ingestion_failures, and the loop in run_embedding_backfill continues to
    the next paper. Never writes to any `papers` field -- only
    paper_embeddings rows are ever touched."""
    result = {"arxiv_id": paper.arxiv_id, "paper_id": str(paper.id), "outcome": None}

    try:
        category_display = _get_primary_category_display(session, paper)
        canonical = build_canonical_text(paper.title, paper.abstract, category_display)
    except Exception as exc:
        # No valid source_text_hash exists in this case (canonical text
        # itself couldn't be built), and source_text_hash is NOT NULL on
        # paper_embeddings, so no row is written here -- only the ingestion
        # failure is logged. Not expected to trigger on current data (every
        # paper has a non-empty title/abstract), but handled without
        # crashing the batch if it ever does.
        tracker.log_failure(
            source=SOURCE, error_type=type(exc).__name__, error_message=str(exc), source_identifier=str(paper.id)
        )
        result["outcome"] = "FAILED"
        result["error"] = str(exc)
        return result

    existing = _existing_embedding(session, paper.id)
    if existing is not None and existing.embedding_status == "SUCCEEDED" and existing.source_text_hash == canonical.source_text_hash:
        result["outcome"] = "SKIPPED"
        result["source_text_hash"] = canonical.source_text_hash
        return result

    # Model call happens outside any SAVEPOINT/transaction -- it makes no
    # session/network calls of its own, but this keeps the same discipline
    # as the OpenAlex/Semantic Scholar jobs (expensive/external work never
    # runs inside a nested transaction).
    try:
        vector = encode_documents([canonical.canonical_text])[0]
        if len(vector) != config.EMBEDDING_DIMENSION:
            raise ValueError(f"expected {config.EMBEDDING_DIMENSION}-dimensional vector, got {len(vector)}")
    except Exception as exc:
        with session.begin_nested():
            _upsert_embedding_row(session, paper.id, canonical, embedding=None, status="FAILED", failure_reason=str(exc))
        session.commit()
        tracker.log_failure(
            source=SOURCE, error_type=type(exc).__name__, error_message=str(exc), source_identifier=str(paper.id)
        )
        result["outcome"] = "FAILED"
        result["error"] = str(exc)
        return result

    with session.begin_nested():
        _upsert_embedding_row(session, paper.id, canonical, embedding=vector, status="SUCCEEDED", failure_reason=None)
    session.commit()

    result["outcome"] = "CREATED" if existing is None else "UPDATED"
    result["source_text_hash"] = canonical.source_text_hash
    return result


def run_embedding_backfill(
    paper_ids: list | None = None,
    arxiv_ids: list | None = None,
    limit: int | None = None,
) -> dict:
    """Never creates a new papers row and never modifies an existing one --
    only paper_embeddings is written. One paper's failure never aborts the
    batch: _process_one_paper catches everything it can identify and moves on."""
    config.validate_embedding_config()
    session = SessionLocal()
    try:
        papers = select_eligible_papers(session, limit=limit, paper_ids=paper_ids, arxiv_ids=arxiv_ids)
        config_snapshot = {
            "embedding_model": config.EMBEDDING_MODEL_NAME,
            "model_version": config.EMBEDDING_MODEL_REVISION,
            "limit": limit,
            "paper_ids": [str(p) for p in paper_ids] if paper_ids else None,
            "arxiv_ids": arxiv_ids,
            "paper_count_selected": len(papers),
        }
        created = updated = skipped = 0
        per_paper_results = []

        with IngestionRunTracker(session, job_type="embedding_backfill", config_snapshot=config_snapshot) as tracker:
            for paper in papers:
                tracker.record_processed()
                result = _process_one_paper(session, tracker, paper)
                per_paper_results.append(result)
                if result["outcome"] == "CREATED":
                    created += 1
                    tracker.record_created()
                elif result["outcome"] == "UPDATED":
                    updated += 1
                    tracker.record_updated()
                elif result["outcome"] == "SKIPPED":
                    skipped += 1
                # FAILED is already counted by tracker.log_failure inside _process_one_paper

        return {
            "run_id": str(tracker.run.id),
            "status": tracker.run.status,
            "attempted": tracker.processed,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "failed": tracker.failed,
            "per_paper": per_paper_results,
        }
    finally:
        session.close()
