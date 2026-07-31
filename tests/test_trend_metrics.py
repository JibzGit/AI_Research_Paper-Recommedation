"""Validates research_platform.trends.metrics: safe growth-rate zero
handling, publication share, momentum, acceleration, consistency, recency,
and minimum-support gating. Pure functions only -- no database, no I/O, no
network. Run directly:

    python3 tests/test_trend_metrics.py
"""
import math

from research_platform.trends.metrics import (
    DEFAULT_MIN_SUPPORT_PERIOD,
    DEFAULT_MIN_SUPPORT_TOTAL,
    compute_absolute_growth,
    compute_acceleration,
    compute_consistency,
    compute_growth_rate,
    compute_momentum,
    compute_publication_share,
    compute_recency,
    compute_share_change,
    meets_minimum_period_support,
    meets_minimum_total_support,
    normalize_growth_rate,
)


def test_growth_rate_standard_case():
    result = compute_growth_rate(recent_count=15, previous_count=10)
    assert result.growth_rate == 0.5
    assert result.is_new_activity is False
    print("PASS: standard growth rate (15 vs 10) == +50%, is_new_activity == False")


def test_growth_rate_negative_case():
    result = compute_growth_rate(recent_count=0, previous_count=14)
    assert result.growth_rate == -1.0
    assert result.is_new_activity is False
    print("PASS: 0 vs 14 == -100% growth (cluster-4-shaped cooling case)")


def test_growth_rate_previous_zero_recent_zero_is_a_real_zero():
    result = compute_growth_rate(recent_count=0, previous_count=0)
    assert result.growth_rate == 0.0
    assert result.growth_rate is not None
    assert result.is_new_activity is False
    print("PASS: previous_count=0, recent_count=0 -> growth_rate is a real 0.0, not None/unknown")


def test_growth_rate_previous_zero_recent_positive_is_undefined_not_infinite():
    result = compute_growth_rate(recent_count=6, previous_count=0)
    assert result.growth_rate is None
    assert result.is_new_activity is True
    print("PASS: previous_count=0, recent_count=6 (cluster-0-shaped) -> growth_rate is None, "
          "never +inf or a fabricated large percentage; is_new_activity flags it instead")


def test_growth_rate_rejects_negative_counts():
    for kwargs in ({"recent_count": -1, "previous_count": 5}, {"recent_count": 5, "previous_count": -1}):
        try:
            compute_growth_rate(**kwargs)
            raised = False
        except ValueError:
            raised = True
        assert raised, f"expected ValueError for {kwargs}"
    print("PASS: negative counts raise ValueError")


def test_absolute_growth():
    assert compute_absolute_growth(recent_count=30, previous_count=0) == 30
    assert compute_absolute_growth(recent_count=11, previous_count=11) == 0
    assert compute_absolute_growth(recent_count=0, previous_count=14) == -14
    print("PASS: absolute growth is always defined, including previous_count=0")


def test_publication_share():
    assert compute_publication_share(entity_count=52, total_count=169) == 52 / 169
    assert compute_publication_share(entity_count=0, total_count=0) is None
    print("PASS: publication share is None only when total_count == 0")


def test_publication_share_rejects_entity_exceeding_total():
    try:
        compute_publication_share(entity_count=10, total_count=5)
        raised = False
    except ValueError:
        raised = True
    assert raised
    print("PASS: entity_count > total_count raises ValueError")


def test_share_change_null_propagation():
    assert compute_share_change(0.3, 0.2) == 0.3 - 0.2
    assert compute_share_change(None, 0.2) is None
    assert compute_share_change(0.3, None) is None
    assert compute_share_change(None, None) is None
    print("PASS: share_change is None whenever either share is None")


def test_normalize_growth_rate_bounds_and_neutral_none():
    assert normalize_growth_rate(None) == 0.5
    assert normalize_growth_rate(0.0) == 0.25
    assert normalize_growth_rate(-1.0) == 0.0
    assert normalize_growth_rate(-5.0) == 0.0  # clamped below -1.0
    assert normalize_growth_rate(3.0) == 1.0
    assert normalize_growth_rate(10.0) == 1.0  # clamped above 3.0
    print("PASS: normalize_growth_rate bounded to [0, 1], None -> neutral 0.5")


