import { Shuffle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

interface UnclusteredCalloutProps {
  /** PlatformOverview.noise_papers -- a real count, never invented. */
  noisePaperCount: number
}

export function UnclusteredCallout({ noisePaperCount }: UnclusteredCalloutProps) {
  return (
    <div className="flex h-full flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="flex items-center gap-2">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-accent-orange/10 text-accent-orange">
          <Shuffle className="size-4" aria-hidden="true" />
        </div>
        <h3 className="text-sm font-medium text-foreground">Unclustered Papers</h3>
      </div>
      <p className="text-sm text-muted-foreground">
        {noisePaperCount} {noisePaperCount === 1 ? 'paper was' : 'papers were'} not confidently assigned to a research
        cluster in the latest run.
      </p>
      <Button asChild size="sm" variant="secondary" className="mt-auto w-fit gap-1.5">
        <Link to="/clusters/noise">
          <Shuffle className="size-3.5" aria-hidden="true" />
          Browse Unclustered Papers
        </Link>
      </Button>
    </div>
  )
}
