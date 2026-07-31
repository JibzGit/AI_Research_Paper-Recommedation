import { Suspense, useRef, useState } from 'react'
import { Outlet } from 'react-router-dom'

import { RouteLoadingFallback } from '@/components/layout/RouteLoadingFallback'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  function closeSidebar() {
    setSidebarOpen(false)
    // Returns focus to the toggle button when the drawer closes via the
    // drawer itself (nav-link click, scrim click, Escape) -- toggling it
    // closed from the button itself keeps focus there already.
    menuButtonRef.current?.focus()
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar open={sidebarOpen} onClose={closeSidebar} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar menuButtonRef={menuButtonRef} onMenuClick={() => setSidebarOpen((prev) => !prev)} />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          {/* Boundary wraps only the routed content, not Sidebar/TopBar --
           * the layout never unmounts or flashes while a lazy route chunk
           * loads. */}
          <Suspense fallback={<RouteLoadingFallback />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
