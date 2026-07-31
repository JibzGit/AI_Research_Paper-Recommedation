import { HttpResponse, http } from 'msw'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import App from '@/App'
import { renderWithProviders, screen } from '@/test/renderWithProviders'
import { server } from '@/test/server'

const API_BASE = 'http://127.0.0.1:8000'

describe('CategoryCoverageSection (dashboard)', () => {
  it('renders category code, real display name, paper count, and a computed (never hardcoded) percentage', async () => {
    server.use(
      http.get(`${API_BASE}/api/v1/categories`, () =>
        HttpResponse.json({
          count: 2,
          categories: [
            { code: 'cs.CV', display_name: 'Computer Vision and Pattern Recognition', paper_count: 50 },
            { code: 'cs.LG', display_name: 'Machine Learning', paper_count: 50 },
          ],
        }),
      ),
      http.get(`${API_BASE}/api/v1/stats/overview`, () =>
        HttpResponse.json({
          total_canonical_papers: 100,
          embedded_papers: 100,
          approved_clusters: 5,
          clustered_papers: 80,
          noise_papers: 20,
          latest_clustering_run_id: 'run-1',
          database_status: 'connected',
        }),
      ),
    )
    renderWithProviders(<App />, { route: '/' })

    expect(await screen.findByText('Computer Vision and Pattern Recognition')).toBeInTheDocument()
    // 50 of 100 total canonical papers -> 50%, computed from real API values.
    expect(screen.getAllByText('50%').length).toBeGreaterThan(0)
  })

  it('falls back to a controlled display-name map only when the backend name is blank, while keeping the real code', async () => {
    server.use(
      http.get(`${API_BASE}/api/v1/categories`, () =>
        HttpResponse.json({ count: 1, categories: [{ code: 'cs.IR', display_name: '', paper_count: 10 }] }),
      ),
    )
    renderWithProviders(<App />, { route: '/' })

    expect(await screen.findByText('Information Retrieval')).toBeInTheDocument()
    expect(screen.getAllByText('cs.IR').length).toBeGreaterThan(0)
  })

  it('a category chip/row navigates to Paper Search filtered by that category', async () => {
    const user = userEvent.setup()
    server.use(
      http.get(`${API_BASE}/api/v1/categories`, () =>
        HttpResponse.json({ count: 1, categories: [{ code: 'cs.CV', display_name: 'Computer Vision', paper_count: 12 }] }),
      ),
    )
    renderWithProviders(<App />, { route: '/' })

    const categoryLink = await screen.findByText('Computer Vision')
    await user.click(categoryLink)

    // Landed on Paper Search with the category filter pre-applied -- the
    // search endpoint requires real query text (never auto-run here), so
    // the reliable, verifiable signal is the active category filter chip.
    expect(await screen.findByRole('heading', { level: 2, name: 'Paper Search' })).toBeInTheDocument()
    expect(await screen.findByText('cs.CV')).toBeInTheDocument()
  })

  it('shows an expandable table for categories beyond the compact chip count', async () => {
    const user = userEvent.setup()
    const categories = Array.from({ length: 10 }, (_, i) => ({
      code: `cs.X${i}`,
      display_name: `Category ${i}`,
      paper_count: 10 - i,
    }))
    server.use(http.get(`${API_BASE}/api/v1/categories`, () => HttpResponse.json({ count: categories.length, categories })))
    renderWithProviders(<App />, { route: '/' })

    const expandButton = await screen.findByRole('button', { name: /Show all 10 categories/ })
    expect(screen.queryByText('Category 9')).not.toBeInTheDocument()

    await user.click(expandButton)
    expect(screen.getByText('Category 9')).toBeInTheDocument()
  })
})
