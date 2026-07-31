"""Deterministic 0-100 trend score: combines metrics.py's normalized
component values under fixed weights, then applies a multiplicative
minimum-support penalty so a low-total-paper entity can never reach a high
score regardless of how extreme its other components look. No database
access, no I/O -- every input here is data the caller already computed
(see metrics.py for how the raw components are produced). Implements the
approved Research Trend Analysis v1 design, section 7.
"""
from typing import NamedTuple

from research_platform.trends.metrics import DEFAULT_MIN_SUPPORT_TOTAL, normalize_growth_rate

# Weights sum to 100 by construction, so with every component in [0, 1] the
# raw pre-support-factor score is always already within [0, 100].
COMPONENT_WEIGHTS = {
    "recent_volume": 25,
    "growth_rate": 25,
    "share_change": 15,
    "acceleration": 15,
    "recency": 10,
    "consistency": 10,
}


class TrendScoreComponents(NamedTuple):
    recent_volume_component: float
    growth_rate_component: float
    share_change_component: float
    acceleration_component: float
    recency_component: float
    consistency_component: float


def _clamp01(value: float, name: str) -> float:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be within [0, 1]; got {value!r}")
    return value


def recent_volume_component(recent_count: int, max_recent_count: int) -> float:
    """How much this entity published recently, relative to the busiest
    entity in the same period. 0.0 when nothing has published at all yet
    (max_recent_count == 0)."""
    if recent_count < 0 or max_recent_count < 0:
        raise ValueError("recent_count and max_recent_count must be non-negative")
    if recent_count > max_recent_count:
        raise ValueError(f"recent_count ({recent_count}) cannot exceed max_recent_count ({max_recent_count})")
    return recent_count / max_recent_count if max_recent_count > 0 else 0.0


def growth_rate_component(growth_rate: float | None) -> float:
    """How much faster (or slower) this entity is publishing than the
    prior comparison period. Reuses metrics.normalize_growth_rate() so
    momentum and this component never disagree on how an undefined
    (None) growth rate should be treated."""
    return normalize_growth_rate(growth_rate)


def share_change_component(share_change: float | None) -> float:
    """Whether this entity is taking a bigger slice of all recent papers,
    not just publishing more in absolute terms. None (undefined, e.g. no
    previous-period denominator) maps to a neutral 0.5."""
    if share_change is None:
        return 0.5
    clamped = max(-1.0, min(1.0, share_change))
    return (clamped + 1.0) / 2.0


def acceleration_component(acceleration: bool | None) -> float:
    """Whether growth is itself speeding up across several windows. True
    is rewarded, False is penalized but not zeroed, None (fewer than 3
    windows of history) is neutral."""
    if acceleration is True:
        return 1.0
    if acceleration is False:
        return 0.3
    return 0.5


def recency_component(recency: float) -> float:
    """How recently this entity's most recent paper landed. Expects an
    already-computed metrics.compute_recency() value (already in [0, 1])."""
    return _clamp01(recency, "recency")


def consistency_component(consistency: float) -> float:
    """Whether this entity shows up window after window, or just once.
    Expects an already-computed metrics.compute_consistency() value
    (already in [0, 1])."""
    return _clamp01(consistency, "consistency")


def compute_support_factor(total_papers: int, *, min_support_total: int = DEFAULT_MIN_SUPPORT_TOTAL) -> float:
    """Multiplicative penalty applied last, so it is structurally
    impossible for a low-total-paper entity to reach a high trend_score
    even if every additive component maxed out. A 1-paper entity with
    min_support_total=5 gets support_factor=0.1 -> trend_score capped at
    10, whatever its other components say."""
    if total_papers < 0:
        raise ValueError(f"total_papers must be non-negative; got {total_papers!r}")
    if min_support_total <= 0:
        raise ValueError(f"min_support_total must be positive; got {min_support_total!r}")
    return min(1.0, total_papers / (2 * min_support_total))


def compute_trend_score(components: TrendScoreComponents, support_factor: float) -> int:
    """0-100 integer trend score. Bounds are guaranteed by construction
    (weights sum to 100, every component and support_factor is in [0, 1]),
    but the result is clamped defensively regardless."""
    if not (0.0 <= support_factor <= 1.0):
        raise ValueError(f"support_factor must be within [0, 1]; got {support_factor!r}")
    raw = (
        COMPONENT_WEIGHTS["recent_volume"] * _clamp01(components.recent_volume_component, "recent_volume_component")
        + COMPONENT_WEIGHTS["growth_rate"] * _clamp01(components.growth_rate_component, "growth_rate_component")
        + COMPONENT_WEIGHTS["share_change"] * _clamp01(components.share_change_component, "share_change_component")
        + COMPONENT_WEIGHTS["acceleration"] * _clamp01(components.acceleration_component, "acceleration_component")
        + COMPONENT_WEIGHTS["recency"] * _clamp01(components.recency_component, "recency_component")
        + COMPONENT_WEIGHTS["consistency"] * _clamp01(components.consistency_component, "consistency_component")
    )
    score = round(raw * support_factor)
    return max(0, min(100, score))
