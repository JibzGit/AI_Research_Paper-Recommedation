import { FileSearch, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { ClusterEvidenceItem, RepresentativePaper } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'

interface ClusterEvidenceListProps {
  evidence: ClusterEvidenceItem[]
  representativePapers: RepresentativePaper[]
}

/** ClusterEvidenceItem only ever has paper_id + reason -- a title is shown
 * only when representativePapers happens to include the same paper_id (a
 * local Map lookup, never an extra request), and is never invented
 * otherwise. */
export function ClusterEvidenceList({ evidence, representativePapers }: ClusterEvidenceListProps) {
  if (evidence.length === 0) {
    return <EmptyState icon={FileSearch} title="No label evidence is available." />
  }

  const titleByPaperId = new Map(representativePapers.map((paper) => [paper.paper_id, paper.title]))

  return (
    <ul className="flex flex-col gap-2">
      {evidence.map((item) => {
        const matchedTitle = titleByPaperId.get(item.paper_id)
        return (
          <li key={item.paper_id} className="rounded-2xl border border-border bg-card p-4 shadow-panel">
            {matchedTitle && <p className="text-sm font-medium text-foreground">{matchedTitle}</p>}
            <p className="text-sm text-muted-foreground">{item.reason}</p>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <span className="truncate text-[11px] text-muted-foreground/70" title={item.paper_id}>
                Paper ID: {item.paper_id}
              </span>
              <Link
                to={`/papers/${item.paper_id}/similar`}
                state={matchedTitle ? { sourcePaper: { paper_id: item.paper_id, title: matchedTitle, arxiv_id: null } } : undefined}
                className="inline-flex shrink-0 items-center gap-1 rounded text-xs font-medium text-accent-blue hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <Sparkles className="size-3 shrink-0" aria-hidden="true" />
                Explore Similar Papers
              </Link>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
