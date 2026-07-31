import { describe, expect, it } from 'vitest'

import { ClusterMembershipBadge } from '@/components/clusters/ClusterMembershipBadge'
import { ConfidenceBadge } from '@/components/clusters/ConfidenceBadge'
import { MembershipProbabilityBadge } from '@/components/clusters/MembershipProbabilityBadge'
import { SimilarityBadge } from '@/components/papers/SimilarityBadge'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

// renderWithProviders (not plain render): every badge here wraps a Radix
// Tooltip, which requires a TooltipProvider ancestor to render at all.

describe('score-badge semantic distinctness', () => {
  it('ConfidenceBadge always says "Label confidence", never generic "confidence"', () => {
    renderWithProviders(<ConfidenceBadge value={0.82} />)
    expect(screen.getByText('Label confidence 82%')).toBeInTheDocument()
  })

  it('MembershipProbabilityBadge says "Avg. membership", not "confidence"', () => {
    renderWithProviders(<MembershipProbabilityBadge value={0.89} />)
    expect(screen.getByText('Avg. membership 89%')).toBeInTheDocument()
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })

  it('ClusterMembershipBadge says "Cluster membership", not "confidence" or "similarity"', () => {
    renderWithProviders(<ClusterMembershipBadge value={1.0} />)
    expect(screen.getByText('Cluster membership 100%')).toBeInTheDocument()
    expect(screen.queryByText(/confidence|similarity/i)).not.toBeInTheDocument()
  })

  it('SimilarityBadge says "Semantic similarity", never "confidence" or "membership"', () => {
    renderWithProviders(<SimilarityBadge value={0.72} />)
    expect(screen.getByText('Semantic similarity 72%')).toBeInTheDocument()
    expect(screen.queryByText(/confidence|membership/i)).not.toBeInTheDocument()
  })

  it('the four score badges never collide on visible label text', () => {
    renderWithProviders(
      <>
        <ConfidenceBadge value={0.5} />
        <MembershipProbabilityBadge value={0.5} />
        <ClusterMembershipBadge value={0.5} />
        <SimilarityBadge value={0.5} />
      </>,
    )
    const labels = ['Label confidence 50%', 'Avg. membership 50%', 'Cluster membership 50%', 'Semantic similarity 50%']
    for (const label of labels) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    expect(new Set(labels).size).toBe(4)
  })
})
