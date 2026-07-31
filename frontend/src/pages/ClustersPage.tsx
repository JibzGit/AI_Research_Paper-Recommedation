import { Boxes, Calculator, ChevronRight, Layers, Network, Shuffle } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import type { ClusterListResponse } from '@/api/types'
import { ClusterDistributionChart } from '@/components/charts/ClusterDistributionChart'
import { ClusterCard } from '@/components/clusters/ClusterCard'
import { ClusterDiscoveryControls } from '@/components/clusters/ClusterDiscoveryControls'
import { UnclusteredCallout } from '@/components/clusters/UnclusteredCallout'
import { ClearFiltersButton } from '@/components/papers/ClearFiltersButton'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton, ChartSkeleton, StatCardSkeleton } from '@/components/common/LoadingSkeleton'
import { StatCard } from '@/components/common/StatCard'
import { useClusters } from '@/hooks/useClusters'
import { usePlatformOverview } from '@/hooks/usePlatformOverview'
import {
  DEFAULT_CLUSTER_DISCOVERY_VALUES,
  availableDominantCategories,
  clusterDiscoveryValuesFromUrl,
  filterAndSortClusters,
  urlParamsFromClusterDiscovery,
  type ClusterDiscoveryValues,
  type ClusterSortOption,
} from '@/lib/clusterDiscoveryParams'
import { getClusterEmptyMessage } from '@/lib/clusterEmptyState'

type OverviewQuery = ReturnType<typeof usePlatformOverview>
type ClustersQuery = ReturnType<typeof useClusters>

export function ClustersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const discoveryValues = clusterDiscoveryValuesFromUrl(searchParams)

  const overviewQuery = usePlatformOverview()
  const clustersQuery = useClusters()

  // No draft/commit split needed: nothing here triggers a network request,
  // so every change writes straight to the URL. replace:true keeps typing
  // in the search box from spamming browser history.
  function updateDiscovery(patch: Partial<ClusterDiscoveryValues>) {
    setSearchParams(urlParamsFromClusterDiscovery({ ...discoveryValues, ...patch }), { replace: true })
  }

  function handleSearchChange(value: string) {
    updateDiscovery({ search: value })
  }
  function handleCategoryChange(value: string | null) {
    updateDiscovery({ category: value })
  }
  function handleSortChange(value: ClusterSortOption) {
    updateDiscovery({ sort: value })
  }
  function handleClear() {
    setSearchParams(urlParamsFromClusterDiscovery(DEFAULT_CLUSTER_DISCOVERY_VALUES), { replace: true })
  }

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs />
      <PageHeader />
      <StatsRow overviewQuery={overviewQuery} />

      <div className="grid gap-4 lg:grid-cols-3">
        <section aria-label="Cluster distribution" className="rounded-2xl border border-border bg-card p-4 shadow-panel lg:col-span-2">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
            <Network className="size-4 text-accent-blue" aria-hidden="true" />
            Cluster distribution
          </h3>
          <p className="sr-only">Paper count for each approved research cluster, plus unclustered papers.</p>
          <ChartSection clustersQuery={clustersQuery} overviewQuery={overviewQuery} />
        </section>

        <section aria-label="Unclustered papers">{overviewQuery.data && <UnclusteredCallout noisePaperCount={overviewQuery.data.noise_papers} />}</section>
      </div>

      <ClustersSection
        clustersQuery={clustersQuery}
        discoveryValues={discoveryValues}
        onSearchChange={handleSearchChange}
        onCategoryChange={handleCategoryChange}
        onSortChange={handleSortChange}
        onClear={handleClear}
      />
    </div>
  )
}

function Breadcrumbs() {
  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
      <Link to="/" className="shrink-0 rounded hover:text-foreground hover:underline focus-visible:outline-none">
        Dashboard
      </Link>
      <ChevronRight className="size-3 shrink-0" aria-hidden="true" />
      <span className="truncate text-foreground" aria-current="page">
        Research Clusters
      </span>
    </nav>
  )
}

