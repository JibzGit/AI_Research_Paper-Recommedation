import { Settings } from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'

export function SettingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Settings</h2>
        <p className="text-sm text-muted-foreground">Application preferences.</p>
      </div>
      <EmptyState
        icon={Settings}
        title="No settings yet"
        description="This application has no user accounts or configurable preferences at this stage."
      />
    </div>
  )
}
