import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/button'

interface PaperPaginationProps {
  total: number
  limit: number
  offset: number
  onPageChange: (newOffset: number) => void
  /** Plural noun for the "Showing X-Y of Z {itemLabel}" text and the
   * Previous/Next accessible names, e.g. "papers", "cluster papers",
   * "unclustered papers". */
  itemLabel?: string
}

/** Generic over any paginated papers response (cluster papers, noise
 * papers, ...) -- total/limit/offset always come from the real response,
 * pages are never calculated from an invented total. */
export function PaperPagination({ total, limit, offset, onPageChange, itemLabel = 'papers' }: PaperPaginationProps) {
  if (total === 0) return null

  const rangeStart = offset + 1
  const rangeEnd = Math.min(offset + limit, total)
  const canGoPrevious = offset > 0
  const canGoNext = offset + limit < total

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
      <p className="text-xs text-muted-foreground">
        Showing <span className="text-foreground tabular-nums">{rangeStart}</span>–
        <span className="text-foreground tabular-nums">{rangeEnd}</span> of{' '}
        <span className="text-foreground tabular-nums">{total}</span> {itemLabel}
      </p>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canGoPrevious}
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          aria-label={`Previous page of ${itemLabel}`}
          className="gap-1"
        >
          <ChevronLeft className="size-3.5" aria-hidden="true" />
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canGoNext}
          onClick={() => onPageChange(offset + limit)}
          aria-label={`Next page of ${itemLabel}`}
          className="gap-1"
        >
          Next
          <ChevronRight className="size-3.5" aria-hidden="true" />
        </Button>
      </div>
    </div>
  )
}
