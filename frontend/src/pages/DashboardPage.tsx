import { Boxes, FileText, LineChart, Layers, Network, Radar, Shuffle, Sparkles, TrendingDown, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ClusterDistributionChart } from '@/components/charts/ClusterDistributionChart'
import { ClusterCard } from '@/components/clusters/ClusterCard'
import { CorpusSummaryPanel } from '@/components/common/CorpusSummaryPanel'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton, ChartSkeleton, StatCardSkeleton } from '@/components/common/LoadingSkeleton'
import { StatCard } from '@/components/common/StatCard'
import { RepresentativePapersSection } from '@/components/papers/RepresentativePapersSection'
import { Button } from '@/components/ui/button'
import { useClusters } from '@/hooks/useClusters'
import { usePlatformOverview } from '@/hooks/usePlatformOverview'
import { useTrendsOverview } from '@/hooks/useTrendsOverview'
import { getClusterEmptyMessage } from '@/lib/clusterEmptyState'

type OverviewQuery = ReturnType<typeof usePlatformOverview>
type ClustersQuery = ReturnType<typeof useClusters>
type TrendsOverviewQuery = ReturnType<typeof useTrendsOverview>

const LEADING_CLUSTERS_COUNT = 6

export function DashboardPage() {
  const overviewQuery = usePlatformOverview()
  const clustersQuery = useClusters()
  const trendsOverviewQuery = useTrendsOverview()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Dashboard</h2>
        <p className="text-sm text-muted-foreground">An overview of the research corpus and clustering state.</p>
      </div>

      <StatsRow overviewQuery={overviewQuery} />

      <div className="grid gap-4 lg:grid-cols-3">
        <section aria-label="Cluster distribution" className="lg:col-span-2">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
            <Network className="size-4 text-accent-blue" aria-hidden="true" />
            Cluster distribution
          </h3>
          <p className="sr-only">Paper count for each approved research cluster, plus unclustered papers.</p>
          <ChartSection clustersQuery={clustersQuery} overviewQuery={overviewQuery} />
        </section>

        <section aria-label="Corpus summary">
          {overviewQuery.data ? (
            <CorpusSummaryPanel overview={overviewQuery.data} />
          ) : overviewQuery.isError ? (
            <ErrorState error={overviewQuery.error ?? new Error('Failed to load corpus summary')} onRetry={() => void overviewQuery.refetch()} />
          ) : (
            <StatCardSkeleton />
          )}
        </section>
      </div>

      <section aria-label="Leading research clusters">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
          <Layers className="size-4 text-accent-purple" aria-hidden="true" />
          Leading research clusters
        </h3>
        <ClustersSection clustersQuery={clustersQuery} />
      </section>

      <section aria-label="Research trends">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <LineChart className="size-4 text-accent-blue" aria-hidden="true" />
            Research Trends
          </h3>
          <Button asChild variant="ghost" size="sm">
            <Link to="/trends">View all trends</Link>
          </Button>
        </div>
        <TrendsSummarySection trendsOverviewQuery={trendsOverviewQuery} />
      </section>

      <section aria-label="Representative papers from leading clusters">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
          <Sparkles className="size-4 text-accent-green" aria-hidden="true" />
          Representative Papers from Leading Clusters
        </h3>
        <RepresentativePapersSection clusters={clustersQuery.data?.clusters} clustersLoading={clustersQuery.isLoading} />
      </section>
    </div>
  )
}

function StatsRow({ overviewQuery }: { overviewQuery: OverviewQuery }) {
  if (overviewQuery.isLoading) {
    return (
      <section
        aria-label="Platform statistics"
        aria-busy="true"
        aria-live="polite"
        className="grid grid-cols-2 gap-3 md:grid-cols-5"
      >
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
      </section>
    )
  }

  if (overviewQuery.isError) {
    return (
      <section aria-label="Platform statistics">
        <ErrorState
          error={overviewQuery.error ?? new Error('Failed to load platform statistics')}
          onRetry={() => void overviewQuery.refetch()}
        />
      </section>
    )
  }

  const overview = overviewQuery.data
  if (!overview) return null

  const embeddedPercent =
    overview.total_canonical_papers > 0 ? Math.round((overview.embedded_papers / overview.total_canonical_papers) * 100) : null
  const clusteredPercent =
    overview.total_canonical_papers > 0 ? Math.round((overview.clustered_papers / overview.total_canonical_papers) * 100) : null
  const noisePercent =
    overview.total_canonical_papers > 0 ? Math.round((overview.noise_papers / overview.total_canonical_papers) * 100) : null

  return (
    <section aria-label="Platform statistics" className="grid grid-cols-2 gap-3 md:grid-cols-5">
      <StatCard label="Total Papers" value={overview.total_canonical_papers} icon={FileText} accent="purple" hint="Canonical papers in the corpus" />
      <StatCard
        label="Embedded Papers"
        value={overview.embedded_papers}
        icon={Radar}
        accent="blue"
        hint={embeddedPercent === null ? 'No canonical papers yet' : `${embeddedPercent}% of corpus`}
      />
      <StatCard label="Approved Clusters" value={overview.approved_clusters} icon={Boxes} accent="green" hint="From the latest clustering run" />
      <StatCard
        label="Clustered Papers"
        value={overview.clustered_papers}
        icon={Network}
        accent="orange"
        hint={clusteredPercent === null ? 'No canonical papers yet' : `${clusteredPercent}% of corpus`}
      />
      <StatCard
        label="Unclustered Papers"
        value={overview.noise_papers}
        icon={Shuffle}
        accent="purple"
        hint={noisePercent === null ? 'No canonical papers yet' : `${noisePercent}% of corpus`}
      />
    </section>
  )
}

