import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const ALL_CATEGORIES_VALUE = '__all__'

interface ClusterCategoryFilterProps {
  value: string | null
  onChange: (value: string | null) => void
  /** Dominant categories among the loaded clusters -- not a separate
   * /api/v1/categories fetch, which would reflect the whole corpus rather
   * than just these clusters. */
  categories: string[]
}

export function ClusterCategoryFilter({ value, onChange, categories }: ClusterCategoryFilterProps) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor="cluster-category-filter" className="text-xs text-muted-foreground">
        Dominant category
      </Label>
      <Select value={value ?? ALL_CATEGORIES_VALUE} onValueChange={(next) => onChange(next === ALL_CATEGORIES_VALUE ? null : next)}>
        <SelectTrigger id="cluster-category-filter" className="h-9 w-full text-xs">
          <SelectValue placeholder="All categories" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_CATEGORIES_VALUE}>All categories</SelectItem>
          {categories.map((category) => (
            <SelectItem key={category} value={category}>
              {category}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
