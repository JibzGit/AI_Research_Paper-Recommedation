import { Menu } from 'lucide-react'
import { type RefObject } from 'react'
import { useLocation } from 'react-router-dom'

import { GlobalSearchBar } from '@/components/search/GlobalSearchBar'
import { Button } from '@/components/ui/button'
import { getPageTitle } from '@/lib/routeTitles'

interface TopBarProps {
  onMenuClick: () => void
  menuButtonRef: RefObject<HTMLButtonElement | null>
}

export function TopBar({ onMenuClick, menuButtonRef }: TopBarProps) {
  const location = useLocation()

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

      <GlobalSearchBar />
    </header>
  )
}
