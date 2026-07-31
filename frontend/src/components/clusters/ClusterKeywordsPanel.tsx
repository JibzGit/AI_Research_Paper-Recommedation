interface ClusterKeywordsPanelProps {
  keywords: string[]
}

export function ClusterKeywordsPanel({ keywords }: ClusterKeywordsPanelProps) {
  return (
    <div className="flex h-full flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-panel">
      <h3 className="text-sm font-medium text-foreground">Keywords</h3>
      {keywords.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {keywords.map((keyword) => (
            <span key={keyword} className="rounded-full bg-muted px-2.5 py-1 text-xs break-words text-muted-foreground">
              {keyword}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground italic">No keywords are available for this cluster.</p>
      )}
    </div>
  )
}
