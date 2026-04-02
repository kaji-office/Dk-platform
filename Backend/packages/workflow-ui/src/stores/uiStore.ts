// ─────────────────────────────────────────────────────────────────────────────
// UI store — sidebar, theme, toast
// ─────────────────────────────────────────────────────────────────────────────

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

export interface Toast {
  id: string
  title: string
  description?: string
  variant?: 'default' | 'destructive' | 'warning'
  durationMs?: number
}

interface UIStore {
  isSidebarCollapsed: boolean
  theme: 'light' | 'dark' | 'system'
  toasts: Toast[]

  toggleSidebar: () => void
  setSidebarCollapsed: (v: boolean) => void
  setTheme: (theme: UIStore['theme']) => void
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

export const useUIStore = create<UIStore>()(
  devtools(
    persist(
      (set) => ({
        isSidebarCollapsed: false,
        theme: 'system',
        toasts: [],

        toggleSidebar: () =>
          set((s) => ({ isSidebarCollapsed: !s.isSidebarCollapsed }), false, 'ui/toggleSidebar'),

        setSidebarCollapsed: (v) =>
          set({ isSidebarCollapsed: v }, false, 'ui/setSidebarCollapsed'),

        setTheme: (theme) =>
          set({ theme }, false, 'ui/setTheme'),

        addToast: (toast) =>
          set(
            (s) => ({
              toasts: [
                ...s.toasts,
                { ...toast, id: `toast_${Date.now()}_${Math.random()}` },
              ],
            }),
            false,
            'ui/addToast',
          ),

        removeToast: (id) =>
          set(
            (s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }),
            false,
            'ui/removeToast',
          ),
      }),
      {
        name: 'ui-preferences',
        partialize: (s) => ({ isSidebarCollapsed: s.isSidebarCollapsed, theme: s.theme }),
      },
    ),
    { name: 'UIStore' },
  ),
)
