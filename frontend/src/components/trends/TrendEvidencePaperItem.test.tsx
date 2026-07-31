import { describe, expect, it } from 'vitest'

import type { TrendEvidencePaper } from '@/api/types'
import { TrendEvidencePaperItem } from '@/components/trends/TrendEvidencePaperItem'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

const BASE_PAPER: TrendEvidencePaper = {
  paper_id: 'f1eace7e-84fe-41c4-8f6f-fd4df69d4ccd',
  title: 'Evidence Attribution in Visual Document Understanding',
  arxiv_id: '2607.24651',
  publication_date: '2026-07-27T16:49:36Z',
  role: 'recent_period',
}

describe('TrendEvidencePaperItem', () => {
  it('trend evidence papers include working PDF access', () => {
    renderWithProviders(<TrendEvidencePaperItem paper={BASE_PAPER} />)
    const pdfLink = screen.getByRole('link', { name: /Open the PDF for ".*", opens in a new tab/ })
    expect(pdfLink).toHaveAttribute('href', 'https://arxiv.org/pdf/2607.24651')
    expect(pdfLink).toHaveAttribute('target', '_blank')
    expect(pdfLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('also renders a working "View on arXiv" link', () => {
    renderWithProviders(<TrendEvidencePaperItem paper={BASE_PAPER} />)
    expect(screen.getByRole('link', { name: /View ".*" on arXiv, opens in a new tab/ })).toHaveAttribute(
      'href',
      'https://arxiv.org/abs/2607.24651',
    )
  })

  it('hides both external actions when arxiv_id is unavailable', () => {
    renderWithProviders(<TrendEvidencePaperItem paper={{ ...BASE_PAPER, arxiv_id: null }} />)
    expect(screen.queryByRole('link', { name: /Open the PDF/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /on arXiv/ })).not.toBeInTheDocument()
  })

  it('the title link (existing internal navigation to Similar Papers) is unaffected', () => {
    renderWithProviders(<TrendEvidencePaperItem paper={BASE_PAPER} />)
    const titleLink = screen.getByRole('link', { name: BASE_PAPER.title })
    expect(titleLink).toHaveAttribute('href', `/papers/${BASE_PAPER.paper_id}/similar`)
    expect(titleLink).not.toHaveAttribute('target')
  })
})
