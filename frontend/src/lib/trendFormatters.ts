import { formatUtcDate } from '@/lib/formatters'

/** growth_rate is null in exactly two legitimate cases: is_new_activity
 * (no comparison-period baseline to divide by -- shown as "New", never
 * "0%" or "+Infinity%") or a genuine 0.0 (both periods empty, a real,
 * distinct value from null -- see backend metrics.compute_growth_rate).
 * Callers must always pass is_new_activity alongside growth_rate; this
 * function never guesses which null case it is. */
export function formatGrowthRate(growthRate: number | null, isNewActivity: boolean): string {
  if (growthRate === null) return isNewActivity ? 'New' : 'N/A'
  const percent = Math.round(growthRate * 100)
  return `${percent > 0 ? '+' : ''}${percent}%`
}

export function formatSignedInt(value: number): string {
  return `${value > 0 ? '+' : ''}${value}`
}

/** For 0..1 fractional metrics (consistency, recency_score, publication
 * shares) that are nullable -- distinct from formatGrowthRate's -1..+N
 * range and null-cause semantics. */
export function formatOptionalPercent(value: number | null): string {
  if (value === null) return 'N/A'
  return `${Math.round(value * 100)}%`
}

const ONE_DAY_MS = 24 * 60 * 60 * 1000

/** trend_context's *_period_end fields are exclusive upper bounds (the
 * backend defines a cohort window as [start, last_day + 1 day) -- see
 * trends/pipeline.py's resolve_cohort_windows()), so the actual last
 * included day is one day before the raw timestamp. Displaying the raw
 * value as-is would show a day the cohort doesn't actually contain. */
export function formatInclusiveEndDate(isoExclusiveEnd: string): string {
  const exclusiveEnd = new Date(isoExclusiveEnd)
  if (Number.isNaN(exclusiveEnd.getTime())) return isoExclusiveEnd
  return formatUtcDate(new Date(exclusiveEnd.getTime() - ONE_DAY_MS).toISOString())
}
