// ─────────────────────────────────────────────────────────────────────────────
// Executions API — TanStack Query hooks + polling for Celery async jobs
//
// Celery job flow:
//   1. POST /workflows/{id}/trigger  → 202 { run_id, status: 'queued' }
//   2. Connect to WS /ws/executions/{run_id}?token=<jwt> for live events
//   3. Poll GET /executions/{run_id} as fallback (node_states is embedded)
//   4. GET /executions/{run_id}/logs  → { logs: [], run_id }
//
// NOTE: /executions/{run_id}/nodes returns 500 in current backend.
//       Use run.node_states from the run detail instead.
// ─────────────────────────────────────────────────────────────────────────────

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { ExecutionRun, ExecutionLog, NodeExecution, ApiResponse } from '@/types/api'

// ── Query keys ────────────────────────────────────────────────────────────────

export const executionKeys = {
  all: ['executions'] as const,
  list: (filters?: Record<string, string>) =>
    [...executionKeys.all, 'list', filters ?? {}] as const,
  detail: (runId: string) => [...executionKeys.all, 'detail', runId] as const,
  logs: (runId: string) => [...executionKeys.all, 'logs', runId] as const,
}

// ── List runs ─────────────────────────────────────────────────────────────────

export function useExecutions(filters?: { workflow_id?: string; status?: string }) {
  return useQuery({
    queryKey: executionKeys.list(filters),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<{ executions: ExecutionRun[] }>>(
        '/api/v1/executions',
        { params: filters },
      )
      return data.data.executions
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

export function usePollExecution(
  runId: string,
  { enabled = true, intervalMs = 2000 }: { enabled?: boolean; intervalMs?: number } = {},
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
      const terminal = ['SUCCESS', 'FAILED', 'CANCELLED']
      return terminal.includes(status ?? '') ? false : intervalMs
    },
  })
}

// ── Node states — derived from embedded run.node_states ───────────────────────
// The /executions/{run_id}/nodes endpoint is unreliable; use run detail instead.

export function useExecutionNodes(runId: string) {
  return useQuery({
    queryKey: executionKeys.detail(runId),  // same cache key as run detail
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ExecutionRun>>(
        `/api/v1/executions/${runId}`,
      )
      return data.data
    },
    enabled: Boolean(runId),
    select: (run) =>
      // Convert node_states Record → NodeExecution[]
      Object.entries(run.node_states ?? {}).map(([node_id, state]) => ({
        node_id,
        status: state.status,
        started_at: state.started_at,
        ended_at: state.ended_at,
        error: state.error,
        outputs: state.outputs,
      } satisfies NodeExecution)),
  })
}

// ── Execution logs ────────────────────────────────────────────────────────────

export function useExecutionLogs(runId: string) {
  return useQuery({
    queryKey: executionKeys.logs(runId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<{ logs: ExecutionLog[]; run_id: string }>>(
        `/api/v1/executions/${runId}/logs`,
      )
      return data.data.logs
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
