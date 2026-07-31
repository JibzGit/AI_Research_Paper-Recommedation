from research_platform.db.session import SessionLocal
from research_platform.ingestion.arxiv_client import fetch_by_categories
from research_platform.ingestion.normalize import parse_entry, try_extract_arxiv_id
from research_platform.ingestion.run_tracker import IngestionRunTracker
from research_platform.ingestion.upsert import upsert_paper


def run_sample_ingestion(categories: list[str], max_results: int) -> dict:
    """Runs a single, non-incremental arXiv collection pass. Per-entry
    failures are logged to ingestion_failures and do not stop the run;
    only an exception outside the per-entry loop (e.g. the API request
    itself failing) marks the whole run as failed."""
    config_snapshot = {"categories": categories, "max_results": max_results, "mode": "sample"}
    session = SessionLocal()
    try:
        with IngestionRunTracker(
            session, job_type="arxiv_sample_ingestion", config_snapshot=config_snapshot
        ) as tracker:
            entries = fetch_by_categories(session, categories, max_results)
            for entry in entries:
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
            tracker.set_cursor(
                {"categories": categories, "max_results": max_results, "note": "sample run, not incremental"}
            )

        return {
            "run_id": str(tracker.run.id),
            "status": tracker.run.status,
            "processed": tracker.processed,
            "created": tracker.created,
            "updated": tracker.updated,
            "failed": tracker.failed,
        }
    finally:
        session.close()
