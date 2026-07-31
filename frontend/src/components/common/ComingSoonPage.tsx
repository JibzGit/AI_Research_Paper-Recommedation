import { Construction, type LucideIcon } from 'lucide-react'

interface ComingSoonPageProps {
  title: string
  description?: string
  icon?: LucideIcon
}

/** Shared placeholder for nav sections with no backing API yet (Trending,
 * Authors, Organizations, Datasets, Models, Daily Digest, Saved Papers). */
export function ComingSoonPage({ title, description, icon: Icon = Construction }: ComingSoonPageProps) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-card/40 p-10 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-accent-purple/10 text-accent-purple">
        <Icon className="size-6" aria-hidden="true" />
      </div>
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        {description ?? "This section isn't available yet. It's on the roadmap for a future phase."}
      </p>
    </div>
  )
}
