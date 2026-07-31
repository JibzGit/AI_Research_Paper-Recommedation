import { ExternalLink, FileText, Search } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type SubmitEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import type { PaperResult } from '@/api/types'
import { Input } from '@/components/ui/input'
import { usePaperSearch } from '@/hooks/usePaperSearch'
import { arxivAbstractUrl, arxivPdfUrl } from '@/lib/arxiv'
import { formatAuthors } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import { useDebouncedValue } from '@/lib/useDebouncedValue'

const SUGGESTION_COUNT = 6
const DEBOUNCE_MS = 300

function suggestionYear(publicationDate: string | null): string | null {
  if (!publicationDate) return null
  const date = new Date(publicationDate)
  return Number.isNaN(date.getTime()) ? null : String(date.getUTCFullYear())
}

export function GlobalSearchBar() {
  const [rawQuery, setRawQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [syncedQueryForActiveIndex, setSyncedQueryForActiveIndex] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const listboxId = useId()

  const debouncedQuery = useDebouncedValue(rawQuery.trim(), DEBOUNCE_MS)
  const hasDebouncedQuery = debouncedQuery !== ''

  const suggestionsQuery = usePaperSearch(
    { query: debouncedQuery, topK: SUGGESTION_COUNT },
    { enabled: isOpen && hasDebouncedQuery },
  )

  const suggestions: PaperResult[] = useMemo(
    () => (isOpen && hasDebouncedQuery ? (suggestionsQuery.data?.results ?? []) : []),
    [isOpen, hasDebouncedQuery, suggestionsQuery.data],
  )

  // isFetching (not isLoading) so the "Searching..." row also reappears
  // while a later keystroke's debounced query is still in flight, not just
  // on the very first request.
  const isSearching = isOpen && hasDebouncedQuery && suggestionsQuery.isFetching
  const showEmpty = isOpen && hasDebouncedQuery && suggestionsQuery.isSuccess && suggestions.length === 0 && !isSearching
  const showError = isOpen && hasDebouncedQuery && suggestionsQuery.isError && !isSearching
  const showResults = isOpen && suggestions.length > 0
  const dropdownVisible = isOpen && hasDebouncedQuery && (isSearching || showEmpty || showError || showResults)

  // Reset the active suggestion whenever the debounced query itself
  // changes -- render-time adjustment (not an effect) per this codebase's
  // established pattern for resyncing derived state.
  if (debouncedQuery !== syncedQueryForActiveIndex) {
    setSyncedQueryForActiveIndex(debouncedQuery)
    setActiveIndex(-1)
  }

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [])

  function goToFullSearch(query: string) {
    setIsOpen(false)
    navigate(query ? `/search?query=${encodeURIComponent(query)}` : '/search')
  }

  function goToPaper(paper: PaperResult) {
    setIsOpen(false)
    navigate(`/papers/${paper.paper_id}/similar`, { state: { sourcePaper: paper } })
  }

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (activeIndex >= 0 && suggestions[activeIndex]) {
      goToPaper(suggestions[activeIndex])
      return
    }
    goToFullSearch(rawQuery.trim())
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      if (suggestions.length === 0) return
      event.preventDefault()
      setActiveIndex((current) => (current + 1 >= suggestions.length ? 0 : current + 1))
    } else if (event.key === 'ArrowUp') {
      if (suggestions.length === 0) return
      event.preventDefault()
      setActiveIndex((current) => (current - 1 < 0 ? suggestions.length - 1 : current - 1))
    } else if (event.key === 'Escape') {
      setIsOpen(false)
      setActiveIndex(-1)
    }
  }

  const activeOptionId = activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined

  return (
    <div ref={containerRef} className="relative ml-auto w-full max-w-sm">
      <form onSubmit={handleSubmit} role="search">
        <div className="relative w-full">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            placeholder="Search papers..."
            value={rawQuery}
            onChange={(event) => {
              setRawQuery(event.target.value)
              setIsOpen(true)
            }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={handleKeyDown}
            className="pl-8"
            aria-label="Search papers"
            role="combobox"
            aria-expanded={dropdownVisible}
            aria-controls={listboxId}
            aria-activedescendant={activeOptionId}
            autoComplete="off"
          />
        </div>
      </form>

      {dropdownVisible && (
        <div
          id={listboxId}
          role="listbox"
          aria-label="Search suggestions"
          className="absolute top-full right-0 z-40 mt-1.5 w-full min-w-[22rem] overflow-hidden rounded-xl border border-border bg-popover shadow-panel-lg"
        >
          {isSearching && <p className="px-3 py-3 text-xs text-muted-foreground">Searching…</p>}

          {showError && (
            <p className="px-3 py-3 text-xs text-accent-error">
              {suggestionsQuery.error?.detail ?? 'Search failed. Try again.'}
            </p>
          )}

          {showEmpty && <p className="px-3 py-3 text-xs text-muted-foreground">No papers found for &ldquo;{debouncedQuery}&rdquo;.</p>}

          {showResults && (
            <ul className="max-h-96 divide-y divide-border overflow-y-auto">
              {suggestions.map((paper, index) => (
                <SuggestionRow
                  key={paper.paper_id}
                  id={`${listboxId}-option-${index}`}
                  paper={paper}
                  active={index === activeIndex}
                  onSelect={() => goToPaper(paper)}
                  onHover={() => setActiveIndex(index)}
                />
              ))}
            </ul>
          )}

          {showResults && (
            <button
              type="button"
              onClick={() => goToFullSearch(rawQuery.trim())}
              className="w-full border-t border-border px-3 py-2 text-left text-xs font-medium text-accent-blue hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
            >
              See all results for &ldquo;{rawQuery.trim()}&rdquo;
            </button>
          )}
        </div>
      )}
    </div>
  )
}

interface SuggestionRowProps {
  id: string
  paper: PaperResult
  active: boolean
  onSelect: () => void
  onHover: () => void
}

function SuggestionRow({ id, paper, active, onSelect, onHover }: SuggestionRowProps) {
  const arxivUrl = arxivAbstractUrl(paper.arxiv_id)
  const pdfUrl = arxivPdfUrl(paper.arxiv_id)
  const year = suggestionYear(paper.publication_date)

  return (
    <li
      id={id}
      role="option"
      aria-selected={active}
      onMouseEnter={onHover}
      className={cn('flex items-start gap-2 px-3 py-2.5', active && 'bg-muted')}
    >
      <button type="button" onClick={onSelect} className="flex min-w-0 flex-1 flex-col items-start gap-0.5 text-left focus-visible:outline-none">
        <span className="line-clamp-1 text-xs font-medium text-foreground">{paper.title}</span>
        <span className="line-clamp-1 text-[11px] text-muted-foreground">
          {[paper.authors.length > 0 ? formatAuthors(paper.authors) : null, paper.primary_category, year].filter(Boolean).join(' · ')}
        </span>
      </button>
      <div className="flex shrink-0 items-center gap-0.5 pt-0.5">
        {arxivUrl && (
          <a
            href={arxivUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(event) => event.stopPropagation()}
            aria-label={`View "${paper.title}" on arXiv, opens in a new tab`}
            className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
        )}
        {pdfUrl && (
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(event) => event.stopPropagation()}
            aria-label={`Open the PDF for "${paper.title}", opens in a new tab`}
            className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <FileText className="size-3.5" aria-hidden="true" />
          </a>
        )}
      </div>
    </li>
  )
}
