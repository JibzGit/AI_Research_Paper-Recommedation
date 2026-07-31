import { Boxes, FileText, Layers, Network, Radar, Shuffle, Sparkles } from 'lucide-react'

import { ClusterDistributionChart } from '@/components/charts/ClusterDistributionChart'
import { ClusterCard } from '@/components/clusters/ClusterCard'
import { CorpusSummaryPanel } from '@/components/common/CorpusSummaryPanel'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton, ChartSkeleton, StatCardSkeleton } from '@/components/common/LoadingSkeleton'
import { StatCard } from '@/components/common/StatCard'
import { RepresentativePapersSection } from '@/components/papers/RepresentativePapersSection'
import { useClusters } from '@/hooks/useClusters'
import { usePlatformOverview } from '@/hooks/usePlatformOverview'
import { getClusterEmptyMessage } from '@/lib/clusterEmptyState'

type OverviewQuery = ReturnType<typeof usePlatformOverview>
type ClustersQuery = ReturnType<typeof useClusters>

const LEADING_CLUSTERS_COUNT = 6

export function DashboardPage() {
  const overviewQuery = usePlatformOverview()
  const clustersQuery = useClusters()

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
