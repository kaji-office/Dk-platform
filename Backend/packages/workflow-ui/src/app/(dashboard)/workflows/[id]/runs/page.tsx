'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useExecutions, useCancelExecution } from '@/api/executions'
import { useTriggerWorkflow } from '@/api/workflows'
import { Play, XCircle } from 'lucide-react'

export default function WorkflowRunsPage() {
  const { id: workflowId } = useParams<{ id: string }>()
  const { data: runs, isLoading } = useExecutions({ workflow_id: workflowId })
  const cancelMutation = useCancelExecution()
  const triggerMutation = useTriggerWorkflow()

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <Link href={`/workflows/${workflowId}`} className="text-xs text-muted-foreground hover:underline">
            ← Back to editor
          </Link>
          <h1 className="text-lg font-semibold mt-1">Run History</h1>
        </div>
        <button
          onClick={() => triggerMutation.mutate({ workflowId })}
          disabled={triggerMutation.isPending}
          className="flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          <Play size={14} /> Run now
        </button>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      <div className="space-y-2">
        {(runs ?? []).map((run) => (
          <div
            key={run.run_id}
            className="flex items-center justify-between rounded-lg border border-border px-4 py-3"
          >
            <div>
              <Link
                href={`/workflows/${workflowId}/runs/${run.run_id}`}
                className="font-mono text-xs hover:underline"
              >
                {run.run_id}
              </Link>
              <p className="text-xs text-muted-foreground mt-0.5">
                {new Date(run.started_at).toLocaleString()}
                {run.ended_at && ` · ${Math.round((new Date(run.ended_at).getTime() - new Date(run.started_at).getTime()) / 1000)}s`}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <StatusBadge status={run.status} />
              {run.status === 'RUNNING' && (
                <button
                  onClick={() => cancelMutation.mutate(run.run_id)}
                  title="Cancel"
                  className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-destructive"
                >
                  <XCircle size={14} />
                </button>
              )}
            </div>
          </div>
        ))}
        {!isLoading && (runs?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No runs yet.</p>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    SUCCESS: 'bg-green-100 text-green-700',
    FAILED: 'bg-red-100 text-red-700',
    RUNNING: 'bg-blue-100 text-blue-700',
    PENDING: 'bg-gray-100 text-gray-600',
    CANCELLED: 'bg-yellow-100 text-yellow-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}
