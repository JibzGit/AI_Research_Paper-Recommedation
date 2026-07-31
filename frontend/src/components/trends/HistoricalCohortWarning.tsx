import { History } from 'lucide-react'

import type { TrendContext } from '@/api/types'
import { formatUtcDate } from '@/lib/formatters'
import { formatInclusiveEndDate } from '@/lib/trendFormatters'

interface HistoricalCohortWarningProps {
  trendContext: TrendContext
  message: string
}

/** Persistent, non-dismissible banner -- every trend view must carry this,
 * never as a small footnote. Explains, in the backend's own words (the
 * `message` field), that these numbers compare two disjoint ingestion
 * cohorts rather than a continuous publication trend. Styled as
 * informational (blue), not as an error or a dismissible toast: this is
 * expected, permanent context for every result on this page, not a
 * transient problem. */
export function HistoricalCohortWarning({ trendContext, message }: HistoricalCohortWarningProps) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-accent-blue/30 bg-accent-blue/5 p-4">
      <div className="flex items-start gap-2.5">
        <History className="mt-0.5 size-4 shrink-0 text-accent-blue" aria-hidden="true" />
        <div className="flex flex-col gap-1">
          <p className="text-sm font-semibold text-foreground">{trendContext.trend_mode_label}</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
      </div>
      <dl className="ml-6.5 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <dt className="font-medium text-foreground">Comparison cohort:</dt>
          <dd>
            {formatUtcDate(trendContext.comparison_period_start)} &ndash; {formatInclusiveEndDate(trendContext.comparison_period_end)}
          </dd>
        </div>
        <div className="flex items-center gap-1.5">
          <dt className="font-medium text-foreground">Recent cohort:</dt>
          <dd>
            {formatUtcDate(trendContext.recent_period_start)} &ndash; {formatInclusiveEndDate(trendContext.recent_period_end)}
          </dd>
        </div>
      </dl>
    </div>
  )
}
