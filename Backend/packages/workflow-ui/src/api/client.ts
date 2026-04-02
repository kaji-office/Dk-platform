// ─────────────────────────────────────────────────────────────────────────────
// Axios client — centralized instance with auth + error interceptors
//
// Auth strategy (from docs/frontend/overview.md §6):
//   - Access token (15 min): stored in React memory via authStore — NEVER localStorage
//   - Refresh token (7 days): HttpOnly cookie — invisible to JS, sent automatically
//   - On 401: interceptor calls POST /auth/token/refresh → retries original request
//   - On 429: shows toast and does NOT auto-retry (per handover doc §12)
// ─────────────────────────────────────────────────────────────────────────────--

import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,         // sends HttpOnly refresh-token cookie automatically
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// ── Request interceptor — attach access token ─────────────────────────────────

apiClient.interceptors.request.use((config) => {
  // Access token lives in authStore (React memory only).
  // We import lazily to avoid circular dependency at module load time.
  const { getAccessToken } = require('@/stores/authStore').useAuthStore.getState()
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor — handle 401, 429, and error normalization ───────────

let isRefreshing = false
// Queue of callbacks waiting for the new token after a refresh
let refreshQueue: Array<(token: string) => void> = []

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retried?: boolean }

    // 429 — Rate limit exceeded: show toast, do NOT auto-retry
    if (error.response?.status === 429) {
      const retryAfter = error.response.headers['retry-after'] ?? '60'
      // Dispatch a custom event so toast can be shown from any component
      if (typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('api:rate-limit', { detail: { retryAfter: Number(retryAfter) } }),
        )
      }
      return Promise.reject(error)
    }

    // 401 — Unauthorized: attempt token refresh (once per request)
    if (error.response?.status === 401 && !originalRequest._retried) {
      originalRequest._retried = true

      if (isRefreshing) {
        // Another request is already refreshing — queue this one
        return new Promise((resolve, reject) => {
          refreshQueue.push((newToken) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            resolve(apiClient(originalRequest))
          })
          // Store reject in case refresh fails (not used here but could be extended)
          void reject
        })
      }

      isRefreshing = true
      try {
        // Read stored refresh token and send in body (backend requires it)
        const { getRefreshToken, setAccessToken } = require('@/stores/authStore').useAuthStore.getState()
        const storedRefreshToken = getRefreshToken()

        if (!storedRefreshToken) {
          throw new Error('No refresh token available')
        }

        // POST /auth/token/refresh — send refresh_token in body
        const { data } = await apiClient.post<{ data: { access_token: string } }>(
          '/api/v1/auth/token/refresh',
          { refresh_token: storedRefreshToken },
        )
        const newToken = data.data.access_token

        // Store new token in authStore
        setAccessToken(newToken)

        // Flush queued requests
        refreshQueue.forEach((cb) => cb(newToken))
        refreshQueue = []

        // Retry original request
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return apiClient(originalRequest)
      } catch (refreshError) {
        // Refresh failed — session expired, force logout
        refreshQueue = []
        const { logout } = require('@/stores/authStore').useAuthStore.getState()
        logout()
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  },
)

// ── WebSocket URL helper ───────────────────────────────────────────────────────
// Browsers cannot set Authorization headers on WebSocket connections.
// Token is passed as query param: ?token=<jwt>

export function buildWsUrl(path: string): string {
  const wsBase =
    process.env.NEXT_PUBLIC_WS_URL ??
    BASE_URL.replace(/^http/, 'ws')
  const { getAccessToken } = require('@/stores/authStore').useAuthStore.getState()
  const token = getAccessToken()
  const sep = path.includes('?') ? '&' : '?'
  return `${wsBase}${path}${token ? `${sep}token=${token}` : ''}`
}
