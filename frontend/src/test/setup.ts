import '@testing-library/jest-dom/vitest'
import { configure } from '@testing-library/dom'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { server } from '@/test/server'

// jsdom doesn't implement layout/scrolling APIs -- real browsers support
// scrollIntoView fine (used for post-pagination focus management), this is
// purely a jsdom gap, not app behavior under test.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// Several pages (Dashboard, Trends) are React.lazy()-loaded and pull in a
// heavy chart chunk (recharts) on first render -- under vitest's default
// parallel-file execution, real (non-mocked) CPU contention across many
// concurrent jsdom environments can occasionally push that first dynamic
// import + render past @testing-library's 1000ms default asyncUtilTimeout,
// even though nothing in the app or the query itself is actually slow or
// broken. Raising this globally (not per-test) gives every findBy*/waitFor
// enough headroom to observe genuinely-eventually-true state under that
// contention without masking a real regression -- a truly broken query
// still fails, just after 5s instead of 1s.
configure({ asyncUtilTimeout: 5000 })

// Any request without a matching handler fails loudly instead of silently
// hitting the real network -- keeps tests hermetic and catches missing
// fixtures immediately rather than as a mysterious timeout.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  cleanup()
})
afterAll(() => server.close())
