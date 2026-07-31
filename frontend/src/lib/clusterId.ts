// Digits only -- no sign, no decimal point, no whitespace. Rejects both
// malformed values ("abc") and negative integers, which are syntactically
// valid JSON-schema integers but never real cluster IDs in this corpus.
const CLUSTER_ID_PATTERN = /^\d+$/

/** Returns null for anything that isn't a genuine non-negative integer --
 * callers never send such a value to the backend. */
export function parseClusterIdParam(raw: string | undefined): number | null {
  if (raw === undefined || !CLUSTER_ID_PATTERN.test(raw)) return null
  const parsed = Number.parseInt(raw, 10)
  return Number.isSafeInteger(parsed) ? parsed : null
}
