import { Network } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts'

import type { ClusterSummary } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'
import { assignClusterSymbols } from '@/lib/clusterSymbols'

interface ClusterDistributionChartProps {
  clusters: ClusterSummary[]
  noisePaperCount: number
  emptyDescription?: string
  /** Chart bars are capped to this many clusters (by paper count, desc) so
   * the chart stays readable as the corpus grows -- the full set is always
   * available in the accompanying legend/table, never dropped. */
  maxBars?: number
}

const BAR_COLORS = [
  'var(--color-accent-purple)',
  'var(--color-accent-blue)',
  'var(--color-accent-green)',
  'var(--color-accent-orange)',
]
const NOISE_COLOR = 'var(--color-muted-foreground)'
const DEFAULT_MAX_BARS = 8

interface ChartDatum {
  id: string
  symbol: string
  fullName: string
  paperCount: number
  isNoise: boolean
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartDatum }> }) {
  const datum = active ? payload?.[0]?.payload : undefined
  if (!datum) return null
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-panel-lg">
      <p className="font-medium text-popover-foreground">
        {datum.isNoise ? datum.fullName : `${datum.symbol} — ${datum.fullName}`}
      </p>
      <p className="text-muted-foreground">{datum.paperCount} papers</p>
    </div>
  )
}

export function ClusterDistributionChart({
  clusters,
  noisePaperCount,
  emptyDescription,
  maxBars = DEFAULT_MAX_BARS,
}: ClusterDistributionChartProps) {
  const hasClusters = clusters.length > 0
  const hasNoise = noisePaperCount > 0

  if (!hasClusters && !hasNoise) {
    return (
      <EmptyState
        icon={Network}
        title="No cluster data available"
        description={emptyDescription ?? 'No approved research clusters are available.'}
      />
    )
  }

  const symbols = assignClusterSymbols(clusters)
  const sortedByCount = [...clusters].sort((a, b) => b.paper_count - a.paper_count)
  const shown = sortedByCount.slice(0, maxBars)
  const hiddenCount = sortedByCount.length - shown.length

  const data: ChartDatum[] = [
    ...shown.map((cluster) => ({
      id: String(cluster.cluster_id),
      symbol: symbols.get(cluster.cluster_id) ?? '?',
      fullName: cluster.cluster_name,
      paperCount: cluster.paper_count,
      isNoise: false,
    })),
    ...(hasNoise ? [{ id: 'noise', symbol: '—', fullName: 'Unclustered', paperCount: noisePaperCount, isNoise: true }] : []),
  ]

  return (
    <div className="flex flex-col gap-2">
      <div
        role="img"
        aria-label={`Bar chart showing paper counts for the ${shown.length} largest research clusters (labeled by symbol)${hasNoise ? ', plus unclustered papers' : ''}. See the table below for full cluster names and details.`}
      >
        <ResponsiveContainer width="100%" height={Math.max(220, data.length * 34)}>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
            <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} allowDecimals={false} />
            <YAxis type="category" dataKey="symbol" width={48} stroke="var(--color-muted-foreground)" fontSize={11} />
            <RechartsTooltip content={<ChartTooltip />} cursor={{ fill: 'var(--color-muted)' }} />
            <Bar dataKey="paperCount" radius={[0, 6, 6, 0]}>
              {data.map((entry, index) => (
                <Cell key={entry.id} fill={entry.isNoise ? NOISE_COLOR : (BAR_COLORS[index % BAR_COLORS.length] ?? NOISE_COLOR)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {hiddenCount > 0 && (
        <p className="text-xs text-muted-foreground">
          Showing the {shown.length} largest of {sortedByCount.length} clusters. See the table below for all clusters.
        </p>
      )}
    </div>
  )
}
