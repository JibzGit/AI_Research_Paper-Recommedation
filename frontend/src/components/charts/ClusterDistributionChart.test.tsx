import { describe, expect, it } from 'vitest'

import type { ClusterSummary } from '@/api/types'
import { ClusterDistributionChart } from '@/components/charts/ClusterDistributionChart'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

function makeCluster(clusterId: number, paperCount: number): ClusterSummary {
  return {
    cluster_id: clusterId,
    cluster_name: `Research Cluster Number ${clusterId}`,
    short_description: '',
    paper_count: paperCount,
    label_confidence: 0.7,
    top_keywords: [],
    dominant_category: null,
    average_membership_probability: 0.6,
    clustering_run_id: 'run-1',
  }
}

describe('ClusterDistributionChart', () => {
  it('shows an empty state when there are no clusters and no unclustered papers', () => {
    renderWithProviders(<ClusterDistributionChart clusters={[]} noisePaperCount={0} />)
    expect(screen.getByText('No cluster data available')).toBeInTheDocument()
  })

  it('describes the chart via an accessible label rather than relying on the chart image alone', () => {
    const clusters = [makeCluster(0, 10), makeCluster(1, 5)]
    renderWithProviders(<ClusterDistributionChart clusters={clusters} noisePaperCount={3} />)
    const chart = screen.getByRole('img')
    expect(chart.getAttribute('aria-label')).toMatch(/2 largest research clusters/)
    expect(chart.getAttribute('aria-label')).toMatch(/plus unclustered papers/)
  })

  it('caps the chart to maxBars and surfaces a note pointing to the full table for the rest', () => {
    const clusters = Array.from({ length: 5 }, (_, i) => makeCluster(i, 10 - i))
    renderWithProviders(<ClusterDistributionChart clusters={clusters} noisePaperCount={0} maxBars={3} />)
    expect(screen.getByText(/Showing the 3 largest of 5 clusters/)).toBeInTheDocument()
  })

  it('does not show the "showing N of M" note when every cluster fits', () => {
    const clusters = [makeCluster(0, 10), makeCluster(1, 5)]
    renderWithProviders(<ClusterDistributionChart clusters={clusters} noisePaperCount={0} maxBars={8} />)
    expect(screen.queryByText(/Showing the/)).not.toBeInTheDocument()
  })
})
