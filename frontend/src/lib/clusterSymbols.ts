import type { ClusterSummary } from '@/api/types'

/**
 * Short, stable display-only symbols (C01, C02, ...) for compact chart/
 * legend labeling. Assigned by ascending cluster_id so the same cluster
 * always gets the same symbol across renders -- but this is purely a
 * display label. The real `cluster_id` remains the only identifier used
 * for links, API calls, or any application logic.
 */
export function assignClusterSymbols(clusters: ClusterSummary[]): Map<number, string> {
  const sorted = [...clusters].sort((a, b) => a.cluster_id - b.cluster_id)
  const width = String(sorted.length).length < 2 ? 2 : String(sorted.length).length
  const symbols = new Map<number, string>()
  sorted.forEach((cluster, index) => {
    symbols.set(cluster.cluster_id, `C${String(index + 1).padStart(width, '0')}`)
  })
  return symbols
}
