import { Bookmark, Building2, Cpu, Database, Newspaper, Sparkles, TrendingUp, Users } from 'lucide-react'
import { Route, Routes } from 'react-router-dom'

import { ComingSoonPage } from '@/components/common/ComingSoonPage'
import { AppShell } from '@/components/layout/AppShell'
import { ClusterDetailPage } from '@/pages/ClusterDetailPage'
import { ClustersPage } from '@/pages/ClustersPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { NoisePapersPage } from '@/pages/NoisePapersPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { SearchPage } from '@/pages/SearchPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SimilarPapersPage } from '@/pages/SimilarPapersPage'

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
