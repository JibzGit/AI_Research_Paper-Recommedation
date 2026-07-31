import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import App from '@/App'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

const BANNED_PHRASES = ['Trending Now', 'Latest AI Trends', 'Current Momentum', 'Year-over-Year', 'continuous historical trend']

describe('TrendsPage', () => {
  it('shows the Historical Cohort Comparison warning with cohort dates', async () => {
    renderWithProviders(<App />, { route: '/trends' })
    await screen.findByText('Comparison cohort:')
    // "Historical Cohort Comparison" legitimately appears twice (the mode
    // label and again inside the message sentence) -- getAllByText, not
    // getByText, which throws on multiple matches.
    expect(screen.getAllByText(/Historical Cohort Comparison/).length).toBeGreaterThan(0)
    expect(screen.getByText('Recent cohort:')).toBeInTheDocument()
    expect(screen.getByText(/Jan 1, 2016.*Jan 11, 2016/)).toBeInTheDocument()
  })

  it('never renders current-trend or continuous-trend wording', async () => {
    renderWithProviders(<App />, { route: '/trends' })
    await screen.findByText('Comparison cohort:')
    const bodyText = document.body.textContent ?? ''
    for (const banned of BANNED_PHRASES) {
      expect(bodyText).not.toContain(banned)
    }
  })

  it('shows Emerging, Stable, and Cooling sections from the overview', async () => {
    renderWithProviders(<App />, { route: '/trends' })
    expect(await screen.findByRole('heading', { name: 'Emerging' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Stable' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Cooling' })).toBeInTheDocument()
    expect(screen.getAllByText('Medical Imaging AI and Clinical Evaluation').length).toBeGreaterThan(0)
  })

  it('restores classification and data-quality filters from the URL', async () => {
    renderWithProviders(<App />, { route: '/trends?type=cluster&classification=Cooling&data_quality=LOW' })
    await screen.findByText('Comparison cohort:')
    expect(screen.getAllByText('Cooling').length).toBeGreaterThan(0)
    expect(screen.getByText('Quality: LOW')).toBeInTheDocument()
  })

  it('switching to the Categories tab shows category results', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/trends' })
    await screen.findByText('Comparison cohort:')
    await user.click(screen.getByRole('tab', { name: 'Categories' }))
    expect((await screen.findAllByText('cs.CV')).length).toBeGreaterThan(0)
  })

  it('freshness status badge is visible', async () => {
    renderWithProviders(<App />, { route: '/trends' })
    expect(await screen.findByText('Freshness: Partially current')).toBeInTheDocument()
  })
})
