"""Validates research_platform.trends.scoring: component normalization,
the multiplicative minimum-support penalty, and the combined 0-100
trend_score formula -- bounds, determinism, and the one-paper penalty case.
Pure functions only -- no database, no I/O, no network. Run directly:

    python3 tests/test_trend_scoring.py
"""
import itertools

from research_platform.trends.scoring import (
    TrendScoreComponents,
    acceleration_component,
    compute_support_factor,
    compute_trend_score,
    consistency_component,
    growth_rate_component,
    recency_component,
    recent_volume_component,
    share_change_component,
)


def _components(**overrides) -> TrendScoreComponents:
    base = dict(
        recent_volume_component=0.5,
        growth_rate_component=0.5,
        share_change_component=0.5,
        acceleration_component=0.5,
        recency_component=0.5,
        consistency_component=0.5,
    )
    base.update(overrides)
    return TrendScoreComponents(**base)


def test_recent_volume_component_ratio_and_zero_denominator():
    assert recent_volume_component(11, 22) == 0.5
    assert recent_volume_component(0, 0) == 0.0
    print("PASS: recent_volume_component is recent/max, 0.0 when max_recent_count == 0")


def test_recent_volume_component_rejects_exceeding_max():
    try:
        recent_volume_component(5, 3)
        raised = False
    except ValueError:
        raised = True
    assert raised
    print("PASS: recent_volume_component raises ValueError when recent_count > max_recent_count")


def test_growth_rate_component_matches_normalize_growth_rate():
    assert growth_rate_component(None) == 0.5
    assert growth_rate_component(0.0) == 0.25
    assert growth_rate_component(3.0) == 1.0
    print("PASS: growth_rate_component reuses metrics.normalize_growth_rate exactly")


def test_share_change_component_neutral_on_none_and_bounded():
    assert share_change_component(None) == 0.5
    assert share_change_component(1.0) == 1.0
    assert share_change_component(-1.0) == 0.0
    assert share_change_component(2.0) == 1.0  # clamped
    print("PASS: share_change_component neutral on None, bounded to [0, 1]")


def test_acceleration_component_three_states():
    assert acceleration_component(True) == 1.0
    assert acceleration_component(False) == 0.3
    assert acceleration_component(None) == 0.5
    print("PASS: acceleration_component distinguishes True / False / None (insufficient history)")


def test_recency_and_consistency_components_reject_out_of_range():
    assert recency_component(0.7) == 0.7
    assert consistency_component(1.0) == 1.0
    for bad in (-0.1, 1.1):
        for fn in (recency_component, consistency_component):
            try:
                fn(bad)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"{fn.__name__} should reject {bad}"
    print("PASS: recency/consistency components pass through [0,1] values, reject out-of-range")


def test_support_factor_scales_with_total_papers():
    assert compute_support_factor(0, min_support_total=5) == 0.0
    assert compute_support_factor(5, min_support_total=5) == 0.5
    assert compute_support_factor(10, min_support_total=5) == 1.0
    assert compute_support_factor(100, min_support_total=5) == 1.0  # capped at 1.0
    print("PASS: support_factor scales from 0 at 0 papers to 1.0 at 2x min_support_total, capped there")


def test_one_paper_entity_score_is_bounded_regardless_of_components():
    support_factor = compute_support_factor(1, min_support_total=5)  # 0.1
    maxed_components = _components(
        recent_volume_component=1.0,
        growth_rate_component=1.0,
        share_change_component=1.0,
        acceleration_component=1.0,
        recency_component=1.0,
        consistency_component=1.0,
    )
    score = compute_trend_score(maxed_components, support_factor)
    assert score <= 10, f"a 1-paper entity must never score above 10 (support_factor=0.1); got {score}"
    print(f"PASS: a 1-paper entity with every component maxed still scores only {score}/100")


def test_trend_score_bounds_across_many_synthetic_inputs():
    sample_values = (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0)
    checked = 0
    for combo in itertools.islice(itertools.product(sample_values, repeat=6), 0, 400):
        components = TrendScoreComponents(*combo)
        for support_factor in (0.0, 0.1, 0.5, 1.0):
            score = compute_trend_score(components, support_factor)
            assert 0 <= score <= 100, f"score {score} out of bounds for {combo}, support_factor={support_factor}"
            checked += 1
    print(f"PASS: trend_score stayed within [0, 100] across {checked} synthetic component/support_factor combinations")


def test_trend_score_deterministic():
    components = _components(recent_volume_component=0.8, growth_rate_component=0.6)
    a = compute_trend_score(components, 0.9)
    b = compute_trend_score(components, 0.9)
    assert a == b
    print("PASS: identical inputs produce an identical trend_score every time")


def test_trend_score_rejects_component_out_of_range():
    bad = _components(recent_volume_component=1.5)
    try:
        compute_trend_score(bad, 1.0)
        raised = False
    except ValueError:
        raised = True
    assert raised
    print("PASS: an out-of-range component raises ValueError rather than silently producing a bad score")


def test_max_score_only_when_everything_maxed():
    components = _components(
        recent_volume_component=1.0,
        growth_rate_component=1.0,
        share_change_component=1.0,
        acceleration_component=1.0,
        recency_component=1.0,
        consistency_component=1.0,
    )
    assert compute_trend_score(components, 1.0) == 100
    print("PASS: trend_score reaches exactly 100 only when every component and support_factor are maxed")


if __name__ == "__main__":
    test_recent_volume_component_ratio_and_zero_denominator()
    test_recent_volume_component_rejects_exceeding_max()
    test_growth_rate_component_matches_normalize_growth_rate()
    test_share_change_component_neutral_on_none_and_bounded()
    test_acceleration_component_three_states()
    test_recency_and_consistency_components_reject_out_of_range()
    test_support_factor_scales_with_total_papers()
    test_one_paper_entity_score_is_bounded_regardless_of_components()
    test_trend_score_bounds_across_many_synthetic_inputs()
    test_trend_score_deterministic()
    test_trend_score_rejects_component_out_of_range()
    test_max_score_only_when_everything_maxed()
    print("\nALL TESTS PASSED")
