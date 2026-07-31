import { HttpResponse, http } from 'msw'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import App from '@/App'
import { renderWithProviders, screen, waitFor, within } from '@/test/renderWithProviders'
import { server } from '@/test/server'

const API_BASE = 'http://127.0.0.1:8000'

describe('GlobalSearchBar (dashboard top search)', () => {
  it('shows a debounced suggestions dropdown with real search results, not fabricated data', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/' })

    const input = screen.getByRole('combobox', { name: 'Search papers' })
    await user.type(input, 'graph neural networks')

    const listbox = await screen.findByRole('listbox', {}, { timeout: 2000 })
    const options = await within(listbox).findAllByRole('option')
    expect(options).toHaveLength(1)
    const [option] = options
    expect(within(option!).getByText('Fast Kronecker product kernel methods via generalized vec trick')).toBeInTheDocument()
    // Secondary metadata: authors, category, year.
    expect(within(option!).getByText(/Antti Airola/)).toBeInTheDocument()
    expect(within(option!).getByText(/stat\.ML/)).toBeInTheDocument()
    expect(within(option!).getByText(/2016/)).toBeInTheDocument()
  })

  it('debounces: rapid keystrokes trigger only one network request', async () => {
    const user = userEvent.setup()
    let requestCount = 0
    server.use(
      http.get(`${API_BASE}/api/v1/papers/search`, () => {
        requestCount += 1
        return HttpResponse.json({ query: 'x', count: 0, results: [] })
      }),
    )
    renderWithProviders(<App />, { route: '/' })

    const input = screen.getByRole('combobox', { name: 'Search papers' })
    await user.type(input, 'transformers')

    await waitFor(() => expect(screen.getByText(/No papers found/)).toBeInTheDocument(), { timeout: 2000 })
    expect(requestCount).toBe(1)
  })

  it('shows an empty state for a query with zero real results', async () => {
    const user = userEvent.setup()
    server.use(http.get(`${API_BASE}/api/v1/papers/search`, () => HttpResponse.json({ query: 'zzz', count: 0, results: [] })))
    renderWithProviders(<App />, { route: '/' })

    const input = screen.getByRole('combobox', { name: 'Search papers' })
    await user.type(input, 'zzz')

    expect(await screen.findByText('No papers found for “zzz”.', {}, { timeout: 2000 })).toBeInTheDocument()
  })

  it('shows an inline error state on a failed suggestions request', async () => {
    const user = userEvent.setup()
    server.use(http.get(`${API_BASE}/api/v1/papers/search`, () => HttpResponse.json({ detail: 'Search backend unavailable' }, { status: 500 })))
    renderWithProviders(<App />, { route: '/' })

    const input = screen.getByRole('combobox', { name: 'Search papers' })
    await user.type(input, 'anything')

    expect(await screen.findByText('Search backend unavailable', {}, { timeout: 2000 })).toBeInTheDocument()
  })

  it('supports keyboard navigation (ArrowDown selects, Enter navigates to the paper)', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/' })

    const input = screen.getByRole('combobox', { name: 'Search papers' })
    await user.type(input, 'graph neural networks')

    const listbox = await screen.findByRole('listbox', {}, { timeout: 2000 })
    const [option] = await within(listbox).findAllByRole('option')

    await user.keyboard('{ArrowDown}')
    expect(option).toHaveAttribute('aria-selected', 'true')

    await user.keyboard('{Enter}')

    expect(await screen.findByRole('heading', { level: 1, name: 'Similar Papers' })).toBeInTheDocument()
    expect(screen.getByText('Fast Kronecker product kernel methods via generalized vec trick')).toBeInTheDocument()
  })

  it('Enter with no suggestion highlighted opens the full Search page with the typed query', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/' })

    const input = screen.getByRole('combobox', { name: 'Search papers' })
    await user.type(input, 'graph neural networks{Enter}')

    const searchInput = await screen.findByLabelText('Search query')
    expect(searchInput).toHaveValue('graph neural networks')
  })

  it('clicking a suggestion navigates to it directly', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/' })

    const input = screen.getByRole('combobox', { name: 'Search papers' })
    await user.type(input, 'graph neural networks')

    const listbox = await screen.findByRole('listbox', {}, { timeout: 2000 })
    const suggestionText = await within(listbox).findByText(
      'Fast Kronecker product kernel methods via generalized vec trick',
      {},
      { timeout: 2000 },
    )
    await user.click(suggestionText)

    expect(await screen.findByRole('heading', { level: 1, name: 'Similar Papers' })).toBeInTheDocument()
  })

  it('each suggestion has working Open PDF / View on arXiv actions using the real arxiv_id', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/' })

    const input = screen.getByRole('combobox', { name: 'Search papers' })
    await user.type(input, 'graph neural networks')

    const listbox = await screen.findByRole('listbox', {}, { timeout: 2000 })
    const pdfLink = await within(listbox).findByRole('link', { name: /Open the PDF for/ }, { timeout: 2000 })
    expect(pdfLink).toHaveAttribute('href', 'https://arxiv.org/pdf/1601.01507')
    const arxivLink = within(listbox).getByRole('link', { name: /on arXiv, opens in a new tab/ })
    expect(arxivLink).toHaveAttribute('href', 'https://arxiv.org/abs/1601.01507')
  })
})
