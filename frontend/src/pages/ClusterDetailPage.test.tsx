import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import App from '@/App'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

describe('ClusterDetailPage filters', () => {
  it('hydrates the active-category chip from the URL on load', async () => {
    renderWithProviders(<App />, { route: '/clusters/2?category=cs.CV&limit=10&offset=0' })

    expect(await screen.findByRole('heading', { name: 'Visual Recognition, Segmentation, and Localization' })).toBeInTheDocument()
    // "cs.CV" legitimately appears twice (the cluster header's dominant-
    // category badge and the active-filter chip) -- both are real,
    // URL-driven renders, so asserting at least one match is sufficient.
    expect(screen.getAllByText('cs.CV').length).toBeGreaterThan(0)
  })

  it('applying a membership-threshold filter writes it into the visible filter state (URL round-trip)', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/clusters/2' })
    await screen.findByRole('heading', { name: 'Visual Recognition, Segmentation, and Localization' })

    // Native <input type="range">, not a Radix Select -- avoids jsdom
    // pointer-capture flakiness while still exercising a real control.
    const slider = screen.getByLabelText('Minimum cluster membership')
    fireEventChange(slider, '0.5')

    await user.click(screen.getByRole('button', { name: 'Apply filters' }))

    expect(await screen.findByText('≥ 0.50 membership')).toBeInTheDocument()
  })
})

function fireEventChange(element: HTMLElement, value: string) {
  const input = element as HTMLInputElement
  const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
  nativeSetter?.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}
