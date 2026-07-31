import { Boxes, FileText, LineChart, Layers, Network, Radar, Shuffle, Sparkles, Tags, TrendingDown, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ClusterDistributionChart } from '@/components/charts/ClusterDistributionChart'
import { ClusterLegendTable } from '@/components/charts/ClusterLegendTable'
import { ClusterCard } from '@/components/clusters/ClusterCard'
import { CorpusSummaryPanel } from '@/components/common/CorpusSummaryPanel'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton, ChartSkeleton, StatCardSkeleton } from '@/components/common/LoadingSkeleton'
import { StatCard } from '@/components/common/StatCard'
import { CategoryCoverageSection } from '@/components/dashboard/CategoryCoverageSection'
import { CategoryVsClusterInfo } from '@/components/dashboard/CategoryVsClusterInfo'
import { RepresentativePapersSection } from '@/components/papers/RepresentativePapersSection'
import { HistoricalCohortWarning } from '@/components/trends/HistoricalCohortWarning'
import { TrendLabelGuide } from '@/components/trends/TrendLabelGuide'
import { Button } from '@/components/ui/button'
import { useCategories } from '@/hooks/useCategories'
import { useClusters } from '@/hooks/useClusters'
import { usePlatformOverview } from '@/hooks/usePlatformOverview'
import { useTrendsOverview } from '@/hooks/useTrendsOverview'
import { getClusterEmptyMessage } from '@/lib/clusterEmptyState'

type OverviewQuery = ReturnType<typeof usePlatformOverview>
type ClustersQuery = ReturnType<typeof useClusters>
type CategoriesQuery = ReturnType<typeof useCategories>
type TrendsOverviewQuery = ReturnType<typeof useTrendsOverview>

const LEADING_CLUSTERS_COUNT = 6

export function DashboardPage() {
  const overviewQuery = usePlatformOverview()
  const clustersQuery = useClusters()
  const categoriesQuery = useCategories()
  const trendsOverviewQuery = useTrendsOverview()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Dashboard</h2>
        <p className="text-sm text-muted-foreground">
          An overview of the research corpus and clustering state. Use the search bar above to find specific papers.
        </p>
      </div>

      <StatsRow overviewQuery={overviewQuery} categoriesQuery={categoriesQuery} />

      <section id="corpus-coverage" aria-label="Corpus coverage" className="flex scroll-mt-20 flex-col gap-4">
        <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Tags className="size-4 text-accent-green" aria-hidden="true" />
          Corpus coverage
        </h3>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <CategoryCoverageSection />
          </div>
          <div className="flex flex-col gap-4">
            {overviewQuery.data ? (
              <CorpusSummaryPanel overview={overviewQuery.data} />
            ) : overviewQuery.isError ? (
              <ErrorState error={overviewQuery.error ?? new Error('Failed to load corpus summary')} onRetry={() => void overviewQuery.refetch()} />
            ) : (
              <StatCardSkeleton />
            )}
          </div>
        </div>
        <CategoryVsClusterInfo />
      </section>

      <section aria-label="Cluster distribution" className="flex flex-col gap-4">
        <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Network className="size-4 text-accent-blue" aria-hidden="true" />
          Cluster distribution
        </h3>
        <p className="sr-only">Paper count for the largest approved research clusters, plus unclustered papers.</p>
        <ChartSection clustersQuery={clustersQuery} overviewQuery={overviewQuery} />
        <LegendSection clustersQuery={clustersQuery} />

        <div>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h4 className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Layers className="size-4 text-accent-purple" aria-hidden="true" />
              Leading research clusters
            </h4>
            <Button asChild variant="ghost" size="sm">
              <Link to="/clusters">View all clusters</Link>
            </Button>
          </div>
          <ClustersSection clustersQuery={clustersQuery} />
        </div>
      </section>

      <section aria-label="Research trends" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <LineChart className="size-4 text-accent-blue" aria-hidden="true" />
            Research Trends
          </h3>
          <Button asChild variant="ghost" size="sm">
            <Link to="/trends">View all trends</Link>
          </Button>
        </div>
        <TrendsSummarySection trendsOverviewQuery={trendsOverviewQuery} />
        <TrendLabelGuide />
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

function StatsRow({ overviewQuery, categoriesQuery }: { overviewQuery: OverviewQuery; categoriesQuery: CategoriesQuery }) {
  if (overviewQuery.isLoading) {
    return (
      <section
        aria-label="Platform statistics"
        aria-busy="true"
        aria-live="polite"
        className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6"
      >
        <StatCardSkeleton />
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
  const categoryCount = categoriesQuery.data?.categories.length

  return (
    <section aria-label="Platform statistics" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <StatCard
        label="Total Papers"
        value={overview.total_canonical_papers}
        icon={FileText}
        accent="purple"
        hint="Canonical papers in the corpus"
        href="/search"
      />
      <StatCard
        label="Embedded Papers"
        value={overview.embedded_papers}
        icon={Radar}
        accent="blue"
        hint={embeddedPercent === null ? 'No canonical papers yet' : `${embeddedPercent}% of corpus`}
        href="/search"
      />
      <StatCard
        label="Approved Clusters"
        value={overview.approved_clusters}
        icon={Boxes}
        accent="green"
        hint="From the latest clustering run"
        href="/clusters"
      />
      <StatCard
        label="Clustered Papers"
        value={overview.clustered_papers}
        icon={Network}
        accent="orange"
        hint={clusteredPercent === null ? 'No canonical papers yet' : `${clusteredPercent}% of corpus`}
        href="/clusters"
      />
      <StatCard
        label="Unclustered Papers"
        value={overview.noise_papers}
        icon={Shuffle}
        accent="purple"
        hint={noisePercent === null ? 'No canonical papers yet' : `${noisePercent}% of corpus`}
        href="/clusters/noise"
      />
      <StatCard
        label="Categories"
        value={categoryCount ?? '—'}
        icon={Tags}
        accent="blue"
        hint="arXiv categories represented"
        href="#corpus-coverage"
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

function LegendSection({ clustersQuery }: { clustersQuery: ClustersQuery }) {
  if (!clustersQuery.data || clustersQuery.data.clusters.length === 0) return null
  return <ClusterLegendTable clusters={clustersQuery.data.clusters} />
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
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Emerging" value={emergingCount} icon={TrendingUp} accent="green" href="/trends?classification=Emerging" />
        <StatCard label="Stable" value={stableCount} icon={LineChart} accent="blue" href="/trends?classification=Stable" />
        <StatCard label="Cooling" value={coolingCount} icon={TrendingDown} accent="orange" href="/trends?classification=Cooling" />
      </div>
      <HistoricalCohortWarning trendContext={data.trend_context} message={data.message} />
    </div>
  )
}
