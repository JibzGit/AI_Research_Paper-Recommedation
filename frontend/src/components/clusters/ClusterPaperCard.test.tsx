import { describe, expect, it } from 'vitest'

import type { ClusterPaper } from '@/api/types'
import { ClusterPaperCard } from '@/components/clusters/ClusterPaperCard'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

const BASE_PAPER: ClusterPaper = {
  paper_id: '29085b7c-11d3-4dd5-aab0-e828fd5e777e',
  arxiv_id: '1601.01507',
  title: 'Fast Kronecker product kernel methods via generalized vec trick',
  abstract: 'Kronecker product kernel provides the standard approach.',
  authors: ['Antti Airola'],
  primary_category: 'stat.ML',
  publication_date: '2016-01-07T12:25:53Z',
  membership_probability: 0.89,
  is_noise: false,
}

describe('ClusterPaperCard (cluster mode)', () => {
  it('renders working "View on arXiv" and "Open PDF" links', () => {
    renderWithProviders(<ClusterPaperCard paper={BASE_PAPER} mode="cluster" />)
    expect(screen.getByRole('link', { name: /View ".*" on arXiv, opens in a new tab/ })).toHaveAttribute(
      'href',
      'https://arxiv.org/abs/1601.01507',
    )
    expect(screen.getByRole('link', { name: /Open the PDF for ".*", opens in a new tab/ })).toHaveAttribute(
      'href',
      'https://arxiv.org/pdf/1601.01507',
    )
  })

  it('hides the PDF action when arxiv_id is unavailable', () => {
    renderWithProviders(<ClusterPaperCard paper={{ ...BASE_PAPER, arxiv_id: null }} mode="cluster" />)
    expect(screen.queryByRole('link', { name: /Open the PDF/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /on arXiv/ })).not.toBeInTheDocument()
  })
})

describe('ClusterPaperCard (noise/unclustered mode)', () => {
  it('unclustered paper cards also get working PDF access', () => {
    renderWithProviders(<ClusterPaperCard paper={{ ...BASE_PAPER, membership_probability: 0.0, is_noise: true }} mode="noise" />)
    const pdfLink = screen.getByRole('link', { name: /Open the PDF for/ })
    expect(pdfLink).toHaveAttribute('href', 'https://arxiv.org/pdf/1601.01507')
    expect(pdfLink).toHaveAttribute('target', '_blank')
    expect(pdfLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('existing internal "Explore Similar Papers" navigation still works unaffected', () => {
    renderWithProviders(<ClusterPaperCard paper={BASE_PAPER} mode="noise" />)
    const similarLink = screen.getByRole('link', { name: 'Explore Similar Papers' })
    expect(similarLink).toHaveAttribute('href', `/papers/${BASE_PAPER.paper_id}/similar`)
  })
})
