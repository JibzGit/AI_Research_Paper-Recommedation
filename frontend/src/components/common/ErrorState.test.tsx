import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import { ErrorState } from '@/components/common/ErrorState'
import { render, screen } from '@/test/renderWithProviders'

describe('ErrorState status-code distinctness', () => {
  it.each([
    [0, 'Cannot reach the API', 'network/offline failure'],
    [400, 'Invalid request', 'business-rule violation'],
    [404, 'Not found', 'genuinely not found'],
    [422, 'Validation error', 'malformed parameters'],
    [500, 'Server error', '5xx'],
  ])('status %i renders the "%s" title (%s)', (status, expectedTitle) => {
    render(<ErrorState error={new ApiError(status, 'backend detail message')} />)
    expect(screen.getByText(expectedTitle)).toBeInTheDocument()
  })

  it('never collapses distinct statuses into the same title', () => {
    const titles = [0, 400, 404, 422, 500].map((status) => {
      const { unmount } = render(<ErrorState error={new ApiError(status, 'detail')} />)
      const title = screen.getByRole('heading').textContent
      unmount()
      return title
    })
    expect(new Set(titles).size).toBe(titles.length)
  })

  it('preserves the backend detail message for 400/404/422', () => {
    render(<ErrorState error={new ApiError(404, 'paper not found: 00000000-0000-0000-0000-000000000000')} />)
    expect(screen.getByText('paper not found: 00000000-0000-0000-0000-000000000000')).toBeInTheDocument()
  })

  it('offers a retry action that calls onRetry', async () => {
    const onRetry = vi.fn()
    render(<ErrorState error={new ApiError(500, 'detail')} onRetry={onRetry} />)
    screen.getByRole('button', { name: 'Try again' }).click()
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('a plain Error (not ApiError) gets a generic fallback, distinct from any status-coded title', () => {
    render(<ErrorState error={new Error('unexpected crash')} />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('unexpected crash')).toBeInTheDocument()
  })
})
