import {
  Bookmark,
  Building2,
  Cpu,
  Database,
  LayoutDashboard,
  LineChart,
  Network,
  Newspaper,
  Search,
  Settings as SettingsIcon,
  Sparkles,
  TrendingUp,
  Users,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  label: string
  href: string
  icon: LucideIcon
  /** MVP-implemented sections have no badge; everything else shows "Soon". */
  soon?: boolean
}

export const APP_NAME = 'Sightline'
export const APP_TAGLINE = 'Research Intelligence'

export const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard },
  { label: 'Trending Papers', href: '/trending', icon: TrendingUp, soon: true },
  { label: 'Paper Search', href: '/search', icon: Search },
  { label: 'Recommendations', href: '/recommendations', icon: Sparkles, soon: true },
  { label: 'Research Clusters', href: '/clusters', icon: Network },
  { label: 'Research Trends', href: '/trends', icon: LineChart },
  { label: 'Authors', href: '/authors', icon: Users, soon: true },
  { label: 'Organizations', href: '/organizations', icon: Building2, soon: true },
  { label: 'Datasets', href: '/datasets', icon: Database, soon: true },
  { label: 'Models', href: '/models', icon: Cpu, soon: true },
  { label: 'Daily Digest', href: '/digest', icon: Newspaper, soon: true },
  { label: 'Saved Papers', href: '/saved', icon: Bookmark, soon: true },
  { label: 'Settings', href: '/settings', icon: SettingsIcon },
]
