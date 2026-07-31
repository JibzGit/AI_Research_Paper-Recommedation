import { BookOpen } from 'lucide-react'

import { TrendClassificationBadge } from '@/components/trends/TrendClassificationBadge'
import type { TrendClassification } from '@/api/types'

interface GuideEntry {
  classification: TrendClassification
  description: string
}

// Plain-language restatement of the backend's ordered classification rule
// table (research_platform/trends/classifications.py: classify_trend) --
// describes the real rule each label maps to, not an invented definition.
const GUIDE_ENTRIES: GuideEntry[] = [
  {
    classification: 'Emerging',
    description:
      'No papers in the comparison cohort, but real paper volume in the recent cohort. A new appearance in this corpus -- it does not prove an entire research area is newly created.',
  },
  {
    classification: 'Accelerating',
    description: 'Strong positive growth between the two cohorts that is itself speeding up, measured against a real comparison-period baseline.',
  },
  {
    classification: 'Consistently Active',
    description: 'High consistency with flat-to-moderate growth -- a steady presence across both cohorts rather than a sharp swing.',
  },
  {
    classification: 'Stable',
    description: 'Growth between the two cohorts stayed within a narrow band of the comparison-period baseline -- neither rising nor falling much.',
  },
  {
    classification: 'Cooling',
    description: 'Paper volume dropped sharply from the comparison-period baseline.',
  },
  {
    classification: 'Insufficient Data',
    description: 'Too few total papers (or no cohort with enough volume) to support a reliable classification either way.',
  },
]

/** Static reference -- how to read the six trend classifications this
 * dashboard and the Research Trends page use. No data dependency; the
 * cohort dates/warning text themselves come from HistoricalCohortWarning,
 * rendered separately using real backend data. */
export function TrendLabelGuide() {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
        <BookOpen className="size-4 text-accent-purple" aria-hidden="true" />
        How to read trend labels
      </h3>
      <dl className="grid gap-3 sm:grid-cols-2">
        {GUIDE_ENTRIES.map((entry) => (
          <div key={entry.classification} className="flex flex-col gap-1">
            <dt>
              <TrendClassificationBadge classification={entry.classification} />
            </dt>
            <dd className="text-xs text-muted-foreground">{entry.description}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
