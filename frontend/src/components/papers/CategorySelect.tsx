import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useCategories } from '@/hooks/useCategories'

const ALL_CATEGORIES_VALUE = '__all__'

interface CategorySelectProps {
  value: string | null
  onChange: (value: string | null) => void
}

/** Populated entirely from GET /api/v1/categories -- no free-text entry, so
 * a category filter can never reference a code that doesn't actually exist
 * in the corpus. */
export function CategorySelect({ value, onChange }: CategorySelectProps) {
  const categoriesQuery = useCategories()
  const categories = categoriesQuery.data?.categories ?? []

  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor="category-select" className="text-xs text-muted-foreground">
        Category
      </Label>
      <Select
        value={value ?? ALL_CATEGORIES_VALUE}
        onValueChange={(next) => onChange(next === ALL_CATEGORIES_VALUE ? null : next)}
      >
        <SelectTrigger id="category-select" className="h-9 w-full text-xs" disabled={categoriesQuery.isLoading}>
          <SelectValue placeholder={categoriesQuery.isLoading ? 'Loading categories...' : 'All categories'} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_CATEGORIES_VALUE}>All categories</SelectItem>
          {categories.map((category) => (
            <SelectItem key={category.code} value={category.code}>
              {category.display_name} ({category.paper_count})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {categoriesQuery.isError && <p className="text-[11px] text-accent-error">Categories unavailable right now.</p>}
    </div>
  )
}
