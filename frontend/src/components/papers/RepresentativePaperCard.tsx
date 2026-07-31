import { FileText } from 'lucide-react'
import { Link } from 'react-router-dom'

export interface RepresentativePaperCardData {
  paperId: string
  arxivId: string | null
  title: string
  clusterId: number
  clusterName: string
}

export function RepresentativePaperCard({ paper }: { paper: RepresentativePaperCardData }) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="flex items-start gap-2">
        <FileText className="mt-0.5 size-4 shrink-0 text-accent-purple" aria-hidden="true" />
        <p className="text-sm font-medium text-foreground">{paper.title}</p>
      </div>
      {paper.arxivId && <p className="text-xs text-muted-foreground">arXiv:{paper.arxivId}</p>}
      <Link
        to={`/clusters/${paper.clusterId}`}
        className="mt-auto w-fit rounded text-xs font-medium text-accent-blue hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        From &ldquo;{paper.clusterName}&rdquo; →
      </Link>
    </div>
  )
}
