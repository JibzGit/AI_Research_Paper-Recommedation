import { describe, expect, it } from 'vitest'

import type { PaperResult } from '@/api/types'
import { PaperSearchResultCard } from '@/components/papers/PaperSearchResultCard'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

const BASE_PAPER: PaperResult = {
  paper_id: '29085b7c-11d3-4dd5-aab0-e828fd5e777e',
  arxiv_id: '1601.01507',
  title: 'Fast Kronecker product kernel methods via generalized vec trick',
  abstract: 'Kronecker product kernel provides the standard approach.',
  authors: ['Antti Airola'],
  primary_category: 'stat.ML',
  publication_date: '2016-01-07T12:25:53Z',
  similarity_score: 0.72,
}

describe('PaperSearchResultCard', () => {
  it('renders working "View on arXiv" and "Open PDF" links with correct URLs', () => {
    renderWithProviders(<PaperSearchResultCard paper={BASE_PAPER} />)
    const arxivLink = screen.getByRole('link', { name: /View ".*" on arXiv, opens in a new tab/ })
    expect(arxivLink).toHaveAttribute('href', 'https://arxiv.org/abs/1601.01507')

    const pdfLink = screen.getByRole('link', { name: /Open the PDF for ".*", opens in a new tab/ })
    expect(pdfLink).toHaveAttribute('href', 'https://arxiv.org/pdf/1601.01507')
  })

  it('both external links open in a new tab with rel="noopener noreferrer"', () => {
    renderWithProviders(<PaperSearchResultCard paper={BASE_PAPER} />)
    for (const link of [
      screen.getByRole('link', { name: /View ".*" on arXiv/ }),
      screen.getByRole('link', { name: /Open the PDF for/ }),
    ]) {
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    }
  })

  it('hides both arXiv and PDF actions when arxiv_id is unavailable, never fabricating a link', () => {
    renderWithProviders(<PaperSearchResultCard paper={{ ...BASE_PAPER, arxiv_id: null }} />)
    expect(screen.queryByRole('link', { name: /on arXiv/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Open the PDF/ })).not.toBeInTheDocument()
  })

  it('existing internal "Find Similar Papers" navigation still works unaffected', () => {
    renderWithProviders(<PaperSearchResultCard paper={BASE_PAPER} />)
    const similarLink = screen.getByRole('link', { name: /Similar Papers/ })
    expect(similarLink).toHaveAttribute('href', `/papers/${BASE_PAPER.paper_id}/similar`)
    expect(similarLink).not.toHaveAttribute('target')
  })
})
