const TITLES_BY_PREFIX: Array<{ prefix: string; title: string }> = [
  { prefix: '/clusters/noise', title: 'Unclustered Papers' },
  { prefix: '/clusters/', title: 'Cluster Detail' },
  { prefix: '/clusters', title: 'Research Clusters' },
  { prefix: '/search', title: 'Paper Search' },
  { prefix: '/settings', title: 'Settings' },
  { prefix: '/trending', title: 'Trending Papers' },
  { prefix: '/recommendations', title: 'Recommendations' },
  { prefix: '/authors', title: 'Authors' },
  { prefix: '/organizations', title: 'Organizations' },
  { prefix: '/datasets', title: 'Datasets' },
  { prefix: '/models', title: 'Models' },
  { prefix: '/digest', title: 'Daily Digest' },
  { prefix: '/saved', title: 'Saved Papers' },
]

const SIMILAR_PAPERS_PATTERN = /^\/papers\/[^/]+\/similar/

/** Ordered by specificity (most specific prefix first) so a path like
 * "/clusters/noise" doesn't get shadowed by the broader "/clusters" entry. */
export function getPageTitle(pathname: string): string {
  if (pathname === '/') return 'Dashboard'
  if (SIMILAR_PAPERS_PATTERN.test(pathname)) return 'Similar Papers'
  const match = TITLES_BY_PREFIX.find((entry) => pathname.startsWith(entry.prefix))
  return match?.title ?? 'Research Platform'
}
