import { AlertTriangle, ChevronRight, FileX } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import type { TrendClassification, TrendDataQuality, TrendEntityType, TrendEvidencePaper, TrendMetrics } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton, ChartSkeleton, StatCardSkeleton } from '@/components/common/LoadingSkeleton'
import { DataQualityBadge } from '@/components/trends/DataQualityBadge'
import { HistoricalCohortWarning } from '@/components/trends/HistoricalCohortWarning'
import { TrendClassificationBadge } from '@/components/trends/TrendClassificationBadge'
import { TrendEvidencePaperItem } from '@/components/trends/TrendEvidencePaperItem'
import { Button } from '@/components/ui/button'
import { useTrendEntityDetail } from '@/hooks/useTrendEntityDetail'
import { formatGrowthRate, formatOptionalPercent, formatSignedInt } from '@/lib/trendFormatters'

const VALID_ENTITY_TYPES: TrendEntityType[] = ['cluster', 'category']

function isValidEntityType(value: string | undefined): value is TrendEntityType {
  return value !== undefined && (VALID_ENTITY_TYPES as string[]).includes(value)
}

export function TrendEntityDetailPage() {
  const { entityType: entityTypeParam, entityId } = useParams<{ entityType: string; entityId: string }>()
  const isValid = isValidEntityType(entityTypeParam) && Boolean(entityId)
  const entityType = isValid ? (entityTypeParam as TrendEntityType) : undefined

  const detailQuery = useTrendEntityDetail(entityType, entityId, undefined, { enabled: isValid })

  if (!isValid) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="This trend link is invalid."
        description="The link you followed doesn't contain a valid entity type and identifier."
        action={
          <Button asChild variant="outline" size="sm">
            <Link to="/trends">Back to Research Trends</Link>
          </Button>
        }
      />
    )
  }

  if (detailQuery.isLoading) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-live="polite">
        <StatCardSkeleton />
        <ChartSkeleton />
        <CardSkeleton />
      </div>
    )
  }

  if (detailQuery.isError) {
    const error = detailQuery.error
    if (error?.status === 404) {
      return (
        <EmptyState
          icon={FileX}
          title="This trend result could not be found."
          description="It may not exist, or may not have been scored in the resolved trend analysis run."
          action={
            <Button asChild variant="outline" size="sm">
              <Link to="/trends">Back to Research Trends</Link>
            </Button>
          }
        />
      )
    }
    return <ErrorState error={error ?? new Error('Failed to load trend detail')} onRetry={() => void detailQuery.refetch()} />
  }

  const data = detailQuery.data
  if (!data) return null

  const { result, trend_context: trendContext, recent_period_evidence: recentEvidence, comparison_period_evidence: comparisonEvidence } = data
  const { metrics, score } = result

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs entityType={entityType as TrendEntityType} entityName={result.entity_name} />

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 className="text-lg font-semibold text-foreground">{result.entity_name}</h2>
            <p className="text-xs text-muted-foreground uppercase">{entityType === 'cluster' ? 'Research cluster' : 'arXiv category'}</p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className="text-3xl font-semibold text-foreground tabular-nums">{score.trend_score}</span>
            <span className="text-xs text-muted-foreground">Trend score</span>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5">
          <TrendClassificationBadge classification={score.trend_classification as TrendClassification} />
          <DataQualityBadge level={score.data_quality_level as TrendDataQuality} />
        </div>

        <HistoricalCohortWarning trendContext={trendContext} message="This result compares the corpus's two ingestion cohorts -- see the dates below -- not a continuous publication trend." />
      </div>

      <MetricsGrid metrics={metrics} momentumScore={score.momentum_score} />

      <section className="grid gap-4 md:grid-cols-2">
        <EvidenceColumn title="Recent cohort evidence" papers={recentEvidence} />
        <EvidenceColumn title="Comparison cohort evidence" papers={comparisonEvidence} />
      </section>
    </div>
  )
}

function Breadcrumbs({ entityType, entityName }: { entityType: TrendEntityType; entityName: string }) {
  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
      <Link to="/" className="shrink-0 rounded hover:text-foreground hover:underline focus-visible:outline-none">
        Dashboard
      </Link>
      <ChevronRight className="size-3 shrink-0" aria-hidden="true" />
      <Link to="/trends" className="shrink-0 rounded hover:text-foreground hover:underline focus-visible:outline-none">
        Research Trends
      </Link>
      <ChevronRight className="size-3 shrink-0" aria-hidden="true" />
      <span className="truncate text-foreground" aria-current="page">
        {entityType === 'cluster' ? 'Cluster: ' : 'Category: '}
        {entityName}
      </span>
    </nav>
  )
}

function MetricsGrid({ metrics, momentumScore }: { metrics: TrendMetrics; momentumScore: number | null }) {
  const items: Array<{ label: string; value: string }> = [
    { label: 'Recent cohort papers', value: String(metrics.recent_paper_count) },
    { label: 'Comparison cohort papers', value: String(metrics.previous_paper_count) },
    { label: 'Absolute growth', value: formatSignedInt(metrics.absolute_growth) },
    { label: 'Growth rate', value: formatGrowthRate(metrics.growth_rate, metrics.is_new_activity) },
    { label: 'Recent publication share', value: formatOptionalPercent(metrics.recent_publication_share) },
    { label: 'Comparison publication share', value: formatOptionalPercent(metrics.previous_publication_share) },
    { label: 'Consistency', value: formatOptionalPercent(metrics.consistency) },
    { label: 'Recency', value: formatOptionalPercent(metrics.recency_score) },
    { label: 'Momentum score', value: momentumScore === null ? 'N/A' : momentumScore.toFixed(2) },
    { label: 'Total papers (both cohorts)', value: String(metrics.total_papers) },
  ]

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-panel" aria-label="Trend metrics">
      <h3 className="mb-3 text-sm font-medium text-foreground">Metrics</h3>
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {items.map((item) => (
          <div key={item.label}>
            <dt className="text-[11px] tracking-wide text-muted-foreground uppercase">{item.label}</dt>
            <dd className="text-sm font-medium text-foreground tabular-nums">{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function EvidenceColumn({ title, papers }: { title: string; papers: TrendEvidencePaper[] }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-panel">
      <h3 className="mb-3 text-sm font-medium text-foreground">{title}</h3>
      {papers.length === 0 ? (
        <p className="text-xs text-muted-foreground">No evidence papers for this cohort.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {papers.map((paper) => (
            <TrendEvidencePaperItem key={paper.paper_id} paper={paper} />
          ))}
        </ul>
      )}
    </div>
  )
}
