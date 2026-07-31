from datetime import datetime, timezone

from sqlalchemy import func, select

from research_platform.config import ARXIV_DEFAULT_PAGE_SIZE
from research_platform.db.models import BackfillWindow, IngestionQuotaPeriod, Paper
from research_platform.db.session import SessionLocal, engine
from research_platform.ingestion.advisory_lock import try_acquire_arxiv_lock
from research_platform.ingestion.arxiv_client import (
    build_date_range_query,
    fetch_by_categories,
    fetch_by_search_query,
)
from research_platform.ingestion.backfill_planner import APPROVED_CATEGORIES
from research_platform.ingestion.normalize import parse_entry, try_extract_arxiv_id
from research_platform.ingestion.run_tracker import IngestionRunTracker
from research_platform.ingestion.upsert import upsert_paper

DEFAULT_NEW_QUEUE_LOOKAHEAD = 30


def _process_new_queue(session, remaining_quota: int, lookahead: int, tracker: IngestionRunTracker):
    """Fetches up to `lookahead` most-recent candidates (one API call,
    independent of quota), determines how many are not yet in the database
    ("available"), and processes up to `remaining_quota` of them. Returns
    (attempted_count, available_count)."""
    if remaining_quota <= 0:
        return 0, 0

    entries = fetch_by_categories(session, APPROVED_CATEGORIES, max_results=lookahead)

    candidates = []
    for entry in entries:
        arxiv_id = try_extract_arxiv_id(entry)
        if arxiv_id is None:
            candidates.append(entry)
            continue
        exists = session.execute(select(Paper.id).where(Paper.arxiv_id == arxiv_id)).scalar_one_or_none()
        if exists is None:
            candidates.append(entry)

    available = len(candidates)
    selected_entries = candidates[:remaining_quota]

    for entry in selected_entries:
        tracker.record_processed()
        arxiv_id_for_log = try_extract_arxiv_id(entry)
        try:
            parsed = parse_entry(entry)
            _, created = upsert_paper(session, parsed)
            session.commit()
            if created:
                tracker.record_created()
            else:
                tracker.record_updated()
        except Exception as exc:
            session.rollback()
            tracker.log_failure(
                source="arxiv",
                error_type=type(exc).__name__,
                error_message=str(exc),
                source_identifier=arxiv_id_for_log,
            )

    return len(selected_entries), available


def _process_historical_queue(session, remaining_quota: int, page_size: int, tracker: IngestionRunTracker):
    """Pulls from the oldest incomplete backfill window(s), paginating with
    a durable checkpoint. Paper upserts and checkpoint advancement for a
    page are committed together, atomically. A page-fetch failure (after
    the client's own retries are exhausted) stops historical processing
    without advancing the checkpoint, so a later run resumes the same page.

    Historical prioritization here uses only "oldest incomplete window".
    Category-coverage and missing-period prioritization are not implemented
    in this phase. Foundational importance cannot yet be measured reliably
    because OpenAlex/Semantic Scholar enrichment does not exist yet -- this
    is a known, documented limitation of Phase 1, not an oversight.
    """
    historical_selected = 0
    stopped_early = False

    while remaining_quota > 0:
        window = session.execute(
            select(BackfillWindow)
            .where(BackfillWindow.status.in_(["PLANNED", "RUNNING"]))
            .order_by(BackfillWindow.window_start.asc())
            .limit(1)
        ).scalar_one_or_none()
        if window is None:
            break  # no more planned historical work available

        effective_page_size = min(page_size, remaining_quota)
        query = build_date_range_query(APPROVED_CATEGORIES, window.window_start, window.window_end)

        try:
            entries = fetch_by_search_query(
                session, query, max_results=effective_page_size, start=window.next_page_offset
            )
        except Exception as exc:
            tracker.log_failure(
                source="arxiv",
                error_type=type(exc).__name__,
                error_message=f"page fetch failed for window {window.id} at offset {window.next_page_offset}: {exc}",
                source_identifier=str(window.id),
            )
            stopped_early = True
            break  # checkpoint (next_page_offset) is NOT advanced

        if window.status == "PLANNED":
            window.status = "RUNNING"

        committed_count = 0
        for entry in entries:
            tracker.record_processed()
            try:
                with session.begin_nested():
                    parsed = parse_entry(entry)
                    _, created = upsert_paper(session, parsed)
                if created:
                    tracker.record_created()
                else:
                    tracker.record_updated()
                committed_count += 1
            except Exception as exc:
                tracker.stage_failure(
                    source="arxiv",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    source_identifier=try_extract_arxiv_id(entry),
                )

        window.next_page_offset += len(entries)
        window.records_committed += committed_count
        window.updated_at = datetime.now(timezone.utc)
        if len(entries) < effective_page_size or window.records_committed >= (window.estimated_result_count or 0):
            window.status = "COMPLETED"
            window.completed_at = datetime.now(timezone.utc)
        session.add(window)
        session.commit()  # atomic: paper upserts + staged failures + checkpoint advancement

        historical_selected += len(entries)
        remaining_quota -= len(entries)

        if len(entries) == 0:
            break  # nothing left in this window; avoid spinning

    return historical_selected, stopped_early


