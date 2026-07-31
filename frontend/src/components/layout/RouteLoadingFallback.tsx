import { Skeleton } from '@/components/ui/skeleton'

/**
 * Shown inside AppShell's <main> while a lazy-loaded route chunk is
 * fetched -- Sidebar/TopBar stay mounted throughout (the Suspense boundary
 * wraps only <Outlet />, not the whole shell), so only the content area
 * shows this placeholder. Echoes the header-card + card-grid shape most
 * pages already use, rather than a bare centered spinner.
 */
export function RouteLoadingFallback() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading page…</span>
      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-panel">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-3 w-2/3" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Skeleton className="h-40 rounded-2xl" />
        <Skeleton className="h-40 rounded-2xl" />
        <Skeleton className="h-40 rounded-2xl" />
      </div>
    </div>
  )
}
