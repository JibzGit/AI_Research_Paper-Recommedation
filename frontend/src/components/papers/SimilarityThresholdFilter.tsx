import { Label } from '@/components/ui/label'
import { MIN_SIMILARITY_MAX, MIN_SIMILARITY_MIN } from '@/lib/searchParams'

const STEP = 0.05

interface SimilarityThresholdFilterProps {
  value: number | null
  onChange: (value: number | null) => void
  error?: string
}

/** Dragging to the minimum position clears the filter back to "Any" rather
 * than sending an explicit -1 -- min_similarity is optional on the
 * backend, and "no filter" and "filter at -1" are the same outcome anyway
 * since -1 is the bottom of cosine similarity's range. */
export function SimilarityThresholdFilter({ value, onChange, error }: SimilarityThresholdFilterProps) {
  const displayValue = value ?? MIN_SIMILARITY_MIN

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <Label htmlFor="min-similarity-slider" className="text-xs text-muted-foreground">
          Min. similarity
        </Label>
        <span className="text-xs font-medium text-foreground tabular-nums">{value === null ? 'Any' : displayValue.toFixed(2)}</span>
      </div>
      <input
        id="min-similarity-slider"
        type="range"
        min={MIN_SIMILARITY_MIN}
        max={MIN_SIMILARITY_MAX}
        step={STEP}
        value={displayValue}
        onChange={(event) => {
          const next = Number(event.target.value)
          onChange(next <= MIN_SIMILARITY_MIN ? null : next)
        }}
        className="h-9 w-full accent-primary"
        aria-label="Minimum semantic similarity"
        aria-valuetext={value === null ? 'Any' : displayValue.toFixed(2)}
      />
      {error && <p className="text-[11px] text-accent-error">{error}</p>}
    </div>
  )
}
