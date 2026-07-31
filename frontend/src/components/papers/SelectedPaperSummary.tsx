import { ArrowLeft, ExternalLink, FileText } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import type { PaperDetail } from '@/api/types'
import { CategoryBadge } from '@/components/papers/CategoryBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { arxivAbstractUrl, arxivPdfUrl } from '@/lib/arxiv'
import { formatPublicationDate } from '@/lib/formatters'

const ABSTRACT_COLLAPSED_LENGTH = 320

interface SelectedPaperSummaryProps {
  paper: PaperDetail
}

/** The prominent header card for the Similar Papers page. Never shows a
 * citation count, venue, impact score, or recommendation score -- none of
 * those exist in PaperDetail. */
export function SelectedPaperSummary({ paper }: SelectedPaperSummaryProps) {
  const [abstractExpanded, setAbstractExpanded] = useState(false)
  const headingRef = useRef<HTMLHeadingElement>(null)

  // Moves focus to the heading whenever the underlying paper actually
  // changes (direct load, or navigating from one similar-paper page to
  // another) so screen-reader users get a clear signal the page's subject
  // changed, not just its URL.
  useEffect(() => {
    headingRef.current?.focus()
  }, [paper.paper_id])

  const arxivUrl = arxivAbstractUrl(paper.arxiv_id)
  const pdfUrl = arxivPdfUrl(paper.arxiv_id)
  const isLongAbstract = paper.abstract.length > ABSTRACT_COLLAPSED_LENGTH
  const showFullAbstract = abstractExpanded || !isLongAbstract

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-panel">
      <Button asChild variant="ghost" size="sm" className="w-fit gap-1.5 text-muted-foreground">
        <Link to="/search">
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Back to search
        </Link>
      </Button>

      {/* h2, not h1: TopBar already renders the page's one document h1
       * (the route title, e.g. "Similar Papers"); every other page in this
       * app uses h2 for its main in-content heading. */}
      <h2 ref={headingRef} tabIndex={-1} className="rounded text-lg font-semibold text-foreground focus-visible:outline-none focus:ring-2 focus:ring-ring">
        {paper.title}
      </h2>

      <p className="text-sm text-muted-foreground">
        {showFullAbstract ? paper.abstract : `${paper.abstract.slice(0, ABSTRACT_COLLAPSED_LENGTH)}…`}
        {isLongAbstract && (
          <button
            type="button"
            onClick={() => setAbstractExpanded((prev) => !prev)}
            className="ml-1.5 font-medium text-accent-blue hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {abstractExpanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
        <CategoryBadge category={paper.primary_category} />
        {paper.publication_date && <span>{formatPublicationDate(paper.publication_date)}</span>}
        {paper.arxiv_id && <span>arXiv:{paper.arxiv_id}</span>}
        <span>Version {paper.current_version_number}</span>
        <EmbeddingStatusBadge available={paper.embedding_available} />
      </div>

      {paper.authors.length > 0 && <p className="text-sm text-muted-foreground">{paper.authors.join(', ')}</p>}

      <div className="flex flex-wrap items-center gap-2">
        {arxivUrl && (
          <Button asChild variant="outline" size="sm" className="w-fit gap-1.5">
            <a href={arxivUrl} target="_blank" rel="noopener noreferrer" aria-label={`View "${paper.title}" on arXiv, opens in a new tab`}>
              <ExternalLink className="size-3.5" aria-hidden="true" />
              View on arXiv
            </a>
          </Button>
        )}
        {pdfUrl && (
          <Button asChild variant="outline" size="sm" className="w-fit gap-1.5">
            <a href={pdfUrl} target="_blank" rel="noopener noreferrer" aria-label={`Open the PDF for "${paper.title}", opens in a new tab`}>
              <FileText className="size-3.5" aria-hidden="true" />
              Open PDF
            </a>
          </Button>
        )}
      </div>
    </div>
  )
}

function EmbeddingStatusBadge({ available }: { available: boolean }) {
  return (
    <Badge variant="outline" className={available ? 'border-accent-green/40 text-accent-green' : 'border-accent-error/40 text-accent-error'}>
      {available ? 'Embedding available' : 'No active embedding'}
    </Badge>
  )
}
