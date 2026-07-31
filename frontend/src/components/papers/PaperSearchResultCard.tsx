import { ExternalLink, FileText, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { PaperResult } from '@/api/types'
import { CategoryBadge } from '@/components/papers/CategoryBadge'
import { SimilarityBadge } from '@/components/papers/SimilarityBadge'
import { Button } from '@/components/ui/button'
import { arxivAbstractUrl, arxivPdfUrl } from '@/lib/arxiv'
import { formatAuthors, formatPublicationDate } from '@/lib/formatters'

interface PaperSearchResultCardProps {
  paper: PaperResult
  /** 'search' (default): a Paper Search result, ranked against a typed
   * query. 'similar': a Similar Papers result, ranked against another
   * paper's embedding -- changes the action label and the similarity
   * tooltip, never the underlying fields shown. */
  mode?: 'search' | 'similar'
  /** Destination for the recommendation action. Defaults to a bare
   * /papers/{id}/similar link (Paper Search's behavior); the Similar
   * Papers page passes one that carries its current filter query string
   * forward, per its "preserve filters when exploring a new paper" rule. */
  similarPapersHref?: string
}

export function PaperSearchResultCard({ paper, mode = 'search', similarPapersHref }: PaperSearchResultCardProps) {
  const arxivUrl = arxivAbstractUrl(paper.arxiv_id)
  const pdfUrl = arxivPdfUrl(paper.arxiv_id)
  const actionLabel = mode === 'search' ? 'View Similar Papers' : 'Explore Similar Papers'
  const actionHref = similarPapersHref ?? `/papers/${paper.paper_id}/similar`

  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">{paper.title}</h3>
        <SimilarityBadge value={paper.similarity_score} context={mode === 'search' ? 'query' : 'paper'} />
      </div>

      <p className="line-clamp-3 text-xs text-muted-foreground">{paper.abstract}</p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        <CategoryBadge category={paper.primary_category} />
        {paper.publication_date && <span>{formatPublicationDate(paper.publication_date)}</span>}
        {paper.arxiv_id && <span>arXiv:{paper.arxiv_id}</span>}
      </div>

      {paper.authors.length > 0 && <p className="text-xs text-muted-foreground">{formatAuthors(paper.authors)}</p>}

      <div className="mt-1 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button asChild size="sm" variant="secondary" className="gap-1.5">
          <Link to={actionHref} state={{ sourcePaper: paper }}>
            <Sparkles className="size-3.5" aria-hidden="true" />
            {actionLabel}
          </Link>
        </Button>
        {arxivUrl && (
          <Button asChild size="sm" variant="ghost" className="gap-1.5 text-muted-foreground">
            <a href={arxivUrl} target="_blank" rel="noopener noreferrer" aria-label={`View "${paper.title}" on arXiv, opens in a new tab`}>
              <ExternalLink className="size-3.5" aria-hidden="true" />
              View on arXiv
            </a>
          </Button>
        )}
        {pdfUrl && (
          <Button asChild size="sm" variant="ghost" className="gap-1.5 text-muted-foreground">
            <a href={pdfUrl} target="_blank" rel="noopener noreferrer" aria-label={`Open the PDF for "${paper.title}", opens in a new tab`}>
              <FileText className="size-3.5" aria-hidden="true" />
              Open PDF
            </a>
          </Button>
        )}
      </div>
    </article>
  )
}
