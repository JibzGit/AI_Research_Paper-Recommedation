import { ExternalLink, FileText, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { RepresentativePaper } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'
import { Button } from '@/components/ui/button'
import { arxivAbstractUrl, arxivPdfUrl } from '@/lib/arxiv'

interface ClusterRepresentativePapersProps {
  papers: RepresentativePaper[]
}

/** representative_papers is already loaded as part of ClusterDetail --
 * this never issues an additional request per paper. */
export function ClusterRepresentativePapers({ papers }: ClusterRepresentativePapersProps) {
  if (papers.length === 0) {
    return <EmptyState icon={FileText} title="No representative papers are available." />
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {papers.map((paper) => {
        const arxivUrl = arxivAbstractUrl(paper.arxiv_id)
        const pdfUrl = arxivPdfUrl(paper.arxiv_id)
        return (
          <div key={paper.paper_id} className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 shadow-panel">
            <div className="flex items-start gap-2">
              <FileText className="mt-0.5 size-4 shrink-0 text-accent-purple" aria-hidden="true" />
              <p className="text-sm font-medium text-foreground">{paper.title}</p>
            </div>
            {paper.arxiv_id && <p className="text-xs text-muted-foreground">arXiv:{paper.arxiv_id}</p>}
            <div className="mt-auto flex flex-wrap items-center gap-1.5">
              <Button asChild size="sm" variant="secondary" className="gap-1.5">
                <Link
                  to={`/papers/${paper.paper_id}/similar`}
                  state={{ sourcePaper: { paper_id: paper.paper_id, title: paper.title, arxiv_id: paper.arxiv_id } }}
                >
                  <Sparkles className="size-3.5" aria-hidden="true" />
                  Explore Similar Papers
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
          </div>
        )
      })}
    </div>
  )
}