function ChartSection({ clustersQuery, overviewQuery }: { clustersQuery: ClustersQuery; overviewQuery: OverviewQuery }) {
  if (clustersQuery.isLoading) {
    return <ChartSkeleton />
  }
  if (clustersQuery.isError) {
    return <ErrorState error={clustersQuery.error ?? new Error('Failed to load clusters')} onRetry={() => void clustersQuery.refetch()} />
  }
  if (!clustersQuery.data) return null

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-panel">
      <ClusterDistributionChart
        clusters={clustersQuery.data.clusters}
        noisePaperCount={overviewQuery.data?.noise_papers ?? 0}
        emptyDescription={getClusterEmptyMessage(clustersQuery.data)}
      />
    </div>
  )
}

function ClustersSection({ clustersQuery }: { clustersQuery: ClustersQuery }) {
  if (clustersQuery.isLoading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-live="polite">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    )
  }
  if (clustersQuery.isError) {
    return <ErrorState error={clustersQuery.error ?? new Error('Failed to load clusters')} onRetry={() => void clustersQuery.refetch()} />
  }
  if (!clustersQuery.data) return null

  if (clustersQuery.data.clusters.length === 0) {
    return <EmptyState icon={Layers} title={getClusterEmptyMessage(clustersQuery.data)} />
  }

  const leadingClusters = clustersQuery.data.clusters.slice(0, LEADING_CLUSTERS_COUNT)

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {leadingClusters.map((cluster) => (
        <ClusterCard key={cluster.cluster_id} cluster={cluster} />
      ))}
    </div>
  )
}

/** Degrades gracefully on 503 ("no successful trend run yet") -- shown as
 * a quiet empty state, not an alarming ErrorState, since this is expected
 * on a fresh install and shouldn't read as the dashboard being broken.
 * Any other failure (network, 5xx) still surfaces through ErrorState like
 * every other dashboard section. */
function TrendsSummarySection({ trendsOverviewQuery }: { trendsOverviewQuery: TrendsOverviewQuery }) {
  if (trendsOverviewQuery.isLoading) {
    return (
      <div className="grid grid-cols-3 gap-3" aria-busy="true" aria-live="polite">
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
      </div>
    )
  }

  if (trendsOverviewQuery.isError) {
    const error = trendsOverviewQuery.error
    if (error?.status === 503) {
      return <EmptyState icon={LineChart} title="Trend analysis not yet available" description={error.detail} />
    }
    return <ErrorState error={error ?? new Error('Failed to load trend overview')} onRetry={() => void trendsOverviewQuery.refetch()} />
  }

  const data = trendsOverviewQuery.data
  if (!data) return null

  const emergingCount = (data.cluster_summary.classification_counts.Emerging ?? 0) + (data.category_summary.classification_counts.Emerging ?? 0)
  const stableCount = (data.cluster_summary.classification_counts.Stable ?? 0) + (data.category_summary.classification_counts.Stable ?? 0)
  const coolingCount = (data.cluster_summary.classification_counts.Cooling ?? 0) + (data.category_summary.classification_counts.Cooling ?? 0)

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Emerging" value={emergingCount} icon={TrendingUp} accent="green" />
        <StatCard label="Stable" value={stableCount} icon={LineChart} accent="blue" />
        <StatCard label="Cooling" value={coolingCount} icon={TrendingDown} accent="orange" />
      </div>
      <p className="text-xs text-muted-foreground">
        {data.trend_context.trend_mode_label}: comparing the corpus's two ingestion cohorts, not a continuous publication trend.
      </p>
    </div>
  )
}
