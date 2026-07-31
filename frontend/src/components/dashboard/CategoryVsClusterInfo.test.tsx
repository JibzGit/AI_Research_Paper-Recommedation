import { describe, expect, it } from 'vitest'

import { CategoryVsClusterInfo } from '@/components/dashboard/CategoryVsClusterInfo'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

describe('CategoryVsClusterInfo', () => {
  it('explains categories are a source taxonomy and clusters are discovered, without implying category codes are cluster labels', () => {
    renderWithProviders(<CategoryVsClusterInfo />)
    expect(screen.getByText(/Categories vs\. clusters/)).toBeInTheDocument()
    expect(screen.getByText(/fixed taxonomy assigned by the paper.s source on arXiv/)).toBeInTheDocument()
    expect(screen.getByText(/discovered automatically from embedding and content similarity/)).toBeInTheDocument()
    expect(screen.getByText(/never a category code/)).toBeInTheDocument()
    expect(screen.getByText(/A single cluster can span multiple categories/)).toBeInTheDocument()
  })
})
