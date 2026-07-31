const PUBLICATION_DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
})

/** Falls back to the raw string rather than throwing/hiding the date on an
 * unparseable value -- publication_date always comes from our own backend,
 * but a formatting bug here shouldn't blank out real data. */
export function formatPublicationDate(isoDate: string): string {
  const date = new Date(isoDate)
  return Number.isNaN(date.getTime()) ? isoDate : PUBLICATION_DATE_FORMATTER.format(date)
}

const UTC_DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
})

/** For dates that are precise UTC boundaries, not "when a reader locally
 * observed something" -- trend cohort window start/end come from the
 * backend as exact UTC midnights, and formatPublicationDate's use of the
 * viewer's local timezone would shift them by a day for anyone west of
 * UTC (e.g. "2016-01-01T00:00:00Z" rendering as "Dec 31, 2015" in US
 * timezones). Explicit UTC formatting keeps the displayed date matching
 * the backend's own definition of the boundary. */
export function formatUtcDate(isoDate: string): string {
  const date = new Date(isoDate)
  return Number.isNaN(date.getTime()) ? isoDate : UTC_DATE_FORMATTER.format(date)
}

const MAX_VISIBLE_AUTHORS = 4

/** Shared by PaperSearchResultCard and ClusterPaperCard -- both list full
 * author names, truncated identically past 4. */
export function formatAuthors(authors: string[]): string {
  if (authors.length <= MAX_VISIBLE_AUTHORS) return authors.join(', ')
  const visible = authors.slice(0, MAX_VISIBLE_AUTHORS)
  return `${visible.join(', ')} +${authors.length - MAX_VISIBLE_AUTHORS} more`
}
