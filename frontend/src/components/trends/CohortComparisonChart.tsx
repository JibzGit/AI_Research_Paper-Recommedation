import { BarChart3 } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts'

import type { TrendResult } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'

interface CohortComparisonChartProps {
  results: TrendResult[]
}

const COMPARISON_COLOR = 'var(--color-accent-blue)'
const RECENT_COLOR = 'var(--color-accent-purple)'
const MAX_LABEL_LENGTH = 22

function truncateLabel(label: string): string {
  return label.length > MAX_LABEL_LENGTH ? `${label.slice(0, MAX_LABEL_LENGTH - 1)}…` : label
}

interface ChartDatum {
  id: string
  fullName: string
  comparisonCount: number
  recentCount: number
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartDatum }> }) {
  const datum = active ? payload?.[0]?.payload : undefined
  if (!datum) return null
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-panel-lg">
      <p className="font-medium text-popover-foreground">{datum.fullName}</p>
      <p className="text-muted-foreground">Comparison cohort: {datum.comparisonCount} papers</p>
      <p className="text-muted-foreground">Recent cohort: {datum.recentCount} papers</p>
    </div>
  )
}

/** Grouped horizontal bars -- two per entity, one for each cohort. Not a
 * time series: the two cohorts are two disjoint publication batches (see
 * HistoricalCohortWarning), not adjacent points on a continuous timeline,
 * so this never renders as a connected line. */
export function CohortComparisonChart({ results }: CohortComparisonChartProps) {
  if (results.length === 0) {
    return <EmptyState icon={BarChart3} title="No entities to compare" description="No trend results are available for this view." />
  }

  const data: ChartDatum[] = results.map((result) => ({
    id: `${result.entity_type}-${result.entity_id}`,
    fullName: result.entity_name,
    comparisonCount: result.metrics.previous_paper_count,
    recentCount: result.metrics.recent_paper_count,
  }))

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-full" style={{ backgroundColor: COMPARISON_COLOR }} aria-hidden="true" />
          Comparison cohort
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-full" style={{ backgroundColor: RECENT_COLOR }} aria-hidden="true" />
          Recent cohort
        </span>
      </div>
      <div
        role="img"
        aria-label={`Grouped bar chart comparing comparison-cohort and recent-cohort paper counts across ${data.length} entities.`}
      >
        <ResponsiveContainer width="100%" height={Math.max(180, data.length * 44)}>
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
            <Bar dataKey="comparisonCount" fill={COMPARISON_COLOR} radius={[0, 4, 4, 0]} />
            <Bar dataKey="recentCount" fill={RECENT_COLOR} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
