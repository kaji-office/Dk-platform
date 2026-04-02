// ─────────────────────────────────────────────────────────────────────────────
// Auth store — user identity + access token (React memory only)
//
// Security: access token stored in React memory, NEVER in localStorage/cookies.
// Refresh token lives in an HttpOnly cookie — invisible to JS.
// On page reload the token is gone; refresh endpoint restores it using the cookie.
// ─────────────────────────────────────────────────────────────────────────────

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { User } from '@/types/api'

interface AuthState {
  // In-memory access token (not persisted)
  _accessToken: string | null
  _refreshToken: string | null

  user: User | null
  isAuthenticated: boolean

  // Called by login / register mutations
  setAuth: (token: string, refreshToken: string, user: User) => void

  // Called by token refresh interceptor
  setAccessToken: (token: string) => void
  getAccessToken: () => string | null
  getRefreshToken: () => string | null

  // Called on logout or refresh failure
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  devtools(
    (set, get) => ({
      _accessToken: null,
      _refreshToken: null,
      user: null,
      isAuthenticated: false,

      setAuth: (token, refreshToken, user) =>
        set({ _accessToken: token, _refreshToken: refreshToken, user, isAuthenticated: true }, false, 'auth/setAuth'),

      setAccessToken: (token) =>
        set({ _accessToken: token }, false, 'auth/setAccessToken'),

      getAccessToken: () => get()._accessToken,
      getRefreshToken: () => get()._refreshToken,

      logout: () =>
        set(
          { _accessToken: null, _refreshToken: null, user: null, isAuthenticated: false },
          false,
          'auth/logout',
        ),
    }),
    { name: 'AuthStore' },
  ),
)
