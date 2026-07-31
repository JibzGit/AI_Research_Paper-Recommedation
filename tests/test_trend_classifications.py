"""Validates research_platform.trends.classifications: the six-way
deterministic classification rule table, data-quality-level rules, and the
fixed trend-mode/freshness label vocabulary (including the banned-phrase
guarantees for the two-cohort comparison). Pure functions only -- no
database, no I/O, no LLM calls. Includes the three documented real
examples from the approved trend-analysis design (cluster 5, cluster 0,
cluster 4). Run directly:

    python3 tests/test_trend_classifications.py
"""
from research_platform.trends.classifications import (
    ACCELERATING,
    BANNED_HISTORICAL_PHRASES,
    CONSISTENTLY_ACTIVE,
    COOLING,
    CURRENT_TRENDS_LABEL,
    CURRENT_UNAVAILABLE_LABEL,
    EMERGING,
    HIGH,
    HISTORICAL_COHORT_COMPARISON_LABEL,
    HISTORICAL_UNAVAILABLE_LABEL,
    INSUFFICIENT,
    INSUFFICIENT_DATA,
    LOW,
    MEDIUM,
    STABLE,
    classify_trend,
    compute_data_quality_level,
    resolve_trend_mode_label,
)
from research_platform.trends.freshness import (
    CURRENT_OK,
    CURRENT_UNAVAILABLE,
    HISTORICAL_OK,
    HISTORICAL_UNAVAILABLE,
)
from research_platform.trends.metrics import compute_growth_rate


# --- Documented real examples (design section 7.5) ---------------------------

def test_cluster_5_eleven_vs_eleven_is_stable():
    """Cluster 5, Model Distillation and Policy Learning: 11 papers in the
    2026 cohort, 11 in the 2016 cohort -- equal presence in both, so this
    must be Stable, not Emerging, despite having the most 2026-cohort
    papers of any cluster."""
    growth = compute_growth_rate(recent_count=11, previous_count=11)
    result = classify_trend(
        total_papers=22,
        recent_count=11,
        previous_count=11,
        growth_rate=growth.growth_rate,
        is_new_activity=growth.is_new_activity,
        acceleration=None,
        consistency=0.5,  # below the 0.75 Consistently-Active threshold
    )
    assert result == STABLE
    print("PASS: Cluster 5 (11 vs 11) classifies as Stable")


def test_cluster_0_zero_vs_six_is_emerging():
    """Cluster 0, Medical Imaging AI and Clinical Evaluation: 0 papers in
    the 2016 cohort, 6 in the 2026 cohort -- new activity with real
    volume. Historical-cohort context only: this means the cluster label
    has no pre-2026 history, not that the research area itself is new
    (only one clustering run exists -- see design section 9)."""
    growth = compute_growth_rate(recent_count=6, previous_count=0)
    result = classify_trend(
        total_papers=6,
        recent_count=6,
        previous_count=0,
        growth_rate=growth.growth_rate,
        is_new_activity=growth.is_new_activity,
        acceleration=None,
        consistency=1.0,
    )
    assert result == EMERGING
    print("PASS: Cluster 0 (0 vs 6) classifies as Emerging")


def test_cluster_4_fourteen_vs_zero_is_cooling():
    """Cluster 4, Online Media Analysis and Event Retrieval: 14 papers in
    the 2016 cohort, 0 in the 2026 cohort."""
    growth = compute_growth_rate(recent_count=0, previous_count=14)
    result = classify_trend(
        total_papers=14,
        recent_count=0,
        previous_count=14,
        growth_rate=growth.growth_rate,
        is_new_activity=growth.is_new_activity,
        acceleration=None,
        consistency=0.0,
    )
    assert result == COOLING
    print("PASS: Cluster 4 (14 vs 0) classifies as Cooling")


# --- One rule per branch, isolated -------------------------------------------

def test_insufficient_data_below_minimum_total_support():
    result = classify_trend(
        total_papers=4,
        recent_count=100,
        previous_count=100,
        growth_rate=999.0,  # even an absurd growth rate can't override the support gate
        is_new_activity=False,
        acceleration=True,
        consistency=1.0,
        min_support_total=5,
    )
    assert result == INSUFFICIENT_DATA
    print("PASS: total_papers below min_support_total always yields Insufficient Data, first rule wins")


def test_emerging_rule():
    result = classify_trend(
        total_papers=10, recent_count=5, previous_count=0,
        growth_rate=None, is_new_activity=True, acceleration=None, consistency=0.2,
    )
    assert result == EMERGING
    print("PASS: is_new_activity with recent_count >= min_support_period -> Emerging")


