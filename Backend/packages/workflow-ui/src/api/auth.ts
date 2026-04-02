// ─────────────────────────────────────────────────────────────────────────────
// Auth API — TanStack Query mutations for all auth endpoints
// Endpoints: docs/frontend/handover.md §2 Auth table
// ─────────────────────────────────────────────────────────────────────────────

import { useMutation } from '@tanstack/react-query'
import { apiClient } from './client'
import type {
  RegisterRequest,
  LoginRequest,
  AuthTokens,
  ApiResponse,
} from '@/types/api'

// ── Register ──────────────────────────────────────────────────────────────────

export function useRegister() {
  return useMutation({
    mutationFn: async (body: RegisterRequest) => {
      const { data } = await apiClient.post<ApiResponse<AuthTokens>>(
        '/api/v1/auth/register',
        body,
      )
      return data.data
    },
  })
}

// ── Login ─────────────────────────────────────────────────────────────────────

export function useLogin() {
  return useMutation({
    mutationFn: async (body: LoginRequest) => {
      const { data } = await apiClient.post<ApiResponse<AuthTokens & { user_id: string; tenant_id: string }>>(
        '/api/v1/auth/login',
        body,
      )
      return data.data
    },
  })
}

// ── Logout ────────────────────────────────────────────────────────────────────

export function useLogout() {
  return useMutation({
    mutationFn: async () => {
      await apiClient.post('/api/v1/auth/logout')
    },
  })
}

// ── Verify email (token from link) ───────────────────────────────────────────

export function useVerifyEmail() {
  return useMutation({
    mutationFn: async (token: string) => {
      await apiClient.post('/api/v1/auth/verify-email', { token })
    },
  })
}

// ── Password reset request ────────────────────────────────────────────────────
// Always shows "email sent" — server returns 204 regardless to prevent enumeration

export function usePasswordResetRequest() {
  return useMutation({
    mutationFn: async (email: string) => {
      await apiClient.post('/api/v1/auth/password/reset-request', { email })
    },
  })
}

// ── Password reset (with token from email link) ───────────────────────────────

export function usePasswordReset() {
  return useMutation({
    mutationFn: async (body: { token: string; new_password: string }) => {
      await apiClient.post('/api/v1/auth/password/reset', body)
    },
  })
}
