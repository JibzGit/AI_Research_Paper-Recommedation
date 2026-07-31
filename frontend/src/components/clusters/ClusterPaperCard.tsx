import { ExternalLink, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { ClusterPaper } from '@/api/types'
import { ClusterMembershipBadge } from '@/components/clusters/ClusterMembershipBadge'
import { UnclusteredBadge } from '@/components/clusters/UnclusteredBadge'
import { CategoryBadge } from '@/components/papers/CategoryBadge'
import { Button } from '@/components/ui/button'
import { arxivAbstractUrl } from '@/lib/arxiv'
import { formatAuthors, formatPublicationDate } from '@/lib/formatters'

interface ClusterPaperCardProps {
  paper: ClusterPaper
  /** 'cluster' (default, unchanged Cluster Detail behavior): shows
   * ClusterMembershipBadge, a real per-paper fit score. 'noise': shows
   * UnclusteredBadge instead -- membership_probability is uniformly 0.0
   * for noise papers (backend metadata, not a fit score), so it's never
   * displayed as "Cluster membership 0%". */
  mode?: 'cluster' | 'noise'
}

/** Same layout as PaperSearchResultCard, built separately rather than
 * forced into it: ClusterPaper and PaperResult are different generated
 * types (membership_probability + is_noise vs. similarity_score), so
 * reuse happens at the shared-primitive level (CategoryBadge, arXiv/author/
 * date formatting) rather than the card itself. is_noise itself is never
 * rendered as a raw boolean either way -- callers pick the correct mode
 * from which endpoint they called (/clusters/{id}/papers is always
 * non-noise, /clusters/noise is always noise). */
export function ClusterPaperCard({ paper, mode = 'cluster' }: ClusterPaperCardProps) {
  const arxivUrl = arxivAbstractUrl(paper.arxiv_id)

  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground">{paper.title}</h4>
        {mode === 'cluster' ? <ClusterMembershipBadge value={paper.membership_probability} /> : <UnclusteredBadge />}
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
          <Link to={`/papers/${paper.paper_id}/similar`} state={{ sourcePaper: paper }}>
            <Sparkles className="size-3.5" aria-hidden="true" />
            Explore Similar Papers
          </Link>
        </Button>
        {arxivUrl && (
          <Button asChild size="sm" variant="ghost" className="gap-1.5 text-muted-foreground">
            <a href={arxivUrl} target="_blank" rel="noopener noreferrer" aria-label={`View "${paper.title}" on arXiv`}>
              <ExternalLink className="size-3.5" aria-hidden="true" />
              arXiv
            </a>
          </Button>
        )}
      </div>
    </article>
  )
}
