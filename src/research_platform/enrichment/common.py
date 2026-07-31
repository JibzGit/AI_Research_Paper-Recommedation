from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from research_platform.db.models import PaperSourceRecord, PaperSourceRecordIdentifierHistory


def upsert_source_record_with_history(
    session,
    paper_id,
    source: str,
    source_paper_id: str,
    raw_metadata: dict,
    source_url: str | None,
    pdf_url: str | None,
) -> None:
    """Shared by every enrichment job (OpenAlex, Semantic Scholar, and any
    future provider). Upserts on (paper_id, source) -- one source record per
    canonical paper per provider, guaranteed by that unique constraint.

    If the provider returns a source_paper_id that differs from what's
    already stored for this (paper_id, source), that's a real external
    identifier change (e.g. the provider merged/redirected a record) and is
    logged to paper_source_record_identifier_history *before* the update,
    so the old ID is never silently lost. This exact scenario was caught by
    the Semantic Scholar idempotency test (10 -> 11 source records) before
    this function existed.
    """
    now = datetime.now(timezone.utc)

    existing = session.execute(
        select(PaperSourceRecord).where(
            PaperSourceRecord.paper_id == paper_id, PaperSourceRecord.source == source
        )
    ).scalar_one_or_none()

    if existing is not None and existing.source_paper_id != source_paper_id:
        session.add(
            PaperSourceRecordIdentifierHistory(
                paper_source_record_id=existing.id,
                paper_id=paper_id,
                source=source,
                old_source_paper_id=existing.source_paper_id,
                new_source_paper_id=source_paper_id,
                changed_at=now,
                reason="provider_returned_different_external_id",
            )
        )
        session.flush()

    stmt = pg_insert(PaperSourceRecord).values(
        paper_id=paper_id,
        source=source,
        source_paper_id=source_paper_id,
        raw_metadata=raw_metadata,
        source_url=source_url,
        pdf_url=pdf_url,
        fetched_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["paper_id", "source"],
        set_={
            "source_paper_id": stmt.excluded.source_paper_id,
            "raw_metadata": stmt.excluded.raw_metadata,
            "source_url": stmt.excluded.source_url,
            "pdf_url": stmt.excluded.pdf_url,
            "fetched_at": now,
            "updated_at": now,
        },
    )
    session.execute(stmt)
