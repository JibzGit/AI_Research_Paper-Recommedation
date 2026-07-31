import { Label } from '@/components/ui/label'
import { MIN_MEMBERSHIP_MAX, MIN_MEMBERSHIP_MIN } from '@/lib/clusterPaperParams'

const STEP = 0.05

interface MembershipThresholdFilterProps {
  value: number | null
  onChange: (value: number | null) => void
  error?: string
}

/** Same "drag to minimum clears the filter" convention as
 * SimilarityThresholdFilter, over [0, 1] instead of [-1, 1]. */
export function MembershipThresholdFilter({ value, onChange, error }: MembershipThresholdFilterProps) {
  const displayValue = value ?? MIN_MEMBERSHIP_MIN

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <Label htmlFor="min-membership-slider" className="text-xs text-muted-foreground">
          Min. membership
        </Label>
        <span className="text-xs font-medium text-foreground tabular-nums">{value === null ? 'Any' : displayValue.toFixed(2)}</span>
      </div>
      <input
        id="min-membership-slider"
        type="range"
        min={MIN_MEMBERSHIP_MIN}
        max={MIN_MEMBERSHIP_MAX}
        step={STEP}
        value={displayValue}
        onChange={(event) => {
          const next = Number(event.target.value)
          onChange(next <= MIN_MEMBERSHIP_MIN ? null : next)
        }}
        className="h-9 w-full accent-primary"
        aria-label="Minimum cluster membership"
        aria-valuetext={value === null ? 'Any' : displayValue.toFixed(2)}
      />
      {error && <p className="text-[11px] text-accent-error">{error}</p>}
    </div>
  )
}
