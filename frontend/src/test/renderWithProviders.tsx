import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { TooltipProvider } from '@/components/ui/tooltip'

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      // No retries/caching noise in tests -- a failing request should fail
      // once and be immediately observable, not retried into a timeout.
      queries: { retry: false, staleTime: 0, gcTime: 0 },
    },
  })
}

interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  route?: string
}

/** Wraps a component with the same providers main.tsx sets up
 * (QueryClientProvider, BrowserRouter-equivalent, TooltipProvider), using
 * MemoryRouter so tests can start at any URL. Rendering the real <App />
 * through this (rather than mounting individual pages) means useParams()/
 * useSearchParams() resolve exactly as they do at runtime. */
export function renderWithProviders(ui: ReactElement, { route = '/', ...options }: RenderWithProvidersOptions = {}) {
  const queryClient = createTestQueryClient()

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <TooltipProvider>{children}</TooltipProvider>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }

  return render(ui, { wrapper: Wrapper, ...options })
}

export * from '@testing-library/react'
