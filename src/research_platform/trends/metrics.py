"""Pure, deterministic publication-trend metrics: growth rate, publication
share, momentum, acceleration, consistency, recency, and minimum-support
gating. No database access, no I/O, no randomness -- every function here is
a plain calculation over already-known counts, so it can be unit tested in
total isolation and reused by any future pipeline without touching a
session. Implements the formulas in the approved Research Trend Analysis
v1 design, section 6.
"""
import math
from typing import NamedTuple, Sequence

DEFAULT_MIN_SUPPORT_TOTAL = 5
DEFAULT_MIN_SUPPORT_PERIOD = 3
DEFAULT_RECENCY_DECAY_DAYS = 90.0


class GrowthRateResult(NamedTuple):
    growth_rate: float | None
    is_new_activity: bool


def _validate_count(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer; got {value!r}")


def compute_growth_rate(recent_count: int, previous_count: int) -> GrowthRateResult:
    """previous_count > 0: standard percentage change. previous_count == 0
    and recent_count == 0: flat -- growth_rate is a real 0.0, not "unknown".
    previous_count == 0 and recent_count > 0: mathematically undefined
    (division by zero) -- reported as growth_rate=None with
    is_new_activity=True rather than a fabricated +inf or an arbitrarily
    large placeholder percentage."""
    _validate_count(recent_count, "recent_count")
    _validate_count(previous_count, "previous_count")
    if previous_count > 0:
        return GrowthRateResult(growth_rate=(recent_count - previous_count) / previous_count, is_new_activity=False)
    if recent_count == 0:
        return GrowthRateResult(growth_rate=0.0, is_new_activity=False)
    return GrowthRateResult(growth_rate=None, is_new_activity=True)


def compute_absolute_growth(recent_count: int, previous_count: int) -> int:
    _validate_count(recent_count, "recent_count")
    _validate_count(previous_count, "previous_count")
    return recent_count - previous_count


def compute_publication_share(entity_count: int, total_count: int) -> float | None:
    """None when total_count == 0 -- there is no "share of nothing"."""
    _validate_count(entity_count, "entity_count")
    _validate_count(total_count, "total_count")
    if entity_count > total_count:
        raise ValueError(f"entity_count ({entity_count}) cannot exceed total_count ({total_count})")
    if total_count == 0:
        return None
    return entity_count / total_count


def compute_share_change(recent_share: float | None, previous_share: float | None) -> float | None:
    if recent_share is None or previous_share is None:
        return None
    return recent_share - previous_share


def normalize_growth_rate(growth_rate: float | None) -> float:
    """Maps a growth rate onto a bounded 0..1 scale: -100% or worse -> 0.0,
    flat 0% -> 0.25, +300% or better -> 1.0 (clamped beyond those bounds).
    None (undefined/new-activity growth rate) maps to 0.5 -- neutral,
    neither a reward nor a penalty for "unknown". Shared by
    compute_momentum() below and scoring.growth_rate_component() so the two
    never drift into different treatments of the same undefined case."""
    if growth_rate is None:
        return 0.5
    clamped = max(-1.0, min(3.0, growth_rate))
    return (clamped + 1.0) / 4.0


def compute_momentum(
    recent_count: int,
    growth_rate: float | None,
    max_recent_count: int,
    *,
    volume_weight: float = 0.5,
    growth_weight: float = 0.5,
) -> float:
    """0..1 blend of raw recent volume and growth rate -- deliberately not
    growth rate alone, so an entity with real recent volume but an
    undefined growth_rate (no prior-period baseline, e.g. a brand-new
    cluster) still registers momentum instead of the growth term zeroing
    the whole thing out."""
    _validate_count(recent_count, "recent_count")
    _validate_count(max_recent_count, "max_recent_count")
    if recent_count > max_recent_count:
        raise ValueError(f"recent_count ({recent_count}) cannot exceed max_recent_count ({max_recent_count})")
    normalized_volume = recent_count / max_recent_count if max_recent_count > 0 else 0.0
    normalized_growth = normalize_growth_rate(growth_rate)
    return volume_weight * normalized_volume + growth_weight * normalized_growth


def compute_acceleration(growth_rate_sequence: Sequence[float | None]) -> bool | None:
    """True/False only when at least 3 consecutive non-null growth rates
    are available, oldest-first -- otherwise None. Acceleration is never
    inferred from 1-2 data points."""
    if len(growth_rate_sequence) < 3:
        return None
    last_three = list(growth_rate_sequence[-3:])
    if any(value is None for value in last_three):
        return None
    return last_three[0] < last_three[1] < last_three[2]


def compute_consistency(active_window_flags: Sequence[bool]) -> float:
    """Fraction of the given past windows in which the entity had any
    activity (recent_count > 0). Rewards entities that show up repeatedly
    over a single spike."""
    if not active_window_flags:
        raise ValueError("active_window_flags must not be empty")
    return sum(1 for flag in active_window_flags if flag) / len(active_window_flags)


def compute_recency(days_since_last_paper: int, *, decay_days: float = DEFAULT_RECENCY_DECAY_DAYS) -> float:
    if not isinstance(days_since_last_paper, int) or isinstance(days_since_last_paper, bool) or days_since_last_paper < 0:
        raise ValueError(f"days_since_last_paper must be a non-negative integer; got {days_since_last_paper!r}")
    if decay_days <= 0:
        raise ValueError(f"decay_days must be positive; got {decay_days!r}")
    return math.exp(-days_since_last_paper / decay_days)


def meets_minimum_total_support(total_papers: int, *, min_support_total: int = DEFAULT_MIN_SUPPORT_TOTAL) -> bool:
    _validate_count(total_papers, "total_papers")
    return total_papers >= min_support_total


def meets_minimum_period_support(period_count: int, *, min_support_period: int = DEFAULT_MIN_SUPPORT_PERIOD) -> bool:
    _validate_count(period_count, "period_count")
    return period_count >= min_support_period
