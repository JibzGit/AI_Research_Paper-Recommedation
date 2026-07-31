import { describe, expect, it } from 'vitest'

import type { PaperDetail } from '@/api/types'
import { SelectedPaperSummary } from '@/components/papers/SelectedPaperSummary'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

const BASE_PAPER: PaperDetail = {
  paper_id: '29085b7c-11d3-4dd5-aab0-e828fd5e777e',
  arxiv_id: '1601.01507',
  title: 'Fast Kronecker product kernel methods via generalized vec trick',
  abstract: 'Kronecker product kernel provides the standard approach.',
  authors: ['Antti Airola'],
  primary_category: 'stat.ML',
  publication_date: '2016-01-07T12:25:53Z',
  current_version_number: 1,
  embedding_available: true,
}

describe('SelectedPaperSummary (paper detail view)', () => {
  it('the existing paper detail view gets a working "Open PDF" action alongside "View on arXiv"', () => {
    renderWithProviders(<SelectedPaperSummary paper={BASE_PAPER} />)
    expect(screen.getByRole('link', { name: /View ".*" on arXiv, opens in a new tab/ })).toHaveAttribute(
      'href',
      'https://arxiv.org/abs/1601.01507',
    )
    const pdfLink = screen.getByRole('link', { name: /Open the PDF for ".*", opens in a new tab/ })
    expect(pdfLink).toHaveAttribute('href', 'https://arxiv.org/pdf/1601.01507')
    expect(pdfLink).toHaveAttribute('target', '_blank')
    expect(pdfLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('hides both actions when arxiv_id is unavailable', () => {
    renderWithProviders(<SelectedPaperSummary paper={{ ...BASE_PAPER, arxiv_id: null }} />)
    expect(screen.queryByRole('link', { name: /Open the PDF/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /on arXiv/ })).not.toBeInTheDocument()
  })

  it('existing "Back to search" internal navigation still works unaffected', () => {
    renderWithProviders(<SelectedPaperSummary paper={BASE_PAPER} />)
    expect(screen.getByRole('link', { name: /Back to search/ })).toHaveAttribute('href', '/search')
  })
})
