import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import App from '@/App'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

describe('SearchPage', () => {
  it('does not submit a blank (whitespace-only) query', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/search' })

    const input = await screen.findByLabelText('Search query')
    await user.type(input, '   ')

    expect(screen.getByRole('button', { name: 'Search' })).toBeDisabled()
    // Still showing the initial empty state -- no committed search happened.
    expect(screen.getByText('Search the research corpus')).toBeInTheDocument()
  })

  it('restores query, top_k, and category from the URL on load', async () => {
    renderWithProviders(<App />, { route: '/search?query=graph+neural+networks&top_k=20&category=cs.LG' })

    const input = await screen.findByLabelText('Search query')
    expect(input).toHaveValue('graph neural networks')

    // Results (from the MSW-mocked response) render for the restored query.
    expect(await screen.findByText(/papers? matching/)).toBeInTheDocument()
    expect(screen.getByText('Fast Kronecker product kernel methods via generalized vec trick')).toBeInTheDocument()

    // The category filter chip reflects the URL-restored value.
    expect(screen.getByText('cs.LG')).toBeInTheDocument()
  })
})
