import { Menu, Search } from 'lucide-react'
import { type RefObject, type SubmitEvent, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getPageTitle } from '@/lib/routeTitles'

interface TopBarProps {
  onMenuClick: () => void
  menuButtonRef: RefObject<HTMLButtonElement | null>
}

export function TopBar({ onMenuClick, menuButtonRef }: TopBarProps) {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  const location = useLocation()

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = query.trim()
    navigate(trimmed ? `/search?q=${encodeURIComponent(trimmed)}` : '/search')
  }

  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-background/85 px-4 py-3 backdrop-blur supports-backdrop-filter:bg-background/60">
      <Button
        ref={menuButtonRef}
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={onMenuClick}
        aria-label="Toggle navigation menu"
      >
        <Menu className="size-5" aria-hidden="true" />
      </Button>

      {/* sr-only (not `hidden`) below md: `hidden` removes the element from
       * the accessibility tree entirely, which would leave zero <h1> on
       * mobile viewports -- exactly where most real screen-reader users
       * would be. The page's one document h1 must exist regardless of
       * viewport width; only its visual presentation is responsive. */}
      <h1 className="sr-only truncate text-sm font-medium text-foreground md:not-sr-only md:block">
        {getPageTitle(location.pathname)}
      </h1>

      <form onSubmit={handleSubmit} className="ml-auto flex w-full max-w-sm items-center" role="search">
        <div className="relative w-full">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            placeholder="Search papers..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="pl-8"
            aria-label="Search papers"
          />
        </div>
      </form>
    </header>
  )
}
