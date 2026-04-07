// ─────────────────────────────────────────────────────────────────────────────
// Users API — profile + API key management
//   GET  /api/v1/users/me                  → User
//   PATCH /api/v1/users/me                 → User
//   GET  /api/v1/users/me/api-keys         → { api_keys: [] }
//   POST /api/v1/users/me/api-keys         → ApiKey (full key shown once)
//   DELETE /api/v1/users/me/api-keys/{id}  → 204
// ─────────────────────────────────────────────────────────────────────────────

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { User, ApiKey, ApiResponse } from '@/types/api'

export const userKeys = {
  me: ['users', 'me'] as const,
  apiKeys: ['users', 'me', 'api-keys'] as const,
}

export function useCurrentUser() {
  return useQuery({
    queryKey: userKeys.me,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<User>>('/api/v1/users/me')
      return data.data
    },
  })
}

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: Partial<Pick<User, 'name' | 'email'>>) => {
      const { data } = await apiClient.patch<ApiResponse<User>>('/api/v1/users/me', body)
      return data.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.me }),
  })
}

export function useApiKeys() {
  return useQuery({
    queryKey: userKeys.apiKeys,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<{ api_keys: ApiKey[] }>>(
        '/api/v1/users/me/api-keys',
      )
      return data.data.api_keys
    },
  })
}

// Returns full key string only once — caller must store it
export function useCreateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (name: string) => {
      const { data } = await apiClient.post<ApiResponse<ApiKey & { key: string }>>(
        '/api/v1/users/me/api-keys',
        { name },
      )
      return data.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.apiKeys }),
  })
}

export function useDeleteApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (keyId: string) => {
      await apiClient.delete(`/api/v1/users/me/api-keys/${keyId}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.apiKeys }),
  })
}
