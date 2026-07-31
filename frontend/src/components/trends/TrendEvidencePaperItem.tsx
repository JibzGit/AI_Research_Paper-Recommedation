import { ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { TrendEvidencePaper } from '@/api/types'
import { arxivAbstractUrl } from '@/lib/arxiv'
import { formatPublicationDate } from '@/lib/formatters'

interface TrendEvidencePaperItemProps {
  paper: TrendEvidencePaper
}

/** Deterministically-selected evidence, never an LLM-generated
 * explanation -- this item only ever displays fields that came straight
 * from a trend_evidence_papers/papers join (title, arXiv id, publication
 * date), the same posture as ClusterPaperCard. */
export function TrendEvidencePaperItem({ paper }: TrendEvidencePaperItemProps) {
  const arxivUrl = arxivAbstractUrl(paper.arxiv_id)

  return (
    <li className="flex flex-col gap-1 rounded-xl border border-border bg-card p-3">
      <Link
        to={`/papers/${paper.paper_id}/similar`}
        className="rounded text-xs font-medium text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        {paper.title}
      </Link>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        {paper.publication_date && <span>{formatPublicationDate(paper.publication_date)}</span>}
        {paper.arxiv_id && <span>arXiv:{paper.arxiv_id}</span>}
        {arxivUrl && (
          <a
            href={arxivUrl}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`View "${paper.title}" on arXiv`}
            className="inline-flex items-center gap-1 rounded hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <ExternalLink className="size-3" aria-hidden="true" />
            arXiv
          </a>
        )}
      </div>
    </li>
  )
}
