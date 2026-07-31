import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { parseOptionalInt } from '@/lib/searchParams'

interface YearRangeFilterProps {
  yearFrom: number | null
  yearTo: number | null
  onYearFromChange: (value: number | null) => void
  onYearToChange: (value: number | null) => void
  error?: string
}

export function YearRangeFilter({ yearFrom, yearTo, onYearFromChange, onYearToChange, error }: YearRangeFilterProps) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs text-muted-foreground">Year range</Label>
      <div className="flex items-center gap-1.5">
        <Input
          type="number"
          inputMode="numeric"
          placeholder="From"
          value={yearFrom ?? ''}
          onChange={(event) => onYearFromChange(parseOptionalInt(event.target.value))}
          className="h-9 w-20 text-xs"
          aria-label="Year from"
          aria-invalid={Boolean(error)}
        />
        <span className="text-xs text-muted-foreground" aria-hidden="true">
          &ndash;
        </span>
        <Input
          type="number"
          inputMode="numeric"
          placeholder="To"
          value={yearTo ?? ''}
          onChange={(event) => onYearToChange(parseOptionalInt(event.target.value))}
          className="h-9 w-20 text-xs"
          aria-label="Year to"
          aria-invalid={Boolean(error)}
        />
      </div>
      {error && <p className="text-[11px] text-accent-error">{error}</p>}
    </div>
  )
}
