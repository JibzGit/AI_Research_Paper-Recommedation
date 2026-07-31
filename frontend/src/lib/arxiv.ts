// Matches the modern arXiv identifier scheme (YYMM.NNNNN, optional version
// suffix) -- this corpus is entirely 2016+ ingested papers, which always
// use this scheme, never the pre-2007 archive/subject-class form.
const ARXIV_ID_PATTERN = /^\d{4}\.\d{4,5}(v\d+)?$/

/** Returns null (never a malformed link) unless arxivId matches the
 * expected pattern -- the arXiv link is only ever rendered when this
 * returns non-null. */
export function arxivAbstractUrl(arxivId: string | null): string | null {
  if (!arxivId || !ARXIV_ID_PATTERN.test(arxivId)) return null
  return `https://arxiv.org/abs/${arxivId}`
}