def test_momentum_new_activity_still_registers_volume():
    momentum = compute_momentum(recent_count=6, growth_rate=None, max_recent_count=11)
    assert momentum > 0.0, "a new-activity entity with real recent volume must not get zero momentum"
    print(f"PASS: momentum for undefined growth_rate but real volume is {momentum:.3f} > 0")


def test_momentum_deterministic():
    a = compute_momentum(recent_count=11, growth_rate=0.0, max_recent_count=11)
    b = compute_momentum(recent_count=11, growth_rate=0.0, max_recent_count=11)
    assert a == b
    print("PASS: momentum is deterministic for identical inputs")


def test_acceleration_requires_three_non_null_points():
    assert compute_acceleration([]) is None
    assert compute_acceleration([0.1]) is None
    assert compute_acceleration([0.1, 0.2]) is None
    assert compute_acceleration([0.1, None, 0.3]) is None
    print("PASS: acceleration is None with fewer than 3 consecutive non-null growth rates")


def test_acceleration_strictly_increasing_true():
    assert compute_acceleration([0.05, 0.10, 0.25]) is True
    print("PASS: acceleration True for strictly increasing growth rates across 3 windows")


def test_acceleration_not_increasing_false():
    assert compute_acceleration([0.25, 0.10, 0.05]) is False
    assert compute_acceleration([0.10, 0.10, 0.10]) is False
    print("PASS: acceleration False for flat/decreasing growth-rate sequences")


def test_consistency_fraction():
    assert compute_consistency([True, True, True, False]) == 0.75
    assert compute_consistency([False, False]) == 0.0
    assert compute_consistency([True]) == 1.0
    print("PASS: consistency is the fraction of active windows")


def test_consistency_rejects_empty():
    try:
        compute_consistency([])
        raised = False
    except ValueError:
        raised = True
    assert raised
    print("PASS: consistency raises ValueError on an empty window list")


def test_recency_decays_toward_zero_and_is_one_at_zero_days():
    assert compute_recency(0) == 1.0
    assert 0.0 < compute_recency(90) < 1.0
    assert compute_recency(4) > compute_recency(90) > compute_recency(365)
    print("PASS: recency == 1.0 at 0 days, decays monotonically as days increase")


def test_recency_rejects_negative_days():
    try:
        compute_recency(-1)
        raised = False
    except ValueError:
        raised = True
    assert raised
    print("PASS: negative days_since_last_paper raises ValueError")


def test_minimum_support_gates():
    assert meets_minimum_total_support(5, min_support_total=DEFAULT_MIN_SUPPORT_TOTAL) is True
    assert meets_minimum_total_support(4, min_support_total=DEFAULT_MIN_SUPPORT_TOTAL) is False
    assert meets_minimum_period_support(3, min_support_period=DEFAULT_MIN_SUPPORT_PERIOD) is True
    assert meets_minimum_period_support(2, min_support_period=DEFAULT_MIN_SUPPORT_PERIOD) is False
    print("PASS: minimum-support gates match the configured thresholds exactly at the boundary")


def test_recency_matches_exp_decay_formula():
    assert math.isclose(compute_recency(90, decay_days=90.0), math.exp(-1))
    print("PASS: recency matches exp(-days/decay_days) exactly")


if __name__ == "__main__":
    test_growth_rate_standard_case()
    test_growth_rate_negative_case()
    test_growth_rate_previous_zero_recent_zero_is_a_real_zero()
    test_growth_rate_previous_zero_recent_positive_is_undefined_not_infinite()
    test_growth_rate_rejects_negative_counts()
    test_absolute_growth()
    test_publication_share()
    test_publication_share_rejects_entity_exceeding_total()
    test_share_change_null_propagation()
    test_normalize_growth_rate_bounds_and_neutral_none()
    test_momentum_new_activity_still_registers_volume()
    test_momentum_deterministic()
    test_acceleration_requires_three_non_null_points()
    test_acceleration_strictly_increasing_true()
    test_acceleration_not_increasing_false()
    test_consistency_fraction()
    test_consistency_rejects_empty()
    test_recency_decays_toward_zero_and_is_one_at_zero_days()
    test_recency_rejects_negative_days()
    test_minimum_support_gates()
    test_recency_matches_exp_decay_formula()
    print("\nALL TESTS PASSED")
