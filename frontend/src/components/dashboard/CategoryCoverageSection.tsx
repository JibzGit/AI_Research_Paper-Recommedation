import { ChevronDown, ChevronUp, Tags } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CardSkeleton } from '@/components/common/LoadingSkeleton'
import { useCategories } from '@/hooks/useCategories'
import { usePlatformOverview } from '@/hooks/usePlatformOverview'
import { getCategoryDisplayName } from '@/lib/categoryDisplayNames'

const COMPACT_CHIP_COUNT = 8

function safePercent(numerator: number, denominator: number): number | null {
  if (denominator <= 0) return null
  return Math.round((numerator / denominator) * 1000) / 10
}

/**
 * The corpus's arXiv category index -- every value here comes straight
 * from GET /api/v1/categories (code, display_name, paper_count) and the
 * platform overview's total paper count. Category codes are the source
 * taxonomy, distinct from the discovered research clusters shown
 * elsewhere on the dashboard (see CategoryVsClusterInfo).
 *
 * Known limitation: the links below only set `?category=`, never a query.
 * GET /api/v1/papers/search requires non-empty query text (confirmed: a
 * request with only `category` and no `query` gets a 422, and an empty
 * `query=""` gets a 400) -- there is no "browse all papers in category X"
 * endpoint. So these links land on Paper Search with the category filter
 * pre-applied, but usePaperSearch's `hasQuery` gate (see usePaperSearch.ts)
 * correctly withholds the request until the user types something; the
 * page shows its normal "type a query" prompt rather than auto-loading
 * results. This is the closest reliable behavior without adding a backend
 * browse-all endpoint, not a bug.
 */
export function CategoryCoverageSection() {
  const categoriesQuery = useCategories()
  const overviewQuery = usePlatformOverview()
  const [expanded, setExpanded] = useState(false)

  if (categoriesQuery.isLoading) {
    return <CardSkeleton />
  }

  if (categoriesQuery.isError) {
    return <ErrorState error={categoriesQuery.error} onRetry={() => void categoriesQuery.refetch()} />
  }

  const categories = categoriesQuery.data?.categories ?? []
  if (categories.length === 0) {
    return <EmptyState icon={Tags} title="No categories represented yet" description="Categories appear once papers are ingested." />
  }

  const totalPapers = overviewQuery.data?.total_canonical_papers ?? categories.reduce((sum, category) => sum + category.paper_count, 0)
  const sorted = [...categories].sort((a, b) => b.paper_count - a.paper_count)
  const compact = sorted.slice(0, COMPACT_CHIP_COUNT)
  const hiddenCount = sorted.length - compact.length
  const visible = expanded ? sorted : compact

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <Tags className="size-4 text-accent-green" aria-hidden="true" />
            Corpus coverage by category
          </h3>
          <p className="text-xs text-muted-foreground">
            {sorted.length} arXiv {sorted.length === 1 ? 'category' : 'categories'} represented in the corpus.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5" role="list" aria-label="Category chips, compact view">
        {compact.map((category) => (
          <Link
            key={category.code}
            to={`/search?category=${encodeURIComponent(category.code)}`}
            role="listitem"
            className="flex items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-1 text-[11px] text-foreground transition-colors hover:border-primary/50 hover:bg-muted/70 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            title={`${getCategoryDisplayName(category.code, category.display_name)} (${category.code})`}
          >
            <span className="font-mono text-muted-foreground">{category.code}</span>
            <span className="tabular-nums text-muted-foreground">{category.paper_count}</span>
          </Link>
        ))}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[30rem] text-left text-xs">
          <caption className="sr-only">Full category index with code, name, paper count, and percentage of the corpus.</caption>
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th scope="col" className="px-3 py-2 font-medium">Code</th>
              <th scope="col" className="px-3 py-2 font-medium">Name</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Papers</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Share</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {visible.map((category) => {
              const percent = safePercent(category.paper_count, totalPapers)
              return (
                <tr key={category.code}>
                  <td className="px-3 py-2 font-mono text-muted-foreground">{category.code}</td>
                  <td className="px-3 py-2">
                    <Link
                      to={`/search?category=${encodeURIComponent(category.code)}`}
                      className="rounded font-medium text-foreground hover:text-accent-blue hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                    >
                      {getCategoryDisplayName(category.code, category.display_name)}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{category.paper_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{percent === null ? '—' : `${percent}%`}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {hiddenCount > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="flex w-fit items-center gap-1 rounded text-xs font-medium text-accent-blue hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          aria-expanded={expanded}
        >
          {expanded ? (
            <>
              <ChevronUp className="size-3.5" aria-hidden="true" />
              Show fewer categories
            </>
          ) : (
            <>
              <ChevronDown className="size-3.5" aria-hidden="true" />
              Show all {sorted.length} categories ({hiddenCount} more)
            </>
          )}
        </button>
      )}
    </div>
  )
}
