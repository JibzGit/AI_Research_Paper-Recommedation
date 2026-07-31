import { Network } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts'

import type { ClusterSummary } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'

interface ClusterDistributionChartProps {
  clusters: ClusterSummary[]
  noisePaperCount: number
  emptyDescription?: string
}

const BAR_COLORS = [
  'var(--color-accent-purple)',
  'var(--color-accent-blue)',
  'var(--color-accent-green)',
  'var(--color-accent-orange)',
]
const NOISE_COLOR = 'var(--color-muted-foreground)'
const MAX_LABEL_LENGTH = 22

function truncateLabel(label: string): string {
  return label.length > MAX_LABEL_LENGTH ? `${label.slice(0, MAX_LABEL_LENGTH - 1)}…` : label
}

interface ChartDatum {
  id: string
  fullName: string
  paperCount: number
  isNoise: boolean
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartDatum }> }) {
  const datum = active ? payload?.[0]?.payload : undefined
  if (!datum) return null
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-panel-lg">
      <p className="font-medium text-popover-foreground">{datum.fullName}</p>
      <p className="text-muted-foreground">{datum.paperCount} papers</p>
    </div>
  )
}

export function ClusterDistributionChart({ clusters, noisePaperCount, emptyDescription }: ClusterDistributionChartProps) {
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

  const data: ChartDatum[] = [
    ...clusters.map((cluster) => ({
      id: String(cluster.cluster_id),
      fullName: cluster.cluster_name,
      paperCount: cluster.paper_count,
      isNoise: false,
    })),
    ...(hasNoise ? [{ id: 'noise', fullName: 'Unclustered', paperCount: noisePaperCount, isNoise: true }] : []),
  ]

  return (
    <div
      role="img"
      aria-label={`Bar chart of paper counts across ${clusters.length} research clusters${hasNoise ? ' plus unclustered papers' : ''}.`}
    >
      <ResponsiveContainer width="100%" height={Math.max(240, data.length * 34)}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
          <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="fullName"
            width={140}
            stroke="var(--color-muted-foreground)"
            fontSize={11}
            tickFormatter={(value: string) => truncateLabel(value)}
          />
          <RechartsTooltip content={<ChartTooltip />} cursor={{ fill: 'var(--color-muted)' }} />
          <Bar dataKey="paperCount" radius={[0, 6, 6, 0]}>
            {data.map((entry, index) => (
              <Cell key={entry.id} fill={entry.isNoise ? NOISE_COLOR : (BAR_COLORS[index % BAR_COLORS.length] ?? NOISE_COLOR)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
