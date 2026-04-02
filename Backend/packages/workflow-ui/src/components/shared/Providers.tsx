// ─────────────────────────────────────────────────────────────────────────────
// Providers — wraps the entire app with QueryClient + rate-limit toast handler
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useUIStore } from '@/stores/uiStore'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: (failureCount, error: unknown) => {
              // Don't retry on 401/403/404
              const status = (error as { response?: { status?: number } })?.response?.status
              if (status && [401, 403, 404].includes(status)) return false
              return failureCount < 2
            },
          },
        },
      }),
  )

  const addToast = useUIStore((s) => s.addToast)

  // Handle rate-limit events emitted by the Axios interceptor
  useEffect(() => {
    const handler = (e: Event) => {
      const { retryAfter } = (e as CustomEvent<{ retryAfter: number }>).detail
      addToast({
        title: 'Rate limit reached',
        description: `Too many requests. Please wait ${retryAfter}s before retrying.`,
        variant: 'warning',
        durationMs: retryAfter * 1000,
      })
    }
    window.addEventListener('api:rate-limit', handler)
    return () => window.removeEventListener('api:rate-limit', handler)
  }, [addToast])

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
