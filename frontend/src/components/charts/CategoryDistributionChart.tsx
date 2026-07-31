import { PieChart } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts'

import type { CategoryDistributionItem } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'

interface CategoryDistributionChartProps {
  distribution: CategoryDistributionItem[]
}

const BAR_COLORS = [
  'var(--color-accent-blue)',
  'var(--color-accent-purple)',
  'var(--color-accent-green)',
  'var(--color-accent-orange)',
]
const MAX_LABEL_LENGTH = 18

function truncateLabel(label: string): string {
  return label.length > MAX_LABEL_LENGTH ? `${label.slice(0, MAX_LABEL_LENGTH - 1)}…` : label
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: CategoryDistributionItem }> }) {
  const datum = active ? payload?.[0]?.payload : undefined
  if (!datum) return null
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-panel-lg">
      <p className="font-medium text-popover-foreground">{datum.category}</p>
      <p className="text-muted-foreground">
        {datum.count} papers · {datum.percent}%
      </p>
    </div>
  )
}

/** category_distribution's percent field comes straight from the backend
 * -- never recomputed client-side from count/total. */
export function CategoryDistributionChart({ distribution }: CategoryDistributionChartProps) {
  if (distribution.length === 0) {
    return <EmptyState icon={PieChart} title="No category distribution is available for this cluster." />
  }

  return (
    <div
      role="img"
      aria-label={`Bar chart of this cluster's papers across ${distribution.length} categories, showing paper count and percent share per category.`}
    >
      <ResponsiveContainer width="100%" height={Math.max(160, distribution.length * 40)}>
        <BarChart data={distribution} layout="vertical" margin={{ left: 8, right: 40, top: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
          <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="category"
            width={90}
            stroke="var(--color-muted-foreground)"
            fontSize={11}
            tickFormatter={(value: string) => truncateLabel(value)}
          />
          <RechartsTooltip content={<ChartTooltip />} cursor={{ fill: 'var(--color-muted)' }} />
          <Bar dataKey="count" radius={[0, 6, 6, 0]}>
            <LabelList
              dataKey="percent"
              position="right"
              formatter={(value: string | number | boolean | null | undefined) => (typeof value === 'number' ? `${value}%` : '')}
              fill="var(--color-muted-foreground)"
              fontSize={11}
            />
            {distribution.map((entry, index) => (
              <Cell key={entry.category} fill={BAR_COLORS[index % BAR_COLORS.length] ?? 'var(--color-muted-foreground)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
