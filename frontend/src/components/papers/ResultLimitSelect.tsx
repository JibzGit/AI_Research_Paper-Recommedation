import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { TOP_K_OPTIONS } from '@/lib/searchParams'

interface ResultLimitSelectProps {
  value: number
  onChange: (value: number) => void
}

export function ResultLimitSelect({ value, onChange }: ResultLimitSelectProps) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor="result-limit-select" className="text-xs text-muted-foreground">
        Results
      </Label>
      <Select value={String(value)} onValueChange={(next) => onChange(Number(next))}>
        <SelectTrigger id="result-limit-select" className="h-9 w-20 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {TOP_K_OPTIONS.map((option) => (
            <SelectItem key={option} value={String(option)}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
