import { X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'

interface FilterChipProps {
  label: string
  onRemove: () => void
}

/** Shared by PaperSearchFilters and SimilarPaperFilters -- an active-filter
 * indicator with an inline remove control. */
export function FilterChip({ label, onRemove }: FilterChipProps) {
  return (
    <Badge variant="outline" className="gap-1 border-primary/40 text-primary">
      {label}
      <button
        type="button"
        onClick={onRemove}
        className="ml-0.5 rounded-full hover:text-foreground focus-visible:outline-none"
        aria-label={`Remove filter: ${label}`}
      >
        <X className="size-3" aria-hidden="true" />
      </button>
    </Badge>
  )
}
