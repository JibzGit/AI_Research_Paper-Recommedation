import { describe, expect, it } from 'vitest'

import { formatGrowthRate, formatInclusiveEndDate, formatOptionalPercent, formatSignedInt } from '@/lib/trendFormatters'

describe('formatGrowthRate', () => {
  it('renders "New" for null + is_new_activity (undefined growth, real recent volume)', () => {
    expect(formatGrowthRate(null, true)).toBe('New')
  })

  it('renders "N/A" for null without is_new_activity (should not happen, but must not crash or lie)', () => {
    expect(formatGrowthRate(null, false)).toBe('N/A')
  })

  it('renders a real 0.0 growth rate as "0%", not "New" or "N/A"', () => {
    expect(formatGrowthRate(0, false)).toBe('0%')
  })

  it('renders positive and negative rates with an explicit sign', () => {
    expect(formatGrowthRate(0.5, false)).toBe('+50%')
    expect(formatGrowthRate(-0.75, false)).toBe('-75%')
  })
})

describe('formatSignedInt', () => {
  it('adds a plus sign only for positive values', () => {
    expect(formatSignedInt(6)).toBe('+6')
    expect(formatSignedInt(-13)).toBe('-13')
    expect(formatSignedInt(0)).toBe('0')
  })
})

describe('formatOptionalPercent', () => {
  it('renders N/A for null, a rounded percent otherwise', () => {
    expect(formatOptionalPercent(null)).toBe('N/A')
    expect(formatOptionalPercent(0.5)).toBe('50%')
    expect(formatOptionalPercent(0.967)).toBe('97%')
  })
})

describe('formatInclusiveEndDate', () => {
  it('subtracts one day from an exclusive upper bound to show the actual last included date', () => {
    // comparison_period_end = 2016-01-12T00:00:00Z means the cohort's last
    // real day is 2016-01-11 (see trends/pipeline.py resolve_cohort_windows).
    expect(formatInclusiveEndDate('2016-01-12T00:00:00Z')).toBe('Jan 11, 2016')
  })

  it('uses UTC, not the local timezone, so the boundary date never shifts by a day', () => {
    expect(formatInclusiveEndDate('2026-07-28T00:00:00Z')).toBe('Jul 27, 2026')
  })
})
