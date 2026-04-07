// ─────────────────────────────────────────────────────────────────────────────
// Sidebar — 240px expanded / 48px collapsed
// Nav items from docs/frontend/overview.md §3 route map
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Workflow,
  Play,
  Calendar,
  ScrollText,
  Settings,
  ChevronLeft,
  ChevronRight,
  Webhook,
  LayoutDashboard,
  MessageSquarePlus,
} from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'

const NAV_ITEMS = [
  { label: 'Dashboard',    href: '/',                     icon: LayoutDashboard },
  { label: 'Workflows',    href: '/workflows',            icon: Workflow },
  { label: 'New with AI',  href: '/workflows/new',        icon: MessageSquarePlus },
  { label: 'Runs',         href: '/runs',                 icon: Play },
  { label: 'Schedules',    href: '/schedules',            icon: Calendar },
  { label: 'Webhooks',     href: '/settings/integrations', icon: Webhook },
  { label: 'Logs',         href: '/logs',                 icon: ScrollText },
  { label: 'Settings',     href: '/settings/profile',     icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const { isSidebarCollapsed, toggleSidebar } = useUIStore()

  return (
    <aside
      className={`
        flex flex-col border-r border-border bg-background transition-all duration-200
        ${isSidebarCollapsed ? 'w-12' : 'w-60'}
      `}
    >
      {/* Logo / brand */}
      <div className="flex h-14 items-center justify-between px-3 border-b border-border">
        {!isSidebarCollapsed && (
          <span className="font-semibold text-sm truncate">DK Workflow</span>
        )}
        <button
          onClick={toggleSidebar}
          className="ml-auto p-1 rounded hover:bg-muted transition-colors"
          aria-label="Toggle sidebar"
        >
          {isSidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 space-y-0.5 px-1.5">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              title={isSidebarCollapsed ? label : undefined}
              className={`
                flex items-center gap-3 rounded-md px-2 py-2 text-sm transition-colors
                ${active
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }
              `}
            >
              <Icon size={16} className="shrink-0" />
              {!isSidebarCollapsed && <span className="truncate">{label}</span>}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
