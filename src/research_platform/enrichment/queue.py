from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from research_platform.db.models import EnrichmentQueue

QUEUE_RULE_VERSION = "enrichment_queue_v1"

# Priority order per the approved Semantic Scholar priority list (lower
# number = processed first). SEMANTIC_SCHOLAR_FALLBACK is a generic
# catch-all for "needs S2 fallback" when the specific OpenAlex outcome
# isn't distinguished by the caller; it shares OPENALEX_AMBIGUOUS's tier
# as a reasonable default.
PRIORITY_BY_REASON = {
    "OPENALEX_NOT_FOUND": 1,
    "OPENALEX_AMBIGUOUS": 2,
    "SEMANTIC_SCHOLAR_FALLBACK": 2,
    "HISTORICAL_CANDIDATE": 3,
    "HIGH_PRIORITY_PAPER": 4,
    "USER_FACING": 4,
    "PERIODIC_REFRESH": 5,
}

ACTIVE_STATUSES = ("PENDING", "IN_PROGRESS", "RETRY_SCHEDULED")
TERMINAL_STATUSES = ("MATCHED", "AMBIGUOUS", "NOT_FOUND", "FAILED", "DEFERRED")

# Retry-policy defaults (first-pass; reasonable to promote to config.py
# once these are tuned against real queue behavior, not done here).
RECENT_PAPER_AGE_DAYS_THRESHOLD = 30
RECENT_NOT_FOUND_RETRY_DAYS = 5
OLD_NOT_FOUND_RETRY_DAYS = 30
TEMPORARY_FAILURE_RETRY_HOURS = 4
MAX_ATTEMPTS_BEFORE_DEFER = 5


def enqueue(session, paper_id, source: str, reason: str, requested_fields: str = "identity_only") -> EnrichmentQueue:
    """Idempotent: one row per (paper_id, source). A paper qualifying for a
    new reason updates the existing row (priority escalated only if the new
    reason outranks the current one, reason recorded in contributing_reasons)
    rather than creating a second active job. A previously-terminal item
    (except MATCHED) is reactivated to PENDING when a new reason arrives;
    MATCHED items are left alone per 'do not repeat identity lookup
    unnecessarily'."""
    if reason not in PRIORITY_BY_REASON:
        raise ValueError(f"unknown enrichment_queue reason: {reason!r}")
    priority = PRIORITY_BY_REASON[reason]
    now = datetime.now(timezone.utc)

    existing = session.execute(
        select(EnrichmentQueue).where(EnrichmentQueue.paper_id == paper_id, EnrichmentQueue.source == source)
    ).scalar_one_or_none()

    if existing is None:
        item = EnrichmentQueue(
            paper_id=paper_id,
            source=source,
            priority=priority,
            reason=reason,
            contributing_reasons=[{"reason": reason, "added_at": now.isoformat(), "priority": priority}],
            status="PENDING",
            requested_fields=requested_fields,
            rule_version=QUEUE_RULE_VERSION,
        )
        session.add(item)
        session.flush()
        return item

    reasons = list(existing.contributing_reasons or [])
    if not any(r.get("reason") == reason for r in reasons):
        reasons.append({"reason": reason, "added_at": now.isoformat(), "priority": priority})
        existing.contributing_reasons = reasons

    if priority < existing.priority:
        existing.priority = priority
        existing.reason = reason

    if requested_fields == "full_detail":
        existing.requested_fields = "full_detail"

    if existing.status not in ("MATCHED", "IN_PROGRESS"):
        existing.status = "PENDING"
        existing.next_retry_at = None

    existing.updated_at = now
    session.add(existing)
    session.flush()
    return existing


def select_ready_items(session, source: str, limit: int = 25) -> list[EnrichmentQueue]:
    now = datetime.now(timezone.utc)
    return (
        session.execute(
            select(EnrichmentQueue)
            .where(
                EnrichmentQueue.source == source,
                EnrichmentQueue.status.in_(("PENDING", "RETRY_SCHEDULED")),
                (EnrichmentQueue.next_retry_at.is_(None)) | (EnrichmentQueue.next_retry_at <= now),
            )
            .order_by(EnrichmentQueue.priority.asc(), EnrichmentQueue.created_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def mark_in_progress(session, item: EnrichmentQueue) -> None:
    now = datetime.now(timezone.utc)
    item.status = "IN_PROGRESS"
    item.attempt_count += 1
    item.last_attempted_at = now
    item.updated_at = now
    session.add(item)


def mark_matched(session, item: EnrichmentQueue) -> None:
    """MATCHED is treated as terminal: subsequent enqueue() calls for this
    (paper_id, source) will not reactivate it, satisfying 'do not repeat
    identity lookup unnecessarily'."""
    now = datetime.now(timezone.utc)
    item.status = "MATCHED"
    item.last_success_at = now
    item.next_retry_at = None
    item.failure_reason = None
    item.updated_at = now
    session.add(item)


def mark_ambiguous(session, item: EnrichmentQueue) -> None:
    now = datetime.now(timezone.utc)
    item.status = "AMBIGUOUS"
    item.next_retry_at = None
    item.updated_at = now
    session.add(item)


def mark_not_found(session, item: EnrichmentQueue, paper_age_days: float | None) -> None:
    now = datetime.now(timezone.utc)
    retry_days = (
        RECENT_NOT_FOUND_RETRY_DAYS
        if paper_age_days is not None and paper_age_days <= RECENT_PAPER_AGE_DAYS_THRESHOLD
        else OLD_NOT_FOUND_RETRY_DAYS
    )
    item.status = "RETRY_SCHEDULED"
    item.next_retry_at = now + timedelta(days=retry_days)
    item.failure_reason = "not_found"
    item.updated_at = now
    session.add(item)


def mark_temporary_failure(session, item: EnrichmentQueue, failure_reason: str) -> None:
    """For failures where the client already exhausted its own
    exponential-backoff retry budget (pacing.py) within a single attempt --
    this schedules the whole paper for a later re-attempt, coarser-grained
    than that per-request backoff, and does not bypass or duplicate the
    shared pacing state in any way."""
    now = datetime.now(timezone.utc)
    if item.attempt_count >= MAX_ATTEMPTS_BEFORE_DEFER:
        item.status = "DEFERRED"
        item.next_retry_at = None
    else:
        item.status = "RETRY_SCHEDULED"
        item.next_retry_at = now + timedelta(hours=TEMPORARY_FAILURE_RETRY_HOURS)
    item.failure_reason = failure_reason
    item.updated_at = now
    session.add(item)


def mark_permanent_failure(session, item: EnrichmentQueue, failure_reason: str) -> None:
    now = datetime.now(timezone.utc)
    item.status = "FAILED"
    item.next_retry_at = None
    item.failure_reason = failure_reason
    item.updated_at = now
    session.add(item)
