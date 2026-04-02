// ─────────────────────────────────────────────────────────────────────────────
// Chat API — TanStack Query hooks for all chat endpoints
// Endpoints: docs/frontend/handover.md §2 "Chat" table
//
// Flow:
//  1. POST /chat/sessions             → creates session, returns session_id
//  2. POST /chat/sessions/{id}/message → send user message → phase + assistant reply
//  3. GET  /chat/sessions/{id}         → fetch full state (called after WS "response" event)
//  4. PUT  /chat/sessions/{id}/workflow → validate canvas edits against backend
// ─────────────────────────────────────────────────────────────────────────────

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { ChatSession, ChatMessageResponse, ApiResponse } from '@/types/chat'
import type { WorkflowDefinition } from '@/types/api'

// ── Query keys ────────────────────────────────────────────────────────────────

export const chatKeys = {
  all: ['chat'] as const,
  sessions: () => [...chatKeys.all, 'sessions'] as const,
  session: (id: string) => [...chatKeys.all, 'session', id] as const,
}

// ── List sessions ─────────────────────────────────────────────────────────────

export function useChatSessions() {
  return useQuery({
    queryKey: chatKeys.sessions(),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ChatSession[]>>(
        '/api/v1/chat/sessions',
      )
      return data.data
    },
  })
}

// ── Get single session (full message history + latest state) ──────────────────
// Called after WS emits "response" to fetch the rich payload (clarification,
// WorkflowDefinition, RequirementSpec) — WS only carries lightweight signals.

export function useChatSession(sessionId: string | null) {
  return useQuery({
    queryKey: chatKeys.session(sessionId ?? ''),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ChatMessageResponse>>(
        `/api/v1/chat/sessions/${sessionId}`,
      )
      return data.data
    },
    enabled: Boolean(sessionId),
    // Don't auto-refetch — triggered manually after WS events
    staleTime: Infinity,
  })
}

// ── Create session ────────────────────────────────────────────────────────────

export function useCreateChatSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<ApiResponse<{ session_id: string; phase: string }>>(
        '/api/v1/chat/sessions',
      )
      return data.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: chatKeys.sessions() }),
  })
}

// ── Send message ──────────────────────────────────────────────────────────────

export function useSendMessage(sessionId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (content: string) => {
      const { data } = await apiClient.post<ApiResponse<ChatMessageResponse>>(
        `/api/v1/chat/sessions/${sessionId}/message`,
        { content },
      )
      return data.data
    },
    onSuccess: (response) => {
      // Immediately update the session cache with the latest state
      qc.setQueryData(chatKeys.session(sessionId), response)
    },
  })
}

// ── Force DAG generation (EDITOR role) ────────────────────────────────────────

export function useForceGenerate(sessionId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<ApiResponse<ChatMessageResponse>>(
        `/api/v1/chat/sessions/${sessionId}/generate`,
      )
      return data.data
    },
    onSuccess: (response) => {
      qc.setQueryData(chatKeys.session(sessionId), response)
    },
  })
}

// ── Submit canvas edits for validation ───────────────────────────────────────
// Body: { workflow: WorkflowDefinition } — full replacement, NOT a diff

export function useUpdateChatWorkflow(sessionId: string) {
  return useMutation({
    mutationFn: async (workflow: WorkflowDefinition) => {
      const { data } = await apiClient.put<
        ApiResponse<{
          valid: boolean
          workflow: WorkflowDefinition
          validation_errors?: Array<{ code: string; message: string; node_id: string | null }>
          suggestions?: string[]
        }>
      >(`/api/v1/chat/sessions/${sessionId}/workflow`, { workflow })
      return data.data
    },
  })
}
