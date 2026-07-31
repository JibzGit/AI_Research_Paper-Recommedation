import type { PlatformOverview } from '@/api/types'

interface CorpusSummaryPanelProps {
  overview: PlatformOverview
}

interface CoverageRow {
  label: string
  percent: number | null
  barClassName: string
}

/** Percentages only, computed client-side from real counts -- never a
 * performance/quality score, and safe against a zero-paper corpus. */
function safePercent(numerator: number, denominator: number): number | null {
  if (denominator <= 0) return null
  return Math.round((numerator / denominator) * 1000) / 10
}

export function CorpusSummaryPanel({ overview }: CorpusSummaryPanelProps) {
  const rows: CoverageRow[] = [
    {
      label: 'Embedding coverage',
      percent: safePercent(overview.embedded_papers, overview.total_canonical_papers),
      barClassName: 'bg-accent-blue',
    },
    {
      label: 'Clustered-paper coverage',
      percent: safePercent(overview.clustered_papers, overview.total_canonical_papers),
      barClassName: 'bg-accent-purple',
    },
    {
      label: 'Unclustered-paper share',
      percent: safePercent(overview.noise_papers, overview.total_canonical_papers),
      barClassName: 'bg-accent-orange',
    },
  ]

  return (
    <div className="flex h-full flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div>
        <h3 className="text-sm font-medium text-foreground">Corpus coverage</h3>
        <p className="text-xs text-muted-foreground">Coverage metrics over the canonical corpus -- not performance scores.</p>
      </div>

      <div className="flex flex-col gap-3">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{row.label}</span>
              <span className="font-medium text-foreground tabular-nums">
                {row.percent === null ? '—' : `${row.percent}%`}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div className={`h-full rounded-full ${row.barClassName}`} style={{ width: `${row.percent ?? 0}%` }} />
            </div>
          </div>
        ))}
      </div>

      {overview.latest_clustering_run_id === null && (
        <p className="text-xs text-accent-orange">No successful clustering run is available yet.</p>
      )}
    </div>
  )
}
