import { describe, expect, it } from 'vitest'

import { TrendLabelGuide } from '@/components/trends/TrendLabelGuide'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

describe('TrendLabelGuide', () => {
  it('visibly explains all six trend classifications, not hidden behind a hover-only tooltip', () => {
    renderWithProviders(<TrendLabelGuide />)
    expect(screen.getByText('How to read trend labels')).toBeInTheDocument()

    for (const classification of ['Emerging', 'Accelerating', 'Consistently Active', 'Stable', 'Cooling', 'Insufficient Data']) {
      expect(screen.getByText(classification)).toBeInTheDocument()
    }

    expect(screen.getByText(/does not prove an entire research area is newly created/)).toBeInTheDocument()
  })
})
