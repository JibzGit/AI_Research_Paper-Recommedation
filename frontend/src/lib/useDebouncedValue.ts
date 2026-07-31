import { useEffect, useState } from 'react'

/** Delays reflecting `value` until it has stopped changing for `delayMs` --
 * used to avoid firing a search request on every keystroke. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
