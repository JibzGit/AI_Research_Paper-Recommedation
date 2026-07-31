import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import App from '@/App'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

describe('DashboardPage', () => {
  it('renders sections in the specified hierarchy: stats, corpus coverage, cluster distribution, trends, trend guide, representative papers', async () => {
    renderWithProviders(<App />, { route: '/' })
    await screen.findByText('Total Papers')

    // Scoped to <main> -- the sidebar nav also contains "Research Trends"/
    // "Research Clusters" links, which would otherwise shadow the page's
    // own section headings when searching the whole document.
    const main = document.querySelector('main')
    expect(main).not.toBeNull()
    const text = main!.textContent ?? ''
    const indexOf = (needle: string) => {
      const index = text.indexOf(needle)
      expect(index, `expected to find "${needle}" in the rendered dashboard`).toBeGreaterThanOrEqual(0)
      return index
    }

    const order: number[] = [
      'Total Papers', // clickable statistics
      'Corpus coverage by category', // corpus coverage
      'Cluster distribution', // cluster distribution + legend/table
      'Leading research clusters',
      'Research Trends', // research trend summary
      'How to read trend labels', // trend-label guide
      'Representative Papers from Leading Clusters',
    ].map(indexOf)

    for (let i = 1; i < order.length; i++) {
      expect(order[i]).toBeGreaterThan(order[i - 1]!)
    }
  })

  it('the Total Papers stat card is a real link into Paper Search', async () => {
    renderWithProviders(<App />, { route: '/' })
    const link = await screen.findByRole('link', { name: /Total Papers: 169/ })
    expect(link).toHaveAttribute('href', '/search')
  })

  it('the Approved Clusters and Unclustered Papers stats link to Research Clusters / Unclustered Papers', async () => {
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByRole('link', { name: /Approved Clusters: 10/ })).toHaveAttribute('href', '/clusters')
    expect(await screen.findByRole('link', { name: /Unclustered Papers: 21/ })).toHaveAttribute('href', '/clusters/noise')
  })

  it('a leading cluster card links to its real Cluster Detail page', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/' })

    // The same cluster name legitimately appears twice -- once as the
    // ClusterCard heading (h4), once as a full name in the legend table --
    // so this targets the card specifically, not the table row.
    const clusterHeading = await screen.findByRole('heading', { level: 4, name: 'Visual Recognition, Segmentation, and Localization' })
    await user.click(clusterHeading.closest('a')!)

    expect(await screen.findByRole('heading', { level: 1, name: 'Cluster Detail' })).toBeInTheDocument()
  })

  it('the cluster legend table row links to the same Cluster Detail page as the chart', async () => {
    renderWithProviders(<App />, { route: '/' })
    const viewLink = await screen.findByRole('link', { name: 'View' })
    expect(viewLink).toHaveAttribute('href', '/clusters/2')
  })

  it('clicking the Emerging trend stat navigates to Research Trends pre-filtered by classification', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/' })

    const emergingLink = await screen.findByRole('link', { name: /Emerging/ })
    await user.click(emergingLink)

    expect(await screen.findByRole('heading', { level: 1, name: 'Research Trends' })).toBeInTheDocument()
  })

  it('shows the real Historical Cohort Comparison warning with backend-provided cohort dates, not invented ones', async () => {
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findAllByText('Historical Cohort Comparison')).not.toHaveLength(0)
    expect((await screen.findAllByText(/Comparison cohort:/)).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Recent cohort:/).length).toBeGreaterThan(0)
    // Real backend-provided dates (2016 comparison cohort, 2026 recent cohort), not placeholders.
    expect(screen.getByText(/Jan 1, 2016/)).toBeInTheDocument()
  })

  it('every clickable stat card exposes a visible focus state via the shared focus-visible ring classes', async () => {
    renderWithProviders(<App />, { route: '/' })
    const link = await screen.findByRole('link', { name: /Total Papers: 169/ })
    expect(link.className).toMatch(/focus-visible:ring-2/)
  })

  it('the categories-vs-clusters explanation and trend-label guide are both present on the dashboard', async () => {
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByText(/Categories vs\. clusters/)).toBeInTheDocument()
    expect(await screen.findByText('How to read trend labels')).toBeInTheDocument()
  })

  it('the global search bar in the top bar is present and usable from the dashboard', async () => {
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByRole('combobox', { name: 'Search papers' })).toBeInTheDocument()
  })
})
