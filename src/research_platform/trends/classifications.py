"""Deterministic classification of a computed trend into one of six
labels, plus the fixed label vocabulary for trend-mode/freshness states and
data-quality levels. No database access, no LLM calls -- every string
returned here comes from a fixed lookup or an ordered rule table, never
free-text generation, so it can never drift into a banned phrase (see
BANNED_HISTORICAL_PHRASES). Implements the approved Research Trend
Analysis v1 design, sections 7.4 and 11.2, as revised: the two-cohort
(2016-batch vs. 2026-batch) comparison is always labeled "Historical Cohort
Comparison" -- never "continuous historical trend", "current momentum",
"year-over-year ... growth", or "trending now".
"""
from research_platform.trends.freshness import (
    CURRENT_OK,
    CURRENT_UNAVAILABLE,
    HISTORICAL_OK,
    HISTORICAL_UNAVAILABLE,
)
from research_platform.trends.metrics import DEFAULT_MIN_SUPPORT_PERIOD, DEFAULT_MIN_SUPPORT_TOTAL

# --- Trend classifications (design section 7.4) -----------------------------

EMERGING = "Emerging"
ACCELERATING = "Accelerating"
CONSISTENTLY_ACTIVE = "Consistently Active"
STABLE = "Stable"
COOLING = "Cooling"
INSUFFICIENT_DATA = "Insufficient Data"


def classify_trend(
    *,
    total_papers: int,
    recent_count: int,
    previous_count: int,
    growth_rate: float | None,
    is_new_activity: bool,
    acceleration: bool | None,
    consistency: float,
    min_support_total: int = DEFAULT_MIN_SUPPORT_TOTAL,
    min_support_period: int = DEFAULT_MIN_SUPPORT_PERIOD,
    growth_threshold: float = 0.20,
    stable_band: float = 0.10,
    cooling_threshold: float = -0.20,
    consistency_threshold: float = 0.75,
) -> str:
    """Ordered rule table, first match wins:

    1. total_papers below minimum support           -> Insufficient Data
    2. new activity (previous_count == 0) with
       real recent volume                            -> Emerging
    3. strong positive growth, accelerating,
       with a real comparison-period baseline         -> Accelerating
    4. high consistency with flat-to-moderate growth  -> Consistently Active
    5. flat growth with a real comparison-period
       baseline                                       -> Stable
    6. strong negative growth with a real
       comparison-period baseline                     -> Cooling
    7. otherwise                                       -> Insufficient Data

    This function assumes the caller has already decided a classification
    should be produced for the given (recent_count, previous_count,
    growth_rate) comparison -- it does not know about trend_mode or
    freshness_status. A current-mode request that freshness.
    resolve_trend_request() resolved to CURRENT_UNAVAILABLE must not reach
    this function at all; there is no classification to compute for an
    unavailable current trend, only the unavailable state itself
    (resolve_trend_mode_label(CURRENT_UNAVAILABLE))."""
    if total_papers < min_support_total:
        return INSUFFICIENT_DATA
    if is_new_activity and recent_count >= min_support_period:
        return EMERGING
    if (
        growth_rate is not None
        and growth_rate > growth_threshold
        and acceleration is True
        and previous_count >= min_support_period
    ):
        return ACCELERATING
    if consistency >= consistency_threshold and (growth_rate is None or -stable_band <= growth_rate <= growth_threshold):
        return CONSISTENTLY_ACTIVE
    if growth_rate is not None and -stable_band <= growth_rate <= stable_band and previous_count >= min_support_period:
        return STABLE
    if growth_rate is not None and growth_rate < cooling_threshold and previous_count >= min_support_period:
        return COOLING
    return INSUFFICIENT_DATA


# --- Data quality level (design section 11.2) --------------------------------

HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
INSUFFICIENT = "INSUFFICIENT"


def compute_data_quality_level(
    *,
    total_papers: int,
    previous_count: int,
    recent_period_distinct_days: int,
    recent_window_days: int,
    multi_window_history: bool = False,
    min_support_total: int = DEFAULT_MIN_SUPPORT_TOTAL,
    min_support_period: int = DEFAULT_MIN_SUPPORT_PERIOD,
    concentration_floor_fraction: float = 0.10,
) -> str:
    """How much a trend_score should be trusted, kept explicitly distinct
    from the score itself: a real spike can still be LOW-quality (e.g. all
    on one calendar day), and a modest score can be HIGH-quality (broad,
    well-supported history)."""
    if total_papers < min_support_total:
        return INSUFFICIENT
    if recent_window_days <= 0:
        raise ValueError(f"recent_window_days must be positive; got {recent_window_days!r}")
    if not (0 <= recent_period_distinct_days <= recent_window_days):
        raise ValueError("recent_period_distinct_days must be between 0 and recent_window_days")
    concentrated = (recent_period_distinct_days / recent_window_days) < concentration_floor_fraction
    if previous_count < min_support_period or concentrated:
        return LOW
    if multi_window_history:
        return HIGH
    return MEDIUM


# --- Trend-mode / freshness label vocabulary (design section 3.4, revised) --

CURRENT_TRENDS_LABEL = "Trending Now"
HISTORICAL_COHORT_COMPARISON_LABEL = "Historical Cohort Comparison"
CURRENT_UNAVAILABLE_LABEL = "Current Trends Unavailable"
HISTORICAL_UNAVAILABLE_LABEL = "Insufficient Data For Historical Comparison"

# Phrasing that must never appear in any label or generated description of a
# two-cohort (2016-batch vs. 2026-batch) comparison. Enforced by
# construction here (the labels below are a fixed lookup, never assembled
# from free text) and asserted directly in tests.
BANNED_HISTORICAL_PHRASES = (
    "continuous historical trend",
    "current momentum",
    "year-over-year",
    "trending now",
)

_MODE_LABELS = {
    CURRENT_OK: CURRENT_TRENDS_LABEL,
    HISTORICAL_OK: HISTORICAL_COHORT_COMPARISON_LABEL,
    CURRENT_UNAVAILABLE: CURRENT_UNAVAILABLE_LABEL,
    HISTORICAL_UNAVAILABLE: HISTORICAL_UNAVAILABLE_LABEL,
}


def resolve_trend_mode_label(resolved_state: str) -> str:
    """Fixed lookup, one label per freshness.resolve_trend_request()
    outcome. HISTORICAL_OK always maps to "Historical Cohort Comparison"
    -- the only label ever used for the 2016-batch-vs-2026-batch
    comparison this corpus can currently produce."""
    if resolved_state not in _MODE_LABELS:
        raise ValueError(f"unknown resolved_state: {resolved_state!r}")
    return _MODE_LABELS[resolved_state]
