import { FileText } from 'lucide-react'
import { describe, expect, it } from 'vitest'

import { StatCard } from '@/components/common/StatCard'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

describe('StatCard', () => {
  it('renders as a plain (non-interactive) card when no href is given', () => {
    renderWithProviders(<StatCard label="Total Papers" value={169} icon={FileText} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('169')).toBeInTheDocument()
  })

  it('renders as an accessible, focusable link when href is a route', () => {
    renderWithProviders(<StatCard label="Total Papers" value={169} icon={FileText} href="/search" />)
    const link = screen.getByRole('link', { name: /Total Papers: 169/ })
    expect(link).toHaveAttribute('href', '/search')
  })

  it('renders a same-page anchor (not a router Link) for a hash href', () => {
    renderWithProviders(<StatCard label="Categories" value={12} href="#corpus-coverage" />)
    const link = screen.getByRole('link', { name: /Categories: 12/ })
    expect(link).toHaveAttribute('href', '#corpus-coverage')
    expect(link.tagName).toBe('A')
  })
})
