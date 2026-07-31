import { Badge } from '@/components/ui/badge'

interface CategoryBadgeProps {
  category: string
}

export function CategoryBadge({ category }: CategoryBadgeProps) {
  return (
    <Badge variant="secondary" className="text-[11px]">
      {category}
    </Badge>
  )
}
