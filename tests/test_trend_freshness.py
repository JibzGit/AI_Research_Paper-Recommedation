"""Validates research_platform.trends.freshness: every freshness_status
rule branch, and the revised trend-mode resolution behavior -- a
'current'-mode request is never silently downgraded into a historical
result; it resolves to an explicit CURRENT_UNAVAILABLE state that
preserves freshness_status and a specific reason. Also validates the
end-to-end "historical cohort comparison" path using the real audited
corpus numbers (169 canonical papers, 4 days since the latest paper, 30
papers in the last 90 days, 0 in the prior 90 days, all 30 on a single
calendar day). Pure functions only -- no database, no I/O. Run directly:

    python3 tests/test_trend_freshness.py
"""
from research_platform.trends.classifications import (
    CURRENT_UNAVAILABLE_LABEL,
    HISTORICAL_COHORT_COMPARISON_LABEL,
    resolve_trend_mode_label,
)
from research_platform.trends.freshness import (
    CURRENT,
    CURRENT_OK,
    CURRENT_UNAVAILABLE,
    HISTORICAL_ONLY,
    HISTORICAL_OK,
    HISTORICAL_UNAVAILABLE,
    INSUFFICIENT_DATA,
    PARTIALLY_CURRENT,
    compute_freshness_status,
    resolve_trend_request,
)

# The real, live audit numbers from the approved trend-analysis design
# (section 2.1/2.2/3.1), reused here rather than re-deriving synthetic
# stand-ins for the headline scenario.
REAL_CORPUS_KWARGS = dict(
    total_canonical_papers=169,
    days_since_latest_paper=4,
    recent_period_paper_count=30,
    comparison_period_paper_count=0,
    recent_period_distinct_days=1,
    recent_window_days=90,
)


# --- freshness_status: every branch ------------------------------------------

def test_freshness_insufficient_data_below_corpus_floor():
    status = compute_freshness_status(
        total_canonical_papers=10, days_since_latest_paper=1,
        recent_period_paper_count=10, comparison_period_paper_count=10,
        recent_period_distinct_days=10, recent_window_days=90, corpus_floor=30,
    )
    assert status == INSUFFICIENT_DATA
    print("PASS: freshness_status is INSUFFICIENT_DATA when total_canonical_papers is below corpus_floor")


def test_freshness_historical_only_via_stale_latest_paper():
    status = compute_freshness_status(
        total_canonical_papers=200, days_since_latest_paper=200,
        recent_period_paper_count=0, comparison_period_paper_count=0,
        recent_period_distinct_days=0, recent_window_days=90, stale_threshold_days=180,
    )
    assert status == HISTORICAL_ONLY
    print("PASS: freshness_status is HISTORICAL_ONLY when days_since_latest_paper exceeds stale_threshold_days")


def test_freshness_historical_only_via_empty_recent_window():
    """Even a fresh latest-paper date doesn't help if the recent window
    itself has zero papers."""
    status = compute_freshness_status(
        total_canonical_papers=200, days_since_latest_paper=5,
        recent_period_paper_count=0, comparison_period_paper_count=5,
        recent_period_distinct_days=0, recent_window_days=90,
    )
    assert status == HISTORICAL_ONLY
    print("PASS: freshness_status is HISTORICAL_ONLY when recent_period_paper_count == 0, even with a fresh latest date")


def test_freshness_partially_current_via_empty_comparison_period():
    """This is the real corpus's actual state today."""
    status = compute_freshness_status(**REAL_CORPUS_KWARGS)
    assert status == PARTIALLY_CURRENT
    print("PASS: freshness_status is PARTIALLY_CURRENT for the real corpus (comparison_period_paper_count == 0)")


