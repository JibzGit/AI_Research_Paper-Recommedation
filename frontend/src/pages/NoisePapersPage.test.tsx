import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import App from '@/App'
import { server } from '@/test/server'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

describe('NoisePapersPage pagination', () => {
  it('preserves the category filter when navigating to the next page', async () => {
    // Override the default single-paper fixture with a 2-paper, 1-per-page
    // response so "Next" is actually actionable.
    server.use(
      http.get('http://127.0.0.1:8000/api/v1/clusters/noise', ({ request }) => {
        const url = new URL(request.url)
        const offset = Number(url.searchParams.get('offset') ?? 0)
        return HttpResponse.json({
          clustering_run_id: '084a1215-53be-4644-86e5-6f8a84b5422f',
          total: 2,
          limit: 1,
          offset,
          papers: [
            {
              paper_id: offset === 0 ? 'aaaaaaaa-0000-0000-0000-000000000001' : 'bbbbbbbb-0000-0000-0000-000000000002',
              arxiv_id: '1601.00001',
              title: offset === 0 ? 'First Unclustered Paper' : 'Second Unclustered Paper',
              abstract: 'An unclustered paper used for pagination testing.',
              authors: ['Test Author'],
              primary_category: 'cs.CL',
              publication_date: '2016-01-01T00:00:00Z',
              membership_probability: 0.0,
              is_noise: true,
            },
          ],
        })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/clusters/noise?category=cs.CL&limit=1&offset=0' })

    expect(await screen.findByText('First Unclustered Paper')).toBeInTheDocument()
    expect(screen.getAllByText('cs.CL').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Next page of unclustered papers' }))

    expect(await screen.findByText('Second Unclustered Paper')).toBeInTheDocument()
    // The category chip is still present after paginating -- the filter
    // was not dropped when only the offset changed.
    expect(screen.getAllByText('cs.CL').length).toBeGreaterThan(0)
  })
})
