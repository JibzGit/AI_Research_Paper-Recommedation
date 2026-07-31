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

const MAX_VISIBLE_AUTHORS = 4

/** Shared by PaperSearchResultCard and ClusterPaperCard -- both list full
 * author names, truncated identically past 4. */
export function formatAuthors(authors: string[]): string {
  if (authors.length <= MAX_VISIBLE_AUTHORS) return authors.join(', ')
  const visible = authors.slice(0, MAX_VISIBLE_AUTHORS)
  return `${visible.join(', ')} +${authors.length - MAX_VISIBLE_AUTHORS} more`
}
