import { Bookmark, Building2, Cpu, Database, Newspaper, Sparkles, TrendingUp, Users } from 'lucide-react'
import { lazy } from 'react'
import { Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'

// AppShell (Sidebar/TopBar) stays eager -- it's the app frame, never
// route-specific. Every page is code-split: React Router only ever renders
// one route element at a time, so each page's chunk loads on first visit
// rather than bloating the initial bundle. All pages use named exports, so
// each dynamic import resolves that named export into the `default` shape
// React.lazy() requires.
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const SearchPage = lazy(() => import('@/pages/SearchPage').then((m) => ({ default: m.SearchPage })))
const SimilarPapersPage = lazy(() => import('@/pages/SimilarPapersPage').then((m) => ({ default: m.SimilarPapersPage })))
const ClustersPage = lazy(() => import('@/pages/ClustersPage').then((m) => ({ default: m.ClustersPage })))
const ClusterDetailPage = lazy(() => import('@/pages/ClusterDetailPage').then((m) => ({ default: m.ClusterDetailPage })))
const NoisePapersPage = lazy(() => import('@/pages/NoisePapersPage').then((m) => ({ default: m.NoisePapersPage })))
const SettingsPage = lazy(() => import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })))
const ComingSoonPage = lazy(() => import('@/components/common/ComingSoonPage').then((m) => ({ default: m.ComingSoonPage })))

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/papers/:paperId/similar" element={<SimilarPapersPage />} />

        <Route path="/clusters" element={<ClustersPage />} />
        {/* Declared before /clusters/:clusterId to mirror the backend's own
            /clusters/noise-before-/{cluster_id} convention for readability
            -- React Router v6 actually ranks static segments above dynamic
            ones regardless of declaration order, so this ordering isn't
            load-bearing here the way it is in the FastAPI route table. */}
        <Route path="/clusters/noise" element={<NoisePapersPage />} />
        <Route path="/clusters/:clusterId" element={<ClusterDetailPage />} />

        <Route path="/settings" element={<SettingsPage />} />

        <Route path="/trending" element={<ComingSoonPage title="Trending Papers" icon={TrendingUp} />} />
        <Route path="/recommendations" element={<ComingSoonPage title="Recommendations" icon={Sparkles} />} />
        <Route path="/authors" element={<ComingSoonPage title="Authors" icon={Users} />} />
        <Route path="/organizations" element={<ComingSoonPage title="Organizations" icon={Building2} />} />
        <Route path="/datasets" element={<ComingSoonPage title="Datasets" icon={Database} />} />
        <Route path="/models" element={<ComingSoonPage title="Models" icon={Cpu} />} />
        <Route path="/digest" element={<ComingSoonPage title="Daily Digest" icon={Newspaper} />} />
        <Route path="/saved" element={<ComingSoonPage title="Saved Papers" icon={Bookmark} />} />

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
