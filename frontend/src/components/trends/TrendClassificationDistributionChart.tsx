import { Gauge } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts'

import type { TrendClassification } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'

interface TrendClassificationDistributionChartProps {
  classificationCounts: Record<string, number>
}

// Fixed display order (not sorted by count) so the chart's shape stays
// legible/comparable across renders regardless of which classifications
// happen to be largest this run. Colors mirror TrendClassificationBadge's
// choices exactly -- Stable/Insufficient Data stay neutral since neither
// is a positive or negative signal.
const CLASSIFICATION_ORDER: TrendClassification[] = [
  'Emerging',
  'Accelerating',
  'Consistently Active',
  'Stable',
  'Cooling',
  'Insufficient Data',
]
const CLASSIFICATION_COLOR: Record<TrendClassification, string> = {
  Emerging: 'var(--color-accent-green)',
  Accelerating: 'var(--color-accent-purple)',
  'Consistently Active': 'var(--color-accent-blue)',
  Stable: 'var(--color-muted-foreground)',
  Cooling: 'var(--color-accent-orange)',
  'Insufficient Data': 'var(--color-muted-foreground)',
}

interface ChartDatum {
  classification: TrendClassification
  count: number
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartDatum }> }) {
  const datum = active ? payload?.[0]?.payload : undefined
  if (!datum) return null
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-panel-lg">
      <p className="font-medium text-popover-foreground">{datum.classification}</p>
      <p className="text-muted-foreground">
        {datum.count} {datum.count === 1 ? 'entity' : 'entities'}
      </p>
    </div>
  )
}

export function TrendClassificationDistributionChart({ classificationCounts }: TrendClassificationDistributionChartProps) {
  const data: ChartDatum[] = CLASSIFICATION_ORDER.map((classification) => ({
    classification,
    count: classificationCounts[classification] ?? 0,
  })).filter((datum) => datum.count > 0)

  if (data.length === 0) {
    return <EmptyState icon={Gauge} title="No trend classifications yet" description="No entities have been scored in this run." />
  }

  return (
    <div role="img" aria-label={`Bar chart of trend classification counts across ${data.length} classifications.`}>
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 40)}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
          <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} allowDecimals={false} />
          <YAxis type="category" dataKey="classification" width={120} stroke="var(--color-muted-foreground)" fontSize={11} />
          <RechartsTooltip content={<ChartTooltip />} cursor={{ fill: 'var(--color-muted)' }} />
          <Bar dataKey="count" radius={[0, 6, 6, 0]}>
            {data.map((entry) => (
              <Cell key={entry.classification} fill={CLASSIFICATION_COLOR[entry.classification]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