def test_freshness_partially_current_via_single_day_concentration():
    """Comparison period now has enough papers, but the recent-period
    activity is still concentrated on very few calendar days -- must still
    block CURRENT."""
    status = compute_freshness_status(
        total_canonical_papers=200, days_since_latest_paper=2,
        recent_period_paper_count=30, comparison_period_paper_count=25,
        recent_period_distinct_days=2, recent_window_days=90,
    )
    assert status == PARTIALLY_CURRENT
    print("PASS: freshness_status is PARTIALLY_CURRENT when recent activity is concentrated on very few calendar days")


def test_freshness_current_when_all_gates_pass():
    status = compute_freshness_status(
        total_canonical_papers=500, days_since_latest_paper=1,
        recent_period_paper_count=40, comparison_period_paper_count=35,
        recent_period_distinct_days=60, recent_window_days=90,
    )
    assert status == CURRENT
    print("PASS: freshness_status is CURRENT only when corpus size, recency, comparison baseline, and spread all pass")


def test_freshness_rejects_invalid_inputs():
    try:
        compute_freshness_status(
            total_canonical_papers=100, days_since_latest_paper=1,
            recent_period_paper_count=10, comparison_period_paper_count=5,
            recent_period_distinct_days=100, recent_window_days=90,  # distinct_days > window_days
        )
        raised = False
    except ValueError:
        raised = True
    assert raised
    print("PASS: recent_period_distinct_days > recent_window_days raises ValueError")


# --- trend-mode resolution: current-mode-unavailable behavior ----------------

def test_current_request_ok_only_when_freshness_is_current():
    resolution = resolve_trend_request("current", CURRENT)
    assert resolution.resolved_state == CURRENT_OK
    assert resolution.reason is None
    print("PASS: a 'current' request resolves to CURRENT_OK only when freshness_status == CURRENT")


def test_current_request_never_silently_downgrades_to_historical():
    """The core requirement: for every non-CURRENT freshness_status, a
    'current'-mode request must resolve to the explicit CURRENT_UNAVAILABLE
    state -- never to HISTORICAL_OK, and never carrying a historical result
    presented as the answer."""
    for status in (PARTIALLY_CURRENT, HISTORICAL_ONLY, INSUFFICIENT_DATA):
        resolution = resolve_trend_request("current", status)
        assert resolution.resolved_state == CURRENT_UNAVAILABLE, (
            f"current request under freshness_status={status} must resolve to CURRENT_UNAVAILABLE, "
            f"got {resolution.resolved_state}"
        )
        assert resolution.resolved_state != HISTORICAL_OK
        assert resolution.freshness_status == status
        assert resolution.reason is not None and len(resolution.reason) > 0
    print("PASS: a 'current' request under PARTIALLY_CURRENT / HISTORICAL_ONLY / INSUFFICIENT_DATA "
          "always resolves to CURRENT_UNAVAILABLE with a preserved freshness_status and reason -- never a downgrade")


def test_current_unavailable_reason_is_specific_per_freshness_status():
    reasons = {
        status: resolve_trend_request("current", status).reason
        for status in (PARTIALLY_CURRENT, HISTORICAL_ONLY, INSUFFICIENT_DATA)
    }
    assert len(set(reasons.values())) == 3, "each freshness_status should produce a distinct, specific reason"
    print("PASS: CURRENT_UNAVAILABLE reason text is specific to the underlying freshness_status, not generic")


def test_historical_cohort_available_flag():
    for status in (CURRENT, PARTIALLY_CURRENT, HISTORICAL_ONLY):
        assert resolve_trend_request("current", status).historical_cohort_available is True
        assert resolve_trend_request("historical", status).historical_cohort_available is True
    assert resolve_trend_request("current", INSUFFICIENT_DATA).historical_cohort_available is False
    assert resolve_trend_request("historical", INSUFFICIENT_DATA).historical_cohort_available is False
    print("PASS: historical_cohort_available is True for every freshness_status except INSUFFICIENT_DATA")


