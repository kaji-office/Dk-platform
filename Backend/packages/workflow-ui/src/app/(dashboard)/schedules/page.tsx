'use client'

import { useState } from 'react'
import { useWorkflows } from '@/api/workflows'
import { useWorkflowSchedules, useUpdateSchedule, useDeleteSchedule } from '@/api/schedules'
import { Trash2, Power } from 'lucide-react'

export default function SchedulesPage() {
  const { data: workflows } = useWorkflows()
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('')
  const { data: schedules, isLoading } = useWorkflowSchedules(selectedWorkflowId)
  const updateMutation = useUpdateSchedule()
  const deleteMutation = useDeleteSchedule()

  return (
    <div className="space-y-4 max-w-4xl">
      <h1 className="text-lg font-semibold">Schedules</h1>

      {/* Workflow selector */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-muted-foreground shrink-0">Workflow:</label>
        <select
          value={selectedWorkflowId}
          onChange={(e) => setSelectedWorkflowId(e.target.value)}
          className="rounded-md border border-input px-3 py-1.5 text-sm flex-1 max-w-xs"
        >
          <option value="">Select a workflow…</option>
          {(workflows ?? []).map((wf) => (
            <option key={wf.id} value={wf.id}>{wf.name}</option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {selectedWorkflowId && (
        <div className="space-y-2">
          {(schedules ?? []).map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between rounded-lg border border-border px-4 py-3"
            >
              <div>
                <p className="font-mono text-sm">{s.cron_expression}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {s.next_fire_at
                    ? `Next: ${new Date(s.next_fire_at).toLocaleString()}`
                    : 'Not scheduled'}
                  {s.timezone ? ` (${s.timezone})` : ''}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded ${s.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {s.is_active ? 'Active' : 'Paused'}
                </span>
                <button
                  onClick={() => updateMutation.mutate({ id: s.id, is_active: !s.is_active })}
                  title={s.is_active ? 'Pause' : 'Activate'}
                  className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground"
                >
                  <Power size={14} />
                </button>
                <button
                  onClick={() => { if (confirm('Delete schedule?')) deleteMutation.mutate(s.id) }}
                  className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-destructive"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
          {!isLoading && (schedules?.length ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground">
              No schedules for this workflow.{' '}
              <span className="text-foreground">Open the workflow editor to add one.</span>
            </p>
          )}
        </div>
      )}
    </div>
  )
}
