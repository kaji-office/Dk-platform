'use client'

import Link from 'next/link'
import { useExecutions } from '@/api/executions'

export default function AllRunsPage() {
  const { data: runs, isLoading } = useExecutions()

  return (
    <div className="space-y-4 max-w-4xl">
      <h1 className="text-lg font-semibold">All Runs</h1>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      <div className="space-y-2">
        {(runs ?? []).map((run) => (
          <Link
            key={run.run_id}
            href={`/workflows/${run.workflow_id}/runs/${run.run_id}`}
            className="flex items-center justify-between rounded-lg border border-border px-4 py-3 hover:bg-muted transition-colors"
          >
            <div>
              <p className="font-mono text-xs">{run.run_id}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Workflow: {run.workflow_id} · {new Date(run.started_at).toLocaleString()}
              </p>
            </div>
            <StatusBadge status={run.status} />
          </Link>
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
