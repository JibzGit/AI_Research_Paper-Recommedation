import { Link } from 'react-router-dom'

import type { TrendClassification, TrendDataQuality, TrendResult } from '@/api/types'
import { DataQualityBadge } from '@/components/trends/DataQualityBadge'
import { TrendClassificationBadge } from '@/components/trends/TrendClassificationBadge'
import { formatGrowthRate, formatSignedInt } from '@/lib/trendFormatters'

interface TrendResultCardProps {
  result: TrendResult
}

export function TrendResultCard({ result }: TrendResultCardProps) {
  const { metrics, score } = result

  return (
    <Link
      to={`/trends/${result.entity_type}/${result.entity_id}`}
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel transition-colors hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground">{result.entity_name}</h4>
        <span className="shrink-0 text-lg font-semibold text-foreground tabular-nums">{score.trend_score}</span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <TrendClassificationBadge classification={score.trend_classification as TrendClassification} />
        <DataQualityBadge level={score.data_quality_level as TrendDataQuality} />
      </div>

      <dl className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
        <div>
          <dt className="text-[11px] tracking-wide uppercase">Comparison</dt>
          <dd className="tabular-nums text-foreground">{metrics.previous_paper_count} papers</dd>
        </div>
        <div>
          <dt className="text-[11px] tracking-wide uppercase">Recent</dt>
          <dd className="tabular-nums text-foreground">{metrics.recent_paper_count} papers</dd>
        </div>
        <div>
          <dt className="text-[11px] tracking-wide uppercase">Growth</dt>
          <dd className="tabular-nums text-foreground">
            {formatGrowthRate(metrics.growth_rate, metrics.is_new_activity)} ({formatSignedInt(metrics.absolute_growth)})
          </dd>
        </div>
      </dl>
    </Link>
  )
}
