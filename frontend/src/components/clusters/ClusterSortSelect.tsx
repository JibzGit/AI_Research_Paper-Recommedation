import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { CLUSTER_SORT_OPTIONS, type ClusterSortOption } from '@/lib/clusterDiscoveryParams'

interface ClusterSortSelectProps {
  value: ClusterSortOption
  onChange: (value: ClusterSortOption) => void
}

export function ClusterSortSelect({ value, onChange }: ClusterSortSelectProps) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor="cluster-sort-select" className="text-xs text-muted-foreground">
        Sort by
      </Label>
      <Select value={value} onValueChange={(next) => onChange(next as ClusterSortOption)}>
        <SelectTrigger id="cluster-sort-select" className="h-9 w-full text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {CLUSTER_SORT_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