def run_quota_ingestion(
    quota_limit: int,
    page_size: int = ARXIV_DEFAULT_PAGE_SIZE,
    new_queue_lookahead: int = DEFAULT_NEW_QUEUE_LOOKAHEAD,
) -> dict:
    with try_acquire_arxiv_lock(engine) as acquired:
        if not acquired:
            print(
                "Another arXiv collection worker already holds the advisory lock; "
                "exiting without starting a new run (not a data-processing failure)."
            )
            return {"status": "lock_held"}

        session = SessionLocal()
        try:
            config_snapshot = {
                "quota_limit": quota_limit,
                "page_size": page_size,
                "new_queue_lookahead": new_queue_lookahead,
            }
            quota_period = IngestionQuotaPeriod(
                period_start=datetime.now(timezone.utc),
                quota_limit=quota_limit,
                status="RUNNING",
                config_snapshot=config_snapshot,
            )
            session.add(quota_period)
            session.commit()

            historical_available = session.execute(
                select(
                    func.coalesce(
                        func.sum(BackfillWindow.estimated_result_count - BackfillWindow.records_committed), 0
                    )
                ).where(BackfillWindow.status.in_(["PLANNED", "RUNNING"]))
            ).scalar_one()

            remaining = quota_limit
            with IngestionRunTracker(
                session, job_type="arxiv_quota_ingestion", config_snapshot=config_snapshot
            ) as tracker:
                new_selected, new_available = _process_new_queue(session, remaining, new_queue_lookahead, tracker)
                remaining -= new_selected

                historical_selected, stopped_early = _process_historical_queue(session, remaining, page_size, tracker)
                remaining -= historical_selected

                tracker.set_cursor({"note": "quota execution run", "unused_capacity": remaining})

            quota_period.new_papers_available = new_available
            quota_period.historical_papers_available = int(historical_available)
            quota_period.new_papers_selected = new_selected
            quota_period.historical_papers_selected = historical_selected
            quota_period.papers_processed = tracker.processed
            quota_period.papers_failed = tracker.failed
            quota_period.unused_capacity = remaining
            quota_period.status = "FAILED" if stopped_early else "COMPLETED"
            quota_period.period_end = datetime.now(timezone.utc)
            quota_period.completed_at = quota_period.period_end
            session.add(quota_period)
            session.commit()

            return {
                "status": "lock_acquired",
                "quota_period_id": str(quota_period.id),
                "quota_period_status": quota_period.status,
                "run_id": str(tracker.run.id),
                "run_status": tracker.run.status,
                "quota_limit": quota_limit,
                "new_papers_available": new_available,
                "new_papers_selected": new_selected,
                "historical_papers_available": int(historical_available),
                "historical_papers_selected": historical_selected,
                "papers_processed": tracker.processed,
                "papers_failed": tracker.failed,
                "unused_capacity": remaining,
                "stopped_early": stopped_early,
            }
        finally:
            session.close()
