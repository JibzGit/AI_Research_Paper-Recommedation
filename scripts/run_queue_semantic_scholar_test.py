"""Controlled test: process a fixed list of enrichment_queue rows through
the existing Semantic Scholar client/matcher/storage pipeline, with queue
state transitions wired in around it. Reuses the job's internal helpers
rather than reimplementing matching/storage logic.
"""
import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import select

from research_platform.db.models import EnrichmentQueue, Paper
from research_platform.db.session import SessionLocal
from research_platform.enrichment import queue as q
from research_platform.enrichment.semantic_scholar_client import (
    SemanticScholarPermanentError,
    SemanticScholarTemporaryError,
)
from research_platform.enrichment.semantic_scholar_enrichment_job import (
    SOURCE,
    _get_author_names,
    _get_publication_year,
    _known_s2_id,
    _store_enrichment_result,
)
from research_platform.enrichment.semantic_scholar_matcher import match_paper
from research_platform.ingestion.run_tracker import IngestionRunTracker


def process_one(session, tracker, queue_item: EnrichmentQueue, paper: Paper) -> dict:
    q.mark_in_progress(session, queue_item)
    session.commit()

    tracker.record_processed()
    try:
        author_names = _get_author_names(session, paper)
        publication_year = _get_publication_year(session, paper)
        known_s2_id = _known_s2_id(session, paper.id)
        result = match_paper(session, paper, author_names, publication_year, known_s2_id)

        with session.begin_nested():
            stats = _store_enrichment_result(session, paper, result)
        session.commit()

        status = stats["match_status"]
        if status == "MATCHED":
            q.mark_matched(session, queue_item)
            tracker.record_updated()
        elif status == "AMBIGUOUS":
            q.mark_ambiguous(session, queue_item)
        elif status == "NOT_FOUND":
            age_days = None
            if paper.first_observed_at:
                age_days = (datetime.now(timezone.utc) - paper.first_observed_at).days
            q.mark_not_found(session, queue_item, age_days)
        elif status == "FAILED":
            # match_paper's own internal FAILED = a temporary/exhausted-retry
            # outcome (SemanticScholarTemporaryError caught inside the
            # matcher), not a Python exception -- queue policy for that is
            # RETRY_SCHEDULED, not a permanent FAILED.
            q.mark_temporary_failure(session, queue_item, failure_reason="semantic_scholar temporary error during match")
        session.commit()
        stats["arxiv_id"] = paper.arxiv_id
        return stats
    except (SemanticScholarPermanentError, Exception) as exc:
        session.rollback()
        tracker.log_failure(
            source=SOURCE, error_type=type(exc).__name__, error_message=str(exc), source_identifier=str(paper.id)
        )
        q.mark_permanent_failure(session, queue_item, failure_reason=f"{type(exc).__name__}: {exc}")
        session.commit()
        return {"arxiv_id": paper.arxiv_id, "match_status": "EXCEPTION", "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arxiv-ids", nargs="+", required=True)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        config_snapshot = {"arxiv_ids": args.arxiv_ids, "source": "enrichment_queue_controlled_test"}
        results = []
        with IngestionRunTracker(
            session, job_type="semantic_scholar_queue_processing", config_snapshot=config_snapshot
        ) as tracker:
            for arxiv_id in args.arxiv_ids:
                paper = session.execute(select(Paper).where(Paper.arxiv_id == arxiv_id)).scalar_one()
                queue_item = session.execute(
                    select(EnrichmentQueue).where(
                        EnrichmentQueue.paper_id == paper.id, EnrichmentQueue.source == "semantic_scholar"
                    )
                ).scalar_one()
                stats = process_one(session, tracker, queue_item, paper)
                results.append(stats)
                print(json.dumps(stats, default=str))

        summary = {
            "run_id": str(tracker.run.id),
            "status": tracker.run.status,
            "processed": tracker.processed,
            "updated": tracker.updated,
            "failed": tracker.failed,
        }
        print(json.dumps(summary, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
