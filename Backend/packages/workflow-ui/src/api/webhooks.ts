// ─────────────────────────────────────────────────────────────────────────────
// Webhooks API — inbound webhook management
// Endpoints: docs/frontend/handover.md §2 "Inbound Webhooks" table
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
      const { data } = await apiClient.get<ApiResponse<InboundWebhook[]>>(
        '/api/v1/webhooks/inbound',
      )
      return data.data
    },
  })
}

export function useInboundWebhook(id: string) {
  return useQuery({
    queryKey: webhookKeys.detail(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<InboundWebhook>>(
        `/api/v1/webhooks/inbound/${id}`,
      )
      return data.data
    },
    enabled: Boolean(id),
  })
}

// ── Create — webhook_secret is returned ONCE and must be stored ───────────────

export function useCreateInboundWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: InboundWebhookCreate) => {
      const { data } = await apiClient.post<ApiResponse<InboundWebhook>>(
        '/api/v1/webhooks/inbound',
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
        `/api/v1/webhooks/inbound/${id}`,
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
      await apiClient.delete(`/api/v1/webhooks/inbound/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: webhookKeys.list() }),
  })
}
