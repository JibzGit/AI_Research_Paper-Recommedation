import type { ClusterListResponse } from '@/api/types'

/** Shared by the cluster section and the distribution chart, both of which
 * depend on the same GET /api/v1/clusters response and need to distinguish
 * "no run has ever succeeded" from "a run succeeded but nothing is
 * approved yet" -- two different, both-valid empty outcomes. */
export function getClusterEmptyMessage(clusterList: ClusterListResponse | undefined): string {
  if (!clusterList || clusterList.clustering_run_id === null) {
    return 'No successful clustering run is available yet.'
  }
  return 'No approved research clusters are available.'
}
