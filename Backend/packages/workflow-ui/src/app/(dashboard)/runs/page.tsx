'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useExecutions } from '@/api/executions'
import { useWorkflows, useTriggerWorkflow } from '@/api/workflows'
import { useUIStore } from '@/stores/uiStore'
import { Play } from 'lucide-react'

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    SUCCESS: 'bg-green-100 text-green-700',
    FAILED: 'bg-red-100 text-red-700',
    RUNNING: 'bg-blue-100 text-blue-700 animate-pulse',
    PENDING: 'bg-gray-100 text-gray-600',
    CANCELLED: 'bg-yellow-100 text-yellow-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}

export default function AllRunsPage() {
  const { data: runs, isLoading } = useExecutions()
  const { data: workflows } = useWorkflows()
  const triggerMutation = useTriggerWorkflow()
  const addToast = useUIStore((s) => s.addToast)

  const [selectedWorkflowId, setSelectedWorkflowId] = useState('')

  function handleTrigger() {
    if (!selectedWorkflowId) return
    triggerMutation.mutate(
      { workflowId: selectedWorkflowId },
      {
        onSuccess: (data) => {
          addToast({
            title: 'Run started',
            description: `Run ID: ${data.run_id}`,
            variant: 'default',
          })
        },
        onError: () => addToast({ title: 'Failed to start run', variant: 'destructive' }),
      },
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-lg font-semibold">Runs</h1>

      {/* Trigger panel */}
      <section className="rounded-lg border border-border p-4 space-y-3">
        <h2 className="text-sm font-medium">Trigger a New Run</h2>
        <div className="flex items-center gap-3">
          <select
            value={selectedWorkflowId}
            onChange={(e) => setSelectedWorkflowId(e.target.value)}
            className="flex-1 max-w-xs rounded-md border border-input px-3 py-1.5 text-sm"
          >
            <option value="">Select a workflow…</option>
            {(workflows ?? []).map((wf) => (
              <option key={wf.id} value={wf.id}>
                {wf.name}
              </option>
            ))}
          </select>
          <button
            onClick={handleTrigger}
            disabled={!selectedWorkflowId || triggerMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm disabled:opacity-50"
          >
            <Play size={13} />
            {triggerMutation.isPending ? 'Starting…' : 'Run now'}
          </button>
        </div>
        {(workflows?.length ?? 0) === 0 && (
          <p className="text-xs text-muted-foreground">
            No workflows yet.{' '}
            <Link href="/workflows/new" className="underline">
              Create one with AI
            </Link>
          </p>
        )}
      </section>

      {/* Run history */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium">Run History</h2>
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {(runs ?? []).map((run) => (
          <Link
            key={run.run_id}
            href={`/workflows/${run.workflow_id}/runs/${run.run_id}`}
            className="flex items-center justify-between rounded-lg border border-border px-4 py-3 hover:bg-muted transition-colors"
          >
            <div>
              <p className="font-mono text-xs">{run.run_id}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Workflow: <span className="font-mono">{run.workflow_id}</span>
                {' · '}
                {new Date(run.started_at).toLocaleString()}
              </p>
            </div>
            <StatusBadge status={run.status} />
          </Link>
        ))}
        {!isLoading && (runs?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No runs yet. Trigger one above.</p>
        )}
      </section>
    </div>
  )
}
