import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { server } from '@/test/server'

// jsdom doesn't implement layout/scrolling APIs -- real browsers support
// scrollIntoView fine (used for post-pagination focus management), this is
// purely a jsdom gap, not app behavior under test.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// Any request without a matching handler fails loudly instead of silently
// hitting the real network -- keeps tests hermetic and catches missing
// fixtures immediately rather than as a mysterious timeout.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  cleanup()
})
afterAll(() => server.close())
