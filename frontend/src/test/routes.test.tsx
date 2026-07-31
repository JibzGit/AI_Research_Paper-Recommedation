import { describe, expect, it } from 'vitest'

import App from '@/App'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

describe('application routing', () => {
  it.each([
    ['/', 'Dashboard'],
    ['/search', 'Paper Search'],
    ['/clusters', 'Research Clusters'],
    ['/trends', 'Research Trends'],
    ['/settings', 'Settings'],
    ['/trending', 'Trending Papers'],
  ])('renders %s', async (route, expectedHeading) => {
    renderWithProviders(<App />, { route })
    expect(await screen.findByRole('heading', { name: expectedHeading })).toBeInTheDocument()
  })

  it('renders cluster detail content for a numeric cluster id', async () => {
    renderWithProviders(<App />, { route: '/clusters/2' })
    expect(await screen.findByRole('heading', { name: 'Visual Recognition, Segmentation, and Localization' })).toBeInTheDocument()
  })

  it('renders trend entity detail content for a valid cluster id', async () => {
    renderWithProviders(<App />, { route: '/trends/cluster/0' })
    expect(await screen.findByRole('heading', { name: 'Medical Imaging AI and Clinical Evaluation' })).toBeInTheDocument()
  })

  it('renders similar-papers content for a valid paper id', async () => {
    renderWithProviders(<App />, { route: '/papers/29085b7c-11d3-4dd5-aab0-e828fd5e777e/similar' })
    expect(await screen.findByRole('heading', { name: /Fast Kronecker product kernel methods/ })).toBeInTheDocument()
  })

  it('renders NotFoundPage for an unknown route', async () => {
    renderWithProviders(<App />, { route: '/this-route-does-not-exist' })
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })

  it('/clusters/noise resolves to the Unclustered Papers page, not a cluster-id lookup', async () => {
    renderWithProviders(<App />, { route: '/clusters/noise' })
    expect(await screen.findByRole('heading', { name: 'Unclustered Papers' })).toBeInTheDocument()
    expect(screen.queryByText('This cluster link is invalid.')).not.toBeInTheDocument()
  })

  it.each([
    ['/clusters/abc', 'This cluster link is invalid.'],
    ['/clusters/-1', 'This cluster link is invalid.'],
    ['/papers/not-a-uuid/similar', 'This paper link is invalid.'],
    ['/trends/paper/0', 'This trend link is invalid.'],
  ])('malformed id at %s shows an invalid-link state, never a loading spinner or crash', async (route, expectedMessage) => {
    renderWithProviders(<App />, { route })
    expect(await screen.findByText(expectedMessage)).toBeInTheDocument()
  })
})