function PageHeader() {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-5 shadow-panel">
      {/* h2, not h1: TopBar already renders the page's one document h1
       * (the route title, "Research Clusters" for this route) -- every
       * other page in this app uses h2 for its main in-content heading. */}
      <h2 className="text-lg font-semibold text-foreground">Research Clusters</h2>
      <p className="text-sm text-muted-foreground">
        Explore research topics discovered from semantic paper embeddings using dimensionality reduction and
        density-based clustering.
      </p>
      <p className="text-xs text-muted-foreground/70">
        Cluster labels describe the themes found in the current corpus and may evolve as new papers are added.
      </p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 pt-1 text-xs text-muted-foreground">
        <Link to="/clusters/noise" className="rounded hover:text-foreground hover:underline focus-visible:outline-none">
          Unclustered Papers
        </Link>
        <Link to="/" className="rounded hover:text-foreground hover:underline focus-visible:outline-none">
          Dashboard
        </Link>
      </div>
    </div>
  )
}

function StatsRow({ overviewQuery }: { overviewQuery: OverviewQuery }) {
  if (overviewQuery.isLoading) {
    return (
      <section
        aria-label="Cluster statistics"
        aria-busy="true"
        aria-live="polite"
        className="grid grid-cols-2 gap-3 md:grid-cols-4"
      >
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
      </section>
    )
  }

  if (overviewQuery.isError) {
    return (
      <section aria-label="Cluster statistics">
        <ErrorState error={overviewQuery.error ?? new Error('Failed to load cluster statistics')} onRetry={() => void overviewQuery.refetch()} />
      </section>
    )
  }

  const overview = overviewQuery.data
  if (!overview) return null

  const avgPapersPerCluster = overview.approved_clusters > 0 ? Math.round((overview.clustered_papers / overview.approved_clusters) * 10) / 10 : null

  return (
    <section aria-label="Cluster statistics" className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatCard label="Approved Clusters" value={overview.approved_clusters} icon={Boxes} accent="green" hint="From the latest clustering run" />
      <StatCard label="Clustered Papers" value={overview.clustered_papers} icon={Network} accent="orange" />
      <StatCard label="Unclustered Papers" value={overview.noise_papers} icon={Shuffle} accent="purple" />
      <StatCard
        label="Avg. Papers / Cluster"
        value={avgPapersPerCluster === null ? '—' : avgPapersPerCluster}
        icon={Calculator}
        accent="blue"
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
    <ClusterDistributionChart
      clusters={clustersQuery.data.clusters}
      noisePaperCount={overviewQuery.data?.noise_papers ?? 0}
      emptyDescription={getClusterEmptyMessage(clustersQuery.data)}
    />
  )
}

function ClustersSection({
  clustersQuery,
  discoveryValues,
  onSearchChange,
  onCategoryChange,
  onSortChange,
  onClear,
}: {
  clustersQuery: ClustersQuery
  discoveryValues: ClusterDiscoveryValues
  onSearchChange: (value: string) => void
  onCategoryChange: (value: string | null) => void
  onSortChange: (value: ClusterSortOption) => void
  onClear: () => void
}) {
  if (clustersQuery.isLoading) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-live="polite">
        <StatCardSkeleton />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    )
  }

  if (clustersQuery.isError) {
    return <ErrorState error={clustersQuery.error ?? new Error('Failed to load clusters')} onRetry={() => void clustersQuery.refetch()} />
  }

  const data = clustersQuery.data
  if (!data) return null

  if (data.clusters.length === 0) {
    return <EmptyState icon={Layers} title={getClusterEmptyMessage(data)} />
  }

  const categories = availableDominantCategories(data.clusters)
  const visibleClusters = filterAndSortClusters(data.clusters, discoveryValues)

  return (
    <div className="flex flex-col gap-3">
      <ClusterDiscoveryControls
        values={discoveryValues}
        categories={categories}
        onSearchChange={onSearchChange}
        onCategoryChange={onCategoryChange}
        onSortChange={onSortChange}
        onClear={onClear}
        visibleCount={visibleClusters.length}
        totalCount={data.clusters.length}
      />

      {visibleClusters.length === 0 ? (
        <FilteredEmptyState onClear={onClear} data={data} />
      ) : (
        <>
          <h3 className="sr-only">Clusters</h3>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visibleClusters.map((cluster) => (
              <ClusterCard key={cluster.cluster_id} cluster={cluster} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function FilteredEmptyState({ onClear, data }: { onClear: () => void; data: ClusterListResponse }) {
  return (
    <EmptyState
      icon={Layers}
      title="No research clusters matched these filters."
      description="Try clearing the search, removing the category filter, or resetting sorting to browse all clusters."
      action={
        <div className="flex items-center gap-2">
          <ClearFiltersButton onClear={onClear} />
          <span className="text-xs text-muted-foreground">{data.count} clusters available</span>
        </div>
      }
    />
  )
}
