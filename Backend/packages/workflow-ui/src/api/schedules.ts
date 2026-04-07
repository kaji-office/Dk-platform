// ─────────────────────────────────────────────────────────────────────────────
// Schedules API — actual routes from openapi.yaml:
//   GET  /api/v1/workflows/{id}/schedules     → { schedules: [] }
//   POST /api/v1/workflows/{id}/schedules     → create
//   PATCH/DELETE /api/v1/schedules/{id}       → update/delete
// ─────────────────────────────────────────────────────────────────────────────

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { WorkflowSchedule, ScheduleCreateRequest, ApiResponse } from '@/types/api'

export const scheduleKeys = {
  all: ['schedules'] as const,
  byWorkflow: (workflowId: string) => [...scheduleKeys.all, 'workflow', workflowId] as const,
  detail: (id: string) => [...scheduleKeys.all, 'detail', id] as const,
}

export function useWorkflowSchedules(workflowId: string) {
  return useQuery({
    queryKey: scheduleKeys.byWorkflow(workflowId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<{ schedules: WorkflowSchedule[] }>>(
        `/api/v1/workflows/${workflowId}/schedules`,
      )
      return data.data.schedules
    },
    enabled: Boolean(workflowId),
  })
}

export function useCreateSchedule(workflowId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: ScheduleCreateRequest) => {
      const { data } = await apiClient.post<ApiResponse<WorkflowSchedule>>(
        `/api/v1/workflows/${workflowId}/schedules`,
        body,
      )
      return data.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scheduleKeys.byWorkflow(workflowId) })
    },
  })
}

export function useUpdateSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      ...body
    }: Partial<ScheduleCreateRequest> & { id: string; is_active?: boolean }) => {
      const { data } = await apiClient.patch<ApiResponse<WorkflowSchedule>>(
        `/api/v1/schedules/${id}`,
        body,
      )
      return data.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: scheduleKeys.all }),
  })
}

export function useDeleteSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/schedules/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: scheduleKeys.all }),
  })
}
