import { describe, expect, it } from 'vitest'

import type { ClusterSummary } from '@/api/types'
import { assignClusterSymbols } from '@/lib/clusterSymbols'

function makeCluster(clusterId: number): ClusterSummary {
  return {
    cluster_id: clusterId,
    cluster_name: `Cluster ${clusterId}`,
    short_description: '',
    paper_count: 1,
    label_confidence: 0.5,
    top_keywords: [],
    dominant_category: null,
    average_membership_probability: 0.5,
    clustering_run_id: 'run-1',
  }
}

describe('assignClusterSymbols', () => {
  it('assigns stable, zero-padded symbols ordered by cluster_id, independent of input order', () => {
    const clusters = [makeCluster(5), makeCluster(0), makeCluster(2)]
    const symbols = assignClusterSymbols(clusters)
    expect(symbols.get(0)).toBe('C01')
    expect(symbols.get(2)).toBe('C02')
    expect(symbols.get(5)).toBe('C03')
  })

  it('never uses cluster_id as the symbol -- symbols are purely positional', () => {
    const clusters = [makeCluster(42)]
    const symbols = assignClusterSymbols(clusters)
    expect(symbols.get(42)).toBe('C01')
  })
})
