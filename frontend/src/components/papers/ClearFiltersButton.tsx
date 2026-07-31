import { X } from 'lucide-react'

import { Button } from '@/components/ui/button'

interface ClearFiltersButtonProps {
  onClear: () => void
  disabled?: boolean
}

export function ClearFiltersButton({ onClear, disabled }: ClearFiltersButtonProps) {
  return (
    <Button type="button" variant="ghost" size="sm" onClick={onClear} disabled={disabled} className="gap-1.5 text-muted-foreground">
      <X className="size-3.5" aria-hidden="true" />
      Clear filters
    </Button>
  )
}