def test_accelerating_rule():
    result = classify_trend(
        total_papers=20, recent_count=15, previous_count=5,
        growth_rate=0.5, is_new_activity=False, acceleration=True, consistency=0.2,
    )
    assert result == ACCELERATING
    print("PASS: growth_rate > threshold + acceleration True + real comparison baseline -> Accelerating")


def test_consistently_active_rule():
    result = classify_trend(
        total_papers=20, recent_count=8, previous_count=7,
        growth_rate=0.05, is_new_activity=False, acceleration=None, consistency=0.9,
    )
    assert result == CONSISTENTLY_ACTIVE
    print("PASS: high consistency + flat-to-moderate growth -> Consistently Active")


def test_stable_rule():
    result = classify_trend(
        total_papers=20, recent_count=10, previous_count=10,
        growth_rate=0.0, is_new_activity=False, acceleration=None, consistency=0.3,
    )
    assert result == STABLE
    print("PASS: flat growth + real comparison baseline + low consistency -> Stable")


def test_cooling_rule():
    result = classify_trend(
        total_papers=20, recent_count=3, previous_count=10,
        growth_rate=-0.5, is_new_activity=False, acceleration=None, consistency=0.3,
    )
    assert result == COOLING
    print("PASS: strong negative growth + real comparison baseline -> Cooling")


def test_insufficient_data_catch_all_for_ambiguous_moderate_growth():
    """15% growth is above the +/-10% Stable band but below the 20%
    Accelerating threshold, with no acceleration/consistency evidence to
    push it into another bucket -- must not be silently guessed into
    Stable or Accelerating."""
    result = classify_trend(
        total_papers=20, recent_count=11, previous_count=10,
        growth_rate=0.15, is_new_activity=False, acceleration=False, consistency=0.3,
    )
    assert result == INSUFFICIENT_DATA
    print("PASS: ambiguous moderate growth with no supporting evidence falls through to Insufficient Data")


def test_period_support_gate_blocks_cooling_on_thin_comparison_period():
    """A -50% growth rate looks like Cooling, but previous_count=2 is below
    min_support_period=3 -- the period-level gate must block the
    classification rather than trusting a 2-paper baseline."""
    result = classify_trend(
        total_papers=20, recent_count=1, previous_count=2,
        growth_rate=-0.5, is_new_activity=False, acceleration=None, consistency=0.3,
        min_support_period=3,
    )
    assert result == INSUFFICIENT_DATA
    print("PASS: Cooling is blocked when previous_count is below min_support_period, even with steep growth_rate")


# --- Data quality level -------------------------------------------------------

def test_data_quality_insufficient_below_total_support():
    assert compute_data_quality_level(
        total_papers=3, previous_count=10, recent_period_distinct_days=30, recent_window_days=90,
    ) == INSUFFICIENT
    print("PASS: data_quality_level is INSUFFICIENT below minimum total support")


def test_data_quality_low_on_thin_comparison_period():
    assert compute_data_quality_level(
        total_papers=20, previous_count=1, recent_period_distinct_days=30, recent_window_days=90,
    ) == LOW
    print("PASS: data_quality_level is LOW when previous_count is below min_support_period")


def test_data_quality_low_on_single_day_concentration():
    """This is the real, live shape of the corpus today: 30 recent papers,
    all on one calendar day out of a 90-day window."""
    assert compute_data_quality_level(
        total_papers=20, previous_count=10, recent_period_distinct_days=1, recent_window_days=90,
    ) == LOW
    print("PASS: data_quality_level is LOW when recent activity is concentrated on ~1 calendar day (real corpus shape)")


def test_data_quality_medium_by_default():
    assert compute_data_quality_level(
        total_papers=20, previous_count=10, recent_period_distinct_days=30, recent_window_days=90,
    ) == MEDIUM
    print("PASS: data_quality_level is MEDIUM once support gates pass without multi-window history")


def test_data_quality_high_requires_explicit_multi_window_history():
    assert compute_data_quality_level(
        total_papers=20, previous_count=10, recent_period_distinct_days=30, recent_window_days=90,
        multi_window_history=True,
    ) == HIGH
    print("PASS: data_quality_level reaches HIGH only when multi_window_history is explicitly True")


def test_data_quality_rejects_invalid_window_inputs():
    try:
        compute_data_quality_level(total_papers=20, previous_count=10, recent_period_distinct_days=100, recent_window_days=90)
        raised = False
    except ValueError:
        raised = True
    assert raised
    print("PASS: recent_period_distinct_days > recent_window_days raises ValueError")


