import random
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from research_platform.config import (
    ARXIV_BASE_DELAY_SECONDS,
    ARXIV_JITTER_MAX_SECONDS,
    ARXIV_MAX_COOLDOWN_SECONDS,
    ARXIV_RATE_LIMIT_BASELINE_SECONDS,
    ARXIV_TEMPORARY_ERROR_BASELINE_SECONDS,
)
from research_platform.db.models import ApiRequestState


def _get_or_create_state(session, source: str) -> ApiRequestState:
    state = session.execute(
        select(ApiRequestState).where(ApiRequestState.source == source).with_for_update()
    ).scalar_one_or_none()
    if state is None:
        state = ApiRequestState(source=source)
        session.add(state)
        session.flush()
    return state


def wait_for_slot(session, source: str) -> float:
    """Blocks until the shared, DB-persisted pacing state says it's safe to
    make the next request for this source. Returns the number of seconds
    actually slept (for observability/testing). Source-agnostic: reads
    whatever next_allowed_at/cooldown_until the last record_* call for this
    source computed, so callers don't need to pass their own constants here."""
    state = _get_or_create_state(session, source)
    session.commit()  # release the row lock before sleeping

    now = datetime.now(timezone.utc)
    earliest = state.next_allowed_at
    if state.cooldown_until and (earliest is None or state.cooldown_until > earliest):
        earliest = state.cooldown_until

    if earliest and earliest > now:
        sleep_seconds = (earliest - now).total_seconds()
        time.sleep(max(0.0, sleep_seconds))
        return max(0.0, sleep_seconds)
    return 0.0


def record_success(
    session,
    source: str,
    base_delay: float = ARXIV_BASE_DELAY_SECONDS,
    jitter_max: float = ARXIV_JITTER_MAX_SECONDS,
) -> None:
    state = _get_or_create_state(session, source)
    now = datetime.now(timezone.utc)
    jitter = random.uniform(0, jitter_max)
    state.last_request_at = now
    state.next_allowed_at = now + timedelta(seconds=base_delay + jitter)
    state.cooldown_until = None
    state.consecutive_failures = 0
    state.updated_at = now
    session.add(state)
    session.commit()


def record_permanent_error(session, source: str, base_delay: float = ARXIV_BASE_DELAY_SECONDS) -> None:
    """A permanent error (e.g. HTTP 400) still consumed a request slot, but
    is not a rate/availability problem, so no cooldown escalation applies."""
    state = _get_or_create_state(session, source)
    now = datetime.now(timezone.utc)
    state.last_request_at = now
    state.next_allowed_at = now + timedelta(seconds=base_delay)
    state.updated_at = now
    session.add(state)
    session.commit()


def _apply_backoff(
    session,
    source: str,
    baseline_seconds: float,
    retry_after: float | None,
    max_cooldown: float,
    jitter_max: float,
) -> float:
    state = _get_or_create_state(session, source)
    now = datetime.now(timezone.utc)
    state.consecutive_failures = (state.consecutive_failures or 0) + 1

    if retry_after is not None:
        cooldown = retry_after
    else:
        cooldown = baseline_seconds * (2 ** (state.consecutive_failures - 1))
    cooldown = min(cooldown, max_cooldown) + random.uniform(0, jitter_max)

    state.last_request_at = now
    state.cooldown_until = now + timedelta(seconds=cooldown)
    state.next_allowed_at = state.cooldown_until
    state.updated_at = now
    session.add(state)
    session.commit()
    return cooldown


def record_rate_limited(
    session,
    source: str,
    retry_after_header: str | None,
    baseline_seconds: float = ARXIV_RATE_LIMIT_BASELINE_SECONDS,
    max_cooldown: float = ARXIV_MAX_COOLDOWN_SECONDS,
    jitter_max: float = ARXIV_JITTER_MAX_SECONDS,
) -> float:
    retry_after = None
    if retry_after_header is not None:
        try:
            retry_after = float(retry_after_header)
        except ValueError:
            retry_after = None
    return _apply_backoff(
        session, source, baseline_seconds=baseline_seconds, retry_after=retry_after,
        max_cooldown=max_cooldown, jitter_max=jitter_max,
    )


def record_temporary_failure(
    session,
    source: str,
    baseline_seconds: float = ARXIV_TEMPORARY_ERROR_BASELINE_SECONDS,
    max_cooldown: float = ARXIV_MAX_COOLDOWN_SECONDS,
    jitter_max: float = ARXIV_JITTER_MAX_SECONDS,
) -> float:
    return _apply_backoff(
        session, source, baseline_seconds=baseline_seconds, retry_after=None,
        max_cooldown=max_cooldown, jitter_max=jitter_max,
    )