def test_resolve_trend_request_rejects_invalid_mode_or_status():
    for kwargs in (("not-a-mode", CURRENT), ("current", "NOT_A_STATUS")):
        try:
            resolve_trend_request(*kwargs)
            raised = False
        except ValueError:
            raised = True
        assert raised, f"expected ValueError for {kwargs}"
    print("PASS: resolve_trend_request rejects unknown trend_mode/freshness_status values")


# --- trend-mode resolution: historical cohort-comparison behavior -----------

def test_historical_request_always_ok_except_insufficient_data():
    for status in (CURRENT, PARTIALLY_CURRENT, HISTORICAL_ONLY):
        resolution = resolve_trend_request("historical", status)
        assert resolution.resolved_state == HISTORICAL_OK
        assert resolution.reason is None
    print("PASS: a 'historical' request is honored (HISTORICAL_OK) under any freshness_status except INSUFFICIENT_DATA")


def test_historical_request_unavailable_when_corpus_itself_too_small():
    resolution = resolve_trend_request("historical", INSUFFICIENT_DATA)
    assert resolution.resolved_state == HISTORICAL_UNAVAILABLE
    assert resolution.reason is not None
    print("PASS: a 'historical' request under INSUFFICIENT_DATA resolves to HISTORICAL_UNAVAILABLE, not a fabricated comparison")


def test_end_to_end_real_corpus_current_request_is_unavailable():
    """Using the real audited numbers: requesting current trends today
    must come back CURRENT_UNAVAILABLE, labeled accordingly -- not a
    silently-substituted historical result."""
    status = compute_freshness_status(**REAL_CORPUS_KWARGS)
    resolution = resolve_trend_request("current", status)
    assert status == PARTIALLY_CURRENT
    assert resolution.resolved_state == CURRENT_UNAVAILABLE
    label = resolve_trend_mode_label(resolution.resolved_state)
    assert label == CURRENT_UNAVAILABLE_LABEL == "Current Trends Unavailable"
    assert resolution.historical_cohort_available is True
    print(f'PASS: real-corpus current request -> freshness_status={status}, '
          f'resolved_state={resolution.resolved_state}, label="{label}", '
          f'historical_cohort_available={resolution.historical_cohort_available}')


def test_end_to_end_real_corpus_historical_request_is_a_cohort_comparison():
    """Using the same real numbers, a 'historical' request must succeed and
    be labeled exactly "Historical Cohort Comparison"."""
    status = compute_freshness_status(**REAL_CORPUS_KWARGS)
    resolution = resolve_trend_request("historical", status)
    assert resolution.resolved_state == HISTORICAL_OK
    label = resolve_trend_mode_label(resolution.resolved_state)
    assert label == HISTORICAL_COHORT_COMPARISON_LABEL == "Historical Cohort Comparison"
    print(f'PASS: real-corpus historical request -> resolved_state={resolution.resolved_state}, label="{label}"')


if __name__ == "__main__":
    test_freshness_insufficient_data_below_corpus_floor()
    test_freshness_historical_only_via_stale_latest_paper()
    test_freshness_historical_only_via_empty_recent_window()
    test_freshness_partially_current_via_empty_comparison_period()
    test_freshness_partially_current_via_single_day_concentration()
    test_freshness_current_when_all_gates_pass()
    test_freshness_rejects_invalid_inputs()
    test_current_request_ok_only_when_freshness_is_current()
    test_current_request_never_silently_downgrades_to_historical()
    test_current_unavailable_reason_is_specific_per_freshness_status()
    test_historical_cohort_available_flag()
    test_resolve_trend_request_rejects_invalid_mode_or_status()
    test_historical_request_always_ok_except_insufficient_data()
    test_historical_request_unavailable_when_corpus_itself_too_small()
    test_end_to_end_real_corpus_current_request_is_unavailable()
    test_end_to_end_real_corpus_historical_request_is_a_cohort_comparison()
    print("\nALL TESTS PASSED")