# --- Trend-mode label vocabulary (design section 3.4, revised) --------------

def test_label_lookup_matches_each_resolved_state():
    assert resolve_trend_mode_label(CURRENT_OK) == CURRENT_TRENDS_LABEL
    assert resolve_trend_mode_label(HISTORICAL_OK) == HISTORICAL_COHORT_COMPARISON_LABEL
    assert resolve_trend_mode_label(CURRENT_UNAVAILABLE) == CURRENT_UNAVAILABLE_LABEL
    assert resolve_trend_mode_label(HISTORICAL_UNAVAILABLE) == HISTORICAL_UNAVAILABLE_LABEL
    print("PASS: every freshness.resolve_trend_request() outcome has exactly one fixed label")


def test_historical_ok_always_uses_historical_cohort_comparison_term():
    assert resolve_trend_mode_label(HISTORICAL_OK) == "Historical Cohort Comparison"
    print('PASS: HISTORICAL_OK label is exactly "Historical Cohort Comparison"')


def test_label_lookup_rejects_unknown_state():
    try:
        resolve_trend_mode_label("NOT_A_REAL_STATE")
        raised = False
    except ValueError:
        raised = True
    assert raised
    print("PASS: an unknown resolved_state raises ValueError rather than returning a made-up label")


def test_no_historical_or_unavailable_label_contains_a_banned_phrase():
    """"trending now" is deliberately excluded from this check: it is the
    correct, reserved label for a genuinely CURRENT_OK result
    (CURRENT_TRENDS_LABEL) -- banning it globally would forbid the one
    place it's actually supposed to appear. What must never happen is any
    *historical*/cohort-comparison-adjacent label using it, or any label
    using "continuous historical trend" / "current momentum" /
    "year-over-year" language -- covered here across all four labels."""
    historical_adjacent_labels = (
        HISTORICAL_COHORT_COMPARISON_LABEL,
        CURRENT_UNAVAILABLE_LABEL,
        HISTORICAL_UNAVAILABLE_LABEL,
    )
    for label in historical_adjacent_labels:
        lowered = label.lower()
        for banned in BANNED_HISTORICAL_PHRASES:
            assert banned not in lowered, f'label "{label}" contains banned phrase "{banned}"'
    for label in (CURRENT_TRENDS_LABEL, *historical_adjacent_labels):
        lowered = label.lower()
        for banned in ("continuous historical trend", "current momentum", "year-over-year"):
            assert banned not in lowered, f'label "{label}" contains banned phrase "{banned}"'
    print("PASS: no historical/cohort/unavailable label contains a banned phrase, and no label anywhere "
          "uses 'continuous historical trend' / 'current momentum' / 'year-over-year' language")


def test_current_trends_label_is_the_only_one_using_trending_now():
    """"Trending Now" is reserved for a genuinely CURRENT_OK result -- it
    must never be the label attached to a historical/cohort result."""
    assert resolve_trend_mode_label(CURRENT_OK) == "Trending Now"
    assert resolve_trend_mode_label(HISTORICAL_OK) != "Trending Now"
    print('PASS: "Trending Now" only ever labels CURRENT_OK, never HISTORICAL_OK')


if __name__ == "__main__":
    test_cluster_5_eleven_vs_eleven_is_stable()
    test_cluster_0_zero_vs_six_is_emerging()
    test_cluster_4_fourteen_vs_zero_is_cooling()
    test_insufficient_data_below_minimum_total_support()
    test_emerging_rule()
    test_accelerating_rule()
    test_consistently_active_rule()
    test_stable_rule()
    test_cooling_rule()
    test_insufficient_data_catch_all_for_ambiguous_moderate_growth()
    test_period_support_gate_blocks_cooling_on_thin_comparison_period()
    test_data_quality_insufficient_below_total_support()
    test_data_quality_low_on_thin_comparison_period()
    test_data_quality_low_on_single_day_concentration()
    test_data_quality_medium_by_default()
    test_data_quality_high_requires_explicit_multi_window_history()
    test_data_quality_rejects_invalid_window_inputs()
    test_label_lookup_matches_each_resolved_state()
    test_historical_ok_always_uses_historical_cohort_comparison_term()
    test_label_lookup_rejects_unknown_state()
    test_no_historical_or_unavailable_label_contains_a_banned_phrase()
    test_current_trends_label_is_the_only_one_using_trending_now()
    print("\nALL TESTS PASSED")
