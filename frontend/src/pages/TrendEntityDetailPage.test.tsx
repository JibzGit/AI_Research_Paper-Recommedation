import { describe, expect, it } from 'vitest'

import App from '@/App'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

const BANNED_PHRASES = ['Trending Now', 'Latest AI Trends', 'Current Momentum', 'Year-over-Year', 'continuous historical trend']

describe('TrendEntityDetailPage', () => {
  it('Cluster 0 shows Emerging with a null growth rate rendered as "New", not 0% or a crash', async () => {
    renderWithProviders(<App />, { route: '/trends/cluster/0' })
    expect(await screen.findByRole('heading', { name: 'Medical Imaging AI and Clinical Evaluation' })).toBeInTheDocument()
    expect(screen.getAllByText('Emerging').length).toBeGreaterThan(0)
    expect(screen.getByText('New')).toBeInTheDocument()
  })

  it('Cluster 4 shows Cooling', async () => {
    renderWithProviders(<App />, { route: '/trends/cluster/4' })
    expect(await screen.findByRole('heading', { name: 'Online Media Analysis and Event Retrieval' })).toBeInTheDocument()
    expect(screen.getAllByText('Cooling').length).toBeGreaterThan(0)
  })

  it('Cluster 5 shows Stable', async () => {
    renderWithProviders(<App />, { route: '/trends/cluster/5' })
    expect(await screen.findByRole('heading', { name: 'Model Distillation and Policy Learning' })).toBeInTheDocument()
    expect(screen.getAllByText('Stable').length).toBeGreaterThan(0)
  })

  it('splits evidence papers into Recent cohort evidence and Comparison cohort evidence, correctly attributed', async () => {
    renderWithProviders(<App />, { route: '/trends/cluster/5' })
    await screen.findByRole('heading', { name: 'Model Distillation and Policy Learning' })
    expect(screen.getByRole('heading', { name: 'Recent cohort evidence' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Comparison cohort evidence' })).toBeInTheDocument()
    expect(screen.queryByText('No evidence papers for this cohort.')).not.toBeInTheDocument()
  })

  it('Cluster 0 has no comparison-period evidence (0 papers in that cohort)', async () => {
    renderWithProviders(<App />, { route: '/trends/cluster/0' })
    await screen.findByRole('heading', { name: 'Medical Imaging AI and Clinical Evaluation' })
    expect(screen.getByText('No evidence papers for this cohort.')).toBeInTheDocument()
  })

  it('never renders current-trend or continuous-trend wording', async () => {
    renderWithProviders(<App />, { route: '/trends/cluster/5' })
    await screen.findByRole('heading', { name: 'Model Distillation and Policy Learning' })
    const bodyText = document.body.textContent ?? ''
    for (const banned of BANNED_PHRASES) {
      expect(bodyText).not.toContain(banned)
    }
  })

  it('shows the Historical Cohort Comparison warning', async () => {
    renderWithProviders(<App />, { route: '/trends/cluster/5' })
    await screen.findByRole('heading', { name: 'Model Distillation and Policy Learning' })
    expect(screen.getByText(/compares the corpus's two ingestion cohorts/)).toBeInTheDocument()
  })
})
