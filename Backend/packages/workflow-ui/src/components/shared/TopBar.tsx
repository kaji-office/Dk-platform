'use client'

import { LogOut, User } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useLogout } from '@/api/auth'
import { useRouter } from 'next/navigation'

interface TopBarProps {
  title?: string
  actions?: React.ReactNode
}

export function TopBar({ title, actions }: TopBarProps) {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const logoutMutation = useLogout()
  const router = useRouter()

  async function handleLogout() {
    await logoutMutation.mutateAsync()
    logout()
    router.push('/login')
  }

  return (
    <header className="h-14 border-b border-border flex items-center justify-between px-4 bg-background shrink-0">
      <div className="flex items-center gap-2">
        {title && <h1 className="text-sm font-medium">{title}</h1>}
      </div>

      <div className="flex items-center gap-2">
        {actions}
        {/* Run status indicator populated by workflowStore */}
        <div className="flex items-center gap-3">
          {user && (
            <span className="text-xs text-muted-foreground hidden sm:block">
              {user.email}
            </span>
          )}
          <button
            onClick={handleLogout}
            className="p-1.5 rounded hover:bg-muted transition-colors"
            title="Logout"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </header>
  )
}
