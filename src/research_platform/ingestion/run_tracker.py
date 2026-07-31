from datetime import datetime, timezone

from research_platform.db.models import IngestionFailure, IngestionRun


class IngestionRunTracker:
    """Wraps one ingestion job execution: creates the ingestion_runs row,
    tracks counters in memory, logs per-record failures immediately without
    aborting the run, and finalizes status/counters/cursor on exit.
    """

    def __init__(self, session, job_type: str, config_snapshot: dict, cursor: dict | None = None):
        self.session = session
        self.job_type = job_type
        self.config_snapshot = config_snapshot
        self.cursor = cursor
        self.processed = 0
        self.created = 0
        self.updated = 0
        self.failed = 0
        self.run: IngestionRun | None = None

    def __enter__(self) -> "IngestionRunTracker":
        self.run = IngestionRun(
            job_type=self.job_type,
            config_snapshot=self.config_snapshot,
            cursor=self.cursor,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(self.run)
        self.session.commit()
        return self

    def record_processed(self, n: int = 1) -> None:
        self.processed += n

    def record_created(self, n: int = 1) -> None:
        self.created += n

    def record_updated(self, n: int = 1) -> None:
        self.updated += n

    def set_cursor(self, cursor: dict) -> None:
        self.cursor = cursor

    def log_failure(
        self,
        source: str,
        error_type: str,
        error_message: str,
        source_identifier: str | None = None,
        raw_payload: dict | None = None,
    ) -> None:
        """Records a per-record failure without raising. Uses its own
        commit so a caller who already rolled back a failed unit of work
        can still persist the failure record cleanly."""
        self.failed += 1
        failure = IngestionFailure(
            ingestion_run_id=self.run.id,
            source=source,
            source_identifier=source_identifier,
            error_type=error_type,
            error_message=error_message,
            raw_payload=raw_payload,
            occurred_at=datetime.now(timezone.utc),
        )
        self.session.add(failure)
        self.session.commit()

    def stage_failure(
        self,
        source: str,
        error_type: str,
        error_message: str,
        source_identifier: str | None = None,
        raw_payload: dict | None = None,
    ) -> None:
        """Like log_failure, but adds the IngestionFailure row to the
        session WITHOUT committing. Used by callers that need the failure
        record to land in the same atomic commit as other page-level work
        (e.g. paper upserts + checkpoint advancement) rather than its own
        eager transaction."""
        self.failed += 1
        failure = IngestionFailure(
            ingestion_run_id=self.run.id,
            source=source,
            source_identifier=source_identifier,
            error_type=error_type,
            error_message=error_message,
            raw_payload=raw_payload,
            occurred_at=datetime.now(timezone.utc),
        )
        self.session.add(failure)

    def __exit__(self, exc_type, exc, tb) -> None:
        self.session.rollback()  # clear any dangling failed transaction state
        if exc_type is not None:
            status = "failed"
        elif self.failed > 0:
            status = "partial"
        else:
            status = "succeeded"

        self.run.status = status
        self.run.records_processed = self.processed
        self.run.records_created = self.created
        self.run.records_updated = self.updated
        self.run.records_failed = self.failed
        self.run.cursor = self.cursor
        self.run.completed_at = datetime.now(timezone.utc)
        self.session.add(self.run)
        self.session.commit()
        # do not suppress exceptions raised inside the with-block
