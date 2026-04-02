// ─────────────────────────────────────────────────────────────────────────────
// Workflows API — TanStack Query hooks for all workflow endpoints
// Endpoints: docs/frontend/handover.md §2 "Workflow CRUD" table
// ─────────────────────────────────────────────────────────────────────────────

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { Workflow, WorkflowSaveRequest, WorkflowDefinition, ApiResponse } from '@/types/api'

// ── Query keys (centralized to avoid typos) ───────────────────────────────────

export const workflowKeys = {
  all: ['workflows'] as const,
  list: () => [...workflowKeys.all, 'list'] as const,
  detail: (id: string) => [...workflowKeys.all, 'detail', id] as const,
}

// ── List workflows ────────────────────────────────────────────────────────────

export function useWorkflows() {
  return useQuery({
    queryKey: workflowKeys.list(),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Workflow[]>>('/api/v1/workflows')
      return data.data
    },
  })
}

// ── Get single workflow ───────────────────────────────────────────────────────

export function useWorkflow(id: string) {
  return useQuery({
    queryKey: workflowKeys.detail(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Workflow>>(`/api/v1/workflows/${id}`)
      return data.data
    },
    enabled: Boolean(id),
  })
}

// ── Create blank workflow ─────────────────────────────────────────────────────

export function useCreateWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description?: string }) => {
      const { data } = await apiClient.post<ApiResponse<Workflow>>('/api/v1/workflows', body)
      return data.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: workflowKeys.list() }),
  })
}

// ── Save (auto-save) workflow ─────────────────────────────────────────────────
// Body: WorkflowSaveRequest — flat fields, NOT wrapped in { workflow: }
// This is used by the debounced auto-save hook.

export function useSaveWorkflow(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: WorkflowSaveRequest) => {
      const { data } = await apiClient.put<ApiResponse<Workflow>>(
        `/api/v1/workflows/${id}`,
        body,
      )
      return data.data
    },
    onSuccess: (updated) => {
      qc.setQueryData(workflowKeys.detail(id), updated)
    },
  })
}

// ── Delete workflow ───────────────────────────────────────────────────────────

export function useDeleteWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/workflows/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: workflowKeys.list() }),
  })
}

// ── Trigger workflow execution ─────────────────────────────────────────────────

export function useTriggerWorkflow() {
  return useMutation({
    mutationFn: async ({
      workflowId,
      inputData = {},
    }: {
      workflowId: string
      inputData?: Record<string, unknown>
    }) => {
      const { data } = await apiClient.post<ApiResponse<{ run_id: string }>>(
        `/api/v1/workflows/${workflowId}/trigger`,
        { input_data: inputData },
      )
      return data.data
    },
  })
}

// ── Activate workflow (for scheduled/webhook triggers) ────────────────────────

export function useActivateWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<ApiResponse<Workflow>>(
        `/api/v1/workflows/${id}/activate`,
      )
      return data.data
    },
    onSuccess: (_, id) => qc.invalidateQueries({ queryKey: workflowKeys.detail(id) }),
  })
}
