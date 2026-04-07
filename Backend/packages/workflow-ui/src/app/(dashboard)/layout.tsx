// ─────────────────────────────────────────────────────────────────────────────
// App shell — sidebar + topbar wrapper for all protected routes
// Layout from docs/frontend/handover.md §9
// ─────────────────────────────────────────────────────────────────────────────

import { Sidebar } from '@/components/shared/Sidebar'
import { TopBar } from '@/components/shared/TopBar'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <TopBar />
        <main className="flex-1 overflow-auto p-6 relative">{children}</main>
      </div>
    </div>
  )
}
