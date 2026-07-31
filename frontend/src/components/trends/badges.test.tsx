import { describe, expect, it } from 'vitest'

import type { TrendClassification, TrendDataQuality } from '@/api/types'
import { DataQualityBadge } from '@/components/trends/DataQualityBadge'
import { TrendClassificationBadge } from '@/components/trends/TrendClassificationBadge'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

// renderWithProviders (not plain render): both badges wrap a Radix
// Tooltip, which requires a TooltipProvider ancestor to render at all.

const ALL_CLASSIFICATIONS: TrendClassification[] = [
  'Emerging',
  'Accelerating',
  'Consistently Active',
  'Stable',
  'Cooling',
  'Insufficient Data',
]
const ALL_QUALITIES: TrendDataQuality[] = ['HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT']

describe('TrendClassificationBadge', () => {
  it.each(ALL_CLASSIFICATIONS)('renders the exact classification text for %s', (classification) => {
    renderWithProviders(<TrendClassificationBadge classification={classification} />)
    expect(screen.getByText(classification)).toBeInTheDocument()
  })

  it('all six classifications produce mutually distinct visible labels', () => {
    renderWithProviders(
      <>
        {ALL_CLASSIFICATIONS.map((classification) => (
          <TrendClassificationBadge key={classification} classification={classification} />
        ))}
      </>,
    )
    for (const classification of ALL_CLASSIFICATIONS) {
      expect(screen.getByText(classification)).toBeInTheDocument()
    }
    expect(new Set(ALL_CLASSIFICATIONS).size).toBe(6)
  })
})

describe('DataQualityBadge', () => {
  it.each(ALL_QUALITIES)('renders a "Data quality: ..." label for %s', (level) => {
    renderWithProviders(<DataQualityBadge level={level} />)
    expect(screen.getByText(`Data quality: ${level.charAt(0) + level.slice(1).toLowerCase()}`)).toBeInTheDocument()
  })

  it('never uses the word "confidence" (distinct concept from label confidence)', () => {
    renderWithProviders(<DataQualityBadge level="LOW" />)
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })
})
