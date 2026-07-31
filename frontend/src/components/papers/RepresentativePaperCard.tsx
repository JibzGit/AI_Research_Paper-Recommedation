import { ExternalLink, FileText, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { arxivAbstractUrl, arxivPdfUrl } from '@/lib/arxiv'

export interface RepresentativePaperCardData {
  paperId: string
  arxivId: string | null
  title: string
  clusterId: number
  clusterName: string
}

export function RepresentativePaperCard({ paper }: { paper: RepresentativePaperCardData }) {
  const arxivUrl = arxivAbstractUrl(paper.arxivId)
  const pdfUrl = arxivPdfUrl(paper.arxivId)

  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="flex items-start gap-2">
        <FileText className="mt-0.5 size-4 shrink-0 text-accent-purple" aria-hidden="true" />
        <p className="text-sm font-medium text-foreground">{paper.title}</p>
      </div>
      {paper.arxivId && <p className="text-xs text-muted-foreground">arXiv:{paper.arxivId}</p>}
      <Link
        to={`/clusters/${paper.clusterId}`}
        className="w-fit rounded text-xs font-medium text-accent-blue hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        From &ldquo;{paper.clusterName}&rdquo; →
      </Link>
      <div className="mt-auto flex flex-wrap items-center gap-1.5 border-t border-border pt-2">
        <Button asChild size="sm" variant="secondary" className="gap-1.5">
          <Link to={`/papers/${paper.paperId}/similar`} state={{ sourcePaper: { paper_id: paper.paperId, title: paper.title, arxiv_id: paper.arxivId } }}>
            <Sparkles className="size-3.5" aria-hidden="true" />
            Find Similar Papers
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
}
