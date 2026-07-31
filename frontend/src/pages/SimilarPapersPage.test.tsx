import { describe, expect, it } from 'vitest'

import App from '@/App'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

const PAPER_ID = '29085b7c-11d3-4dd5-aab0-e828fd5e777e'

describe('SimilarPapersPage', () => {
  it('renders full paper details from GET /api/v1/papers/{id} with no navigation state at all', async () => {
    // MemoryRouter's initialEntries as a plain string path carries no
    // location.state -- this is exactly the "opened in a new tab / shared
    // link" scenario the page must not depend on navigation state for.
    renderWithProviders(<App />, { route: `/papers/${PAPER_ID}/similar` })

    expect(await screen.findByRole('heading', { name: /Fast Kronecker product kernel methods/ })).toBeInTheDocument()
    // Fields that only exist on the full PaperDetail response (not on the
    // lighter PaperResult nav-state shape) prove the real fetch happened.
    expect(await screen.findByText('Embedding available')).toBeInTheDocument()
    expect(screen.getByText(/Version 1/)).toBeInTheDocument()
  })
})
