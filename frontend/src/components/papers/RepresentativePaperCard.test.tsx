import { describe, expect, it } from 'vitest'

import { RepresentativePaperCard, type RepresentativePaperCardData } from '@/components/papers/RepresentativePaperCard'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

const BASE_PAPER: RepresentativePaperCardData = {
  paperId: '29085b7c-11d3-4dd5-aab0-e828fd5e777e',
  arxivId: '1601.01507',
  title: 'Fast Kronecker product kernel methods via generalized vec trick',
  clusterId: 2,
  clusterName: 'Visual Recognition, Segmentation, and Localization',
}

describe('RepresentativePaperCard (Dashboard)', () => {
  it('the Dashboard representative-paper card gets Find Similar Papers, View on arXiv, and Open PDF', () => {
    renderWithProviders(<RepresentativePaperCard paper={BASE_PAPER} />)
    expect(screen.getByRole('link', { name: 'Find Similar Papers' })).toHaveAttribute('href', `/papers/${BASE_PAPER.paperId}/similar`)
    expect(screen.getByRole('link', { name: /View ".*" on arXiv, opens in a new tab/ })).toHaveAttribute(
      'href',
      'https://arxiv.org/abs/1601.01507',
    )
    const pdfLink = screen.getByRole('link', { name: /Open the PDF for ".*", opens in a new tab/ })
    expect(pdfLink).toHaveAttribute('href', 'https://arxiv.org/pdf/1601.01507')
    expect(pdfLink).toHaveAttribute('target', '_blank')
    expect(pdfLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('hides arXiv and PDF actions when arxivId is unavailable, but keeps internal navigation', () => {
    renderWithProviders(<RepresentativePaperCard paper={{ ...BASE_PAPER, arxivId: null }} />)
    expect(screen.queryByRole('link', { name: /Open the PDF/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /on arXiv/ })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Find Similar Papers' })).toBeInTheDocument()
  })

  it('existing "From cluster" internal navigation still works unaffected', () => {
    renderWithProviders(<RepresentativePaperCard paper={BASE_PAPER} />)
    expect(screen.getByRole('link', { name: /From/ })).toHaveAttribute('href', `/clusters/${BASE_PAPER.clusterId}`)
  })
})
