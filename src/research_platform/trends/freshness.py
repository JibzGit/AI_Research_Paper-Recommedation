"""Deterministic freshness-status classification and trend-mode
availability resolution. No database access -- every input here (paper
counts, day counts) is assumed already computed by a future queries.py
against the live corpus; this module only decides what those numbers mean.
Implements the approved Research Trend Analysis v1 design, section 3, as
revised: a 'current' trend request is never silently downgraded into a
historical result. When current trends are unavailable, resolve_trend_
request() returns an explicit CURRENT_UNAVAILABLE state that preserves the
freshness_status and a specific reason, and separately flags whether a
historical cohort comparison could be offered alongside it -- a caller
decides whether to attach one; this module never substitutes it in as "the
answer" to a current-mode request.
"""
from typing import NamedTuple

CURRENT = "CURRENT"
PARTIALLY_CURRENT = "PARTIALLY_CURRENT"
HISTORICAL_ONLY = "HISTORICAL_ONLY"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

_VALID_FRESHNESS_STATUSES = {CURRENT, PARTIALLY_CURRENT, HISTORICAL_ONLY, INSUFFICIENT_DATA}

DEFAULT_CORPUS_FLOOR = 30
DEFAULT_STALE_THRESHOLD_DAYS = 180
DEFAULT_COMPARISON_FLOOR = 5
DEFAULT_MIN_SPREAD_FRACTION = 0.10


def _validate_non_negative_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer; got {value!r}")


def compute_freshness_status(
    *,
    total_canonical_papers: int,
    days_since_latest_paper: int,
    recent_period_paper_count: int,
    comparison_period_paper_count: int,
    recent_period_distinct_days: int,
    recent_window_days: int = 90,
    corpus_floor: int = DEFAULT_CORPUS_FLOOR,
    stale_threshold_days: int = DEFAULT_STALE_THRESHOLD_DAYS,
    comparison_floor: int = DEFAULT_COMPARISON_FLOOR,
    min_spread_fraction: float = DEFAULT_MIN_SPREAD_FRACTION,
) -> str:
    """Ordered rule table, first match wins:

    1. total_canonical_papers < corpus_floor        -> INSUFFICIENT_DATA
    2. days_since_latest_paper > stale_threshold_days -> HISTORICAL_ONLY
    3. recent_period_paper_count == 0                -> HISTORICAL_ONLY
    4. comparison_period_paper_count < comparison_floor -> PARTIALLY_CURRENT
    5. recent activity concentrated on very few distinct
       calendar days (an ingestion-batch signature, not an
       organic publication pattern)                  -> PARTIALLY_CURRENT
    6. otherwise                                      -> CURRENT
    """
    for value, name in (
        (total_canonical_papers, "total_canonical_papers"),
        (days_since_latest_paper, "days_since_latest_paper"),
        (recent_period_paper_count, "recent_period_paper_count"),
        (comparison_period_paper_count, "comparison_period_paper_count"),
        (recent_period_distinct_days, "recent_period_distinct_days"),
        (recent_window_days, "recent_window_days"),
    ):
        _validate_non_negative_int(value, name)
    if recent_window_days == 0:
        raise ValueError("recent_window_days must be positive")
    if recent_period_distinct_days > recent_window_days:
        raise ValueError("recent_period_distinct_days cannot exceed recent_window_days")

    if total_canonical_papers < corpus_floor:
        return INSUFFICIENT_DATA
    if days_since_latest_paper > stale_threshold_days:
        return HISTORICAL_ONLY
    if recent_period_paper_count == 0:
        return HISTORICAL_ONLY
    if comparison_period_paper_count < comparison_floor:
        return PARTIALLY_CURRENT
    min_spread_days = max(1, round(min_spread_fraction * recent_window_days))
    if recent_period_distinct_days < min_spread_days:
        return PARTIALLY_CURRENT
    return CURRENT


CURRENT_OK = "CURRENT_OK"
CURRENT_UNAVAILABLE = "CURRENT_UNAVAILABLE"
HISTORICAL_OK = "HISTORICAL_OK"
HISTORICAL_UNAVAILABLE = "HISTORICAL_UNAVAILABLE"

REQUESTED_CURRENT = "current"
REQUESTED_HISTORICAL = "historical"

_CURRENT_UNAVAILABLE_REASONS = {
    PARTIALLY_CURRENT: (
        "the comparison period does not contain enough papers (or recent "
        "activity is too concentrated in a few calendar days) to compute a "
        "reliable current-trend growth rate"
    ),
    HISTORICAL_ONLY: (
        "no papers have been published recently enough for a current-trend "
        "window to contain any data"
    ),
    INSUFFICIENT_DATA: (
        "the corpus does not contain enough canonical papers to support "
        "current-trend analysis"
    ),
}


class TrendModeResolution(NamedTuple):
    requested_trend_mode: str
    resolved_state: str
    freshness_status: str
    reason: str | None
    historical_cohort_available: bool


def resolve_trend_request(requested_trend_mode: str, freshness_status: str) -> TrendModeResolution:
    """A 'current' request resolves to CURRENT_OK only when freshness_status
    == CURRENT; any other freshness_status resolves to the explicit
    CURRENT_UNAVAILABLE state (never HISTORICAL_OK -- a current-mode
    request is never silently answered with a historical result).
    historical_cohort_available tells the caller whether a historical
    comparison could additionally, separately be offered; this function
    does not attach one itself.

    A 'historical' request is honored (HISTORICAL_OK) regardless of
    freshness_status, except when the corpus itself has too few papers for
    any comparison at all (INSUFFICIENT_DATA), which resolves to
    HISTORICAL_UNAVAILABLE."""
    if requested_trend_mode not in (REQUESTED_CURRENT, REQUESTED_HISTORICAL):
        raise ValueError(f"requested_trend_mode must be 'current' or 'historical'; got {requested_trend_mode!r}")
    if freshness_status not in _VALID_FRESHNESS_STATUSES:
        raise ValueError(f"unknown freshness_status: {freshness_status!r}")

    historical_cohort_available = freshness_status != INSUFFICIENT_DATA

    if requested_trend_mode == REQUESTED_CURRENT:
        if freshness_status == CURRENT:
            return TrendModeResolution(requested_trend_mode, CURRENT_OK, freshness_status, None, historical_cohort_available)
        reason = _CURRENT_UNAVAILABLE_REASONS[freshness_status]
        return TrendModeResolution(requested_trend_mode, CURRENT_UNAVAILABLE, freshness_status, reason, historical_cohort_available)

    if freshness_status == INSUFFICIENT_DATA:
        reason = _CURRENT_UNAVAILABLE_REASONS[INSUFFICIENT_DATA]
        return TrendModeResolution(requested_trend_mode, HISTORICAL_UNAVAILABLE, freshness_status, reason, historical_cohort_available)
    return TrendModeResolution(requested_trend_mode, HISTORICAL_OK, freshness_status, None, historical_cohort_available)
