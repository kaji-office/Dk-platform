// ─────────────────────────────────────────────────────────────────────────────
// Schedules API — cron-based workflow scheduling
// ─────────────────────────────────────────────────────────────────────────────

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { WorkflowSchedule, ScheduleCreateRequest, ApiResponse } from '@/types/api'

export const scheduleKeys = {
  all: ['schedules'] as const,
  list: () => [...scheduleKeys.all, 'list'] as const,
  detail: (id: string) => [...scheduleKeys.all, 'detail', id] as const,
  byWorkflow: (workflowId: string) => [...scheduleKeys.all, 'workflow', workflowId] as const,
}

export function useSchedules() {
  return useQuery({
    queryKey: scheduleKeys.list(),
    queryFn: async () => {
      // Backend returns { schedules: WorkflowSchedule[] }
      const { data } = await apiClient.get<{ schedules: WorkflowSchedule[] }>(
        '/api/v1/schedules',
      )
      return data.schedules ?? []
    },
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
      qc.invalidateQueries({ queryKey: scheduleKeys.list() })
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
    onSuccess: () => qc.invalidateQueries({ queryKey: scheduleKeys.list() }),
  })
}

export function useDeleteSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/schedules/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: scheduleKeys.list() }),
  })
}
