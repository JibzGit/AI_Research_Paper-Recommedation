import { Info } from 'lucide-react'

/**
 * Compact, always-visible explanation of the difference between arXiv
 * categories and discovered clusters -- static copy, no data dependency.
 * Exists to stop category codes (cs.CV, cs.IR, ...) from being read as
 * cluster labels, since a cluster's dominant_category badge and a
 * category chip can otherwise look interchangeable at a glance.
 */
export function CategoryVsClusterInfo() {
  return (
    <div className="flex items-start gap-2.5 rounded-2xl border border-border bg-card/60 p-4">
      <Info className="mt-0.5 size-4 shrink-0 text-accent-blue" aria-hidden="true" />
      <div className="flex flex-col gap-1 text-xs text-muted-foreground">
        <p className="font-medium text-foreground">Categories vs. clusters -- these are two different things</p>
        <p>
          <span className="font-medium text-foreground">Categories</span> (like{' '}
          <span className="font-mono">cs.CV</span> or <span className="font-mono">cs.IR</span>) are a fixed taxonomy
          assigned by the paper&rsquo;s source on arXiv.
        </p>
        <p>
          <span className="font-medium text-foreground">Clusters</span> are discovered automatically from embedding
          and content similarity, and use their own generated names and symbols (C01, C02, ...) -- never a category
          code.
        </p>
        <p>A single cluster can span multiple categories, and papers in one category can land in several different clusters.</p>
      </div>
    </div>
  )
}
