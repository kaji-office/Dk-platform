// ─────────────────────────────────────────────────────────────────────────────
// Executions API — TanStack Query hooks + polling for Celery async jobs
//
// Celery job flow:
//   1. POST /workflows/{id}/trigger  → returns { run_id }
//   2. Connect to WS /ws/executions/{run_id}?token=<jwt> for live events
//   3. Poll GET /executions/{run_id} as fallback when WS is unavailable
//   4. GET /executions/{run_id}/nodes for per-node states
//   5. GET /executions/{run_id}/logs for log stream
// ─────────────────────────────────────────────────────────────────────────────

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { ExecutionRun, NodeExecution, ExecutionLog, ApiResponse } from '@/types/api'

// ── Query keys ────────────────────────────────────────────────────────────────

export const executionKeys = {
  all: ['executions'] as const,
  list: (filters?: Record<string, string>) =>
    [...executionKeys.all, 'list', filters ?? {}] as const,
  detail: (runId: string) => [...executionKeys.all, 'detail', runId] as const,
  nodes: (runId: string) => [...executionKeys.all, 'nodes', runId] as const,
  logs: (runId: string) => [...executionKeys.all, 'logs', runId] as const,
}

// ── List runs ─────────────────────────────────────────────────────────────────

export function useExecutions(filters?: { workflow_id?: string; status?: string }) {
  return useQuery({
    queryKey: executionKeys.list(filters),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ExecutionRun[]>>('/api/v1/executions', {
        params: filters,
      })
      return data.data
    },
  })
}

// ── Get single run ────────────────────────────────────────────────────────────

export function useExecution(runId: string) {
  return useQuery({
    queryKey: executionKeys.detail(runId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ExecutionRun>>(
        `/api/v1/executions/${runId}`,
      )
      return data.data
    },
    enabled: Boolean(runId),
  })
}

// ── Poll active run — fallback when WebSocket is unavailable ──────────────────
// Refetches every `intervalMs` while run is in a non-terminal state.
// Stop polling by setting enabled=false once WebSocket connects.

export function usePollExecution(
  runId: string,
  {
    enabled = true,
    intervalMs = 2000,
  }: { enabled?: boolean; intervalMs?: number } = {},
) {
  return useQuery({
    queryKey: executionKeys.detail(runId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ExecutionRun>>(
        `/api/v1/executions/${runId}`,
      )
      return data.data
    },
    enabled: Boolean(runId) && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      // Stop polling when run reaches a terminal state
      const terminal = ['SUCCESS', 'FAILED', 'CANCELLED']
      return terminal.includes(status ?? '') ? false : intervalMs
    },
  })
}

// ── Per-node execution states ─────────────────────────────────────────────────

export function useExecutionNodes(runId: string) {
  return useQuery({
    queryKey: executionKeys.nodes(runId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<NodeExecution[]>>(
        `/api/v1/executions/${runId}/nodes`,
      )
      return data.data
    },
    enabled: Boolean(runId),
  })
}

// ── Execution logs ────────────────────────────────────────────────────────────

export function useExecutionLogs(runId: string) {
  return useQuery({
    queryKey: executionKeys.logs(runId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ExecutionLog[]>>(
        `/api/v1/executions/${runId}/logs`,
      )
      return data.data
    },
    enabled: Boolean(runId),
  })
}

// ── Cancel run ────────────────────────────────────────────────────────────────

export function useCancelExecution() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (runId: string) => {
      await apiClient.post(`/api/v1/executions/${runId}/cancel`)
    },
    onSuccess: (_, runId) =>
      qc.invalidateQueries({ queryKey: executionKeys.detail(runId) }),
  })
}
