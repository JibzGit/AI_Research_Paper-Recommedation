import { Link } from 'react-router-dom'

import type { ClusterSummary } from '@/api/types'
import { assignClusterSymbols } from '@/lib/clusterSymbols'

interface ClusterLegendTableProps {
  clusters: ClusterSummary[]
}

/**
 * The accessible, non-chart summary of cluster distribution: a real table
 * (not an aria-label on a chart) mapping each display-only symbol back to
 * its full name, real cluster_id, paper count, and average membership
 * probability, with a link to the full Cluster Detail page. Always lists
 * every cluster -- unlike the chart above, nothing here is capped.
 */
export function ClusterLegendTable({ clusters }: ClusterLegendTableProps) {
  if (clusters.length === 0) return null

  const symbols = assignClusterSymbols(clusters)
  const sorted = [...clusters].sort((a, b) => a.cluster_id - b.cluster_id)

  return (
    <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-panel">
      <table className="w-full min-w-[36rem] text-left text-xs">
        <caption className="sr-only">All approved research clusters with their display symbol, full name, paper count, and average membership probability.</caption>
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            <th scope="col" className="px-4 py-2.5 font-medium">Symbol</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Cluster name</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Cluster ID</th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">Papers</th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">Avg. membership</th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sorted.map((cluster) => (
            <tr key={cluster.cluster_id} className="text-foreground">
              <td className="px-4 py-2.5 font-mono text-[11px] text-muted-foreground tabular-nums">{symbols.get(cluster.cluster_id)}</td>
              <td className="px-4 py-2.5 font-medium">{cluster.cluster_name}</td>
              <td className="px-4 py-2.5 tabular-nums text-muted-foreground">{cluster.cluster_id}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{cluster.paper_count}</td>
              <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">
                {(cluster.average_membership_probability * 100).toFixed(0)}%
              </td>
              <td className="px-4 py-2.5">
                <Link
                  to={`/clusters/${cluster.cluster_id}`}
                  className="rounded font-medium text-accent-blue hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
