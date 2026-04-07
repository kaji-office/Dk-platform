// ─────────────────────────────────────────────────────────────────────────────
// Webhooks API — actual routes from openapi.yaml:
//   GET  /api/v1/webhooks                    → { webhooks: [] }
//   POST /api/v1/webhooks                    → create (returns secret once)
//   GET  /api/v1/webhooks/{id}               → detail
//   PATCH/DELETE /api/v1/webhooks/{id}       → update/delete
//   POST /api/v1/webhooks/inbound/{workflow_id} → external trigger (not called from UI)
// ─────────────────────────────────────────────────────────────────────────────

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { InboundWebhook, InboundWebhookCreate, ApiResponse } from '@/types/api'

export const webhookKeys = {
  all: ['webhooks'] as const,
  list: () => [...webhookKeys.all, 'list'] as const,
  detail: (id: string) => [...webhookKeys.all, 'detail', id] as const,
}

export function useInboundWebhooks() {
  return useQuery({
    queryKey: webhookKeys.list(),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<{ webhooks: InboundWebhook[] }>>(
        '/api/v1/webhooks',
      )
      return data.data.webhooks
    },
  })
}

export function useInboundWebhook(id: string) {
  return useQuery({
    queryKey: webhookKeys.detail(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<InboundWebhook>>(
        `/api/v1/webhooks/${id}`,
      )
      return data.data
    },
    enabled: Boolean(id),
  })
}

// ── Create — `secret` is returned ONCE and must be stored ────────────────────

export function useCreateInboundWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: InboundWebhookCreate) => {
      const { data } = await apiClient.post<ApiResponse<InboundWebhook>>(
        '/api/v1/webhooks',
        body,
      )
      return data.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: webhookKeys.list() }),
  })
}

export function useUpdateInboundWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: Partial<InboundWebhookCreate> & { id: string }) => {
      const { data } = await apiClient.patch<ApiResponse<InboundWebhook>>(
        `/api/v1/webhooks/${id}`,
        body,
      )
      return data.data
    },
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: webhookKeys.detail(id) })
      qc.invalidateQueries({ queryKey: webhookKeys.list() })
    },
  })
}

export function useDeleteInboundWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/webhooks/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: webhookKeys.list() }),
  })
}
