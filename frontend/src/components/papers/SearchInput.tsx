import { Search, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface SearchInputProps {
  value: string
  onChange: (value: string) => void
  id?: string
  placeholder?: string
  ariaLabel?: string
}

/** Enter-to-submit works for free when this renders inside a <form>: a text
 * input inside a form submits on Enter natively. placeholder/ariaLabel are
 * optional so existing callers (Paper Search) are unaffected by defaults;
 * the Research Clusters page overrides both for its client-side search. */
export function SearchInput({
  value,
  onChange,
  id = 'paper-search-query',
  placeholder = 'Describe a topic, method, or research problem...',
  ariaLabel = 'Search query',
}: SearchInputProps) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
      <Input
        id={id}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="h-11 pr-9 pl-9 text-sm"
        aria-label={ariaLabel}
      />
      {value && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
          onClick={() => onChange('')}
          aria-label="Clear search text"
        >
          <X className="size-3.5" aria-hidden="true" />
        </Button>
      )}
    </div>
  )
}
