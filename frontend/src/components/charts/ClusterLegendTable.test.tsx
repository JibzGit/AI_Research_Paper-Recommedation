import { describe, expect, it } from 'vitest'

import type { ClusterSummary } from '@/api/types'
import { ClusterLegendTable } from '@/components/charts/ClusterLegendTable'
import { renderWithProviders, screen, within } from '@/test/renderWithProviders'

const CLUSTERS: ClusterSummary[] = [
  {
    cluster_id: 7,
    cluster_name: 'Graph Representation Learning',
    short_description: '',
    paper_count: 14,
    label_confidence: 0.7,
    top_keywords: [],
    dominant_category: 'cs.LG',
    average_membership_probability: 0.813,
    clustering_run_id: 'run-1',
  },
  {
    cluster_id: 1,
    cluster_name: 'Medical Imaging AI',
    short_description: '',
    paper_count: 6,
    label_confidence: 0.6,
    top_keywords: [],
    dominant_category: 'eess.IV',
    average_membership_probability: 0.5,
    clustering_run_id: 'run-1',
  },
]

describe('ClusterLegendTable', () => {
  it('renders every cluster with its display symbol mapped to the full name, real ID, count, and membership', () => {
    renderWithProviders(<ClusterLegendTable clusters={CLUSTERS} />)

    // Sorted by cluster_id ascending: cluster 1 -> C01, cluster 7 -> C02.
    const [row0, row1] = screen.getAllByRole('row').slice(1) // skip header row
    expect(within(row0!).getByText('C01')).toBeInTheDocument()
    expect(within(row0!).getByText('Medical Imaging AI')).toBeInTheDocument()
    expect(within(row0!).getByText('1')).toBeInTheDocument()
    expect(within(row0!).getByText('6')).toBeInTheDocument()
    expect(within(row0!).getByText('50%')).toBeInTheDocument()

    expect(within(row1!).getByText('C02')).toBeInTheDocument()
    expect(within(row1!).getByText('Graph Representation Learning')).toBeInTheDocument()
  })

  it('links each cluster row to its real Cluster Detail page (never the display symbol)', () => {
    renderWithProviders(<ClusterLegendTable clusters={CLUSTERS} />)
    const links = screen.getAllByRole('link', { name: 'View' })
    expect(links[0]).toHaveAttribute('href', '/clusters/1')
    expect(links[1]).toHaveAttribute('href', '/clusters/7')
  })

  it('renders nothing when there are no clusters', () => {
    const { container } = renderWithProviders(<ClusterLegendTable clusters={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
