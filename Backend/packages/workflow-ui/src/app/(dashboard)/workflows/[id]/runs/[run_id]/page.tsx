'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useExecution, useExecutionNodes, useExecutionLogs, usePollExecution, useCancelExecution } from '@/api/executions'
import { useExecutionWebSocket } from '@/hooks/useExecutionWebSocket'
import { NODE_STATUS_STYLES } from '@/stores/workflowStore'
import type { NodeStatus } from '@/types/api'
import { XCircle } from 'lucide-react'

export default function ExecutionDetailPage() {
  const { id: workflowId, run_id: runId } = useParams<{ id: string; run_id: string }>()

  const { data: run } = useExecution(runId)
  // nodeStates derived from run.node_states (embedded in run detail)
  const { data: nodeStates } = useExecutionNodes(runId)
  // logs endpoint may be unavailable — isError handled gracefully below
  const { data: logs, isError: logsError } = useExecutionLogs(runId)
  const cancelMutation = useCancelExecution()

  // Connect to WS for live updates; fallback polling handles WS unavailability
  const { disconnect } = useExecutionWebSocket(runId, {
    onTerminal: () => disconnect(),
  })

  // Polling fallback — refetchInterval stops automatically on terminal status
  usePollExecution(runId, {
    enabled: run?.status === 'RUNNING' || run?.status === 'PENDING',
    intervalMs: 3000,
  })

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <Link
          href={`/workflows/${workflowId}/runs`}
          className="text-xs text-muted-foreground hover:underline"
        >
          ← Run history
        </Link>
        <div className="flex items-center gap-3 mt-1">
          <h1 className="text-lg font-semibold font-mono">{runId}</h1>
          {run && <StatusBadge status={run.status} />}
          {run?.status === 'RUNNING' && (
            <button
              onClick={() => cancelMutation.mutate(runId)}
              className="flex items-center gap-1 text-xs text-destructive hover:underline"
            >
              <XCircle size={12} /> Cancel
            </button>
          )}
        </div>
      </div>

      {/* Node execution states */}
      <section>
        <h2 className="text-sm font-medium mb-2">Node Execution</h2>
        <div className="space-y-1.5">
          {(nodeStates ?? []).map((node) => {
            const styles = NODE_STATUS_STYLES[node.status as NodeStatus] ?? NODE_STATUS_STYLES.PENDING
            return (
              <div
                key={node.node_id}
                className={`flex items-center gap-3 rounded-md border px-3 py-2 ring-1 ${styles.ring} ${styles.opacity ?? ''}`}
              >
                <span className={`w-2 h-2 rounded-full shrink-0 ${styles.dot} ${styles.animate ?? ''}`} />
                <span className="font-mono text-xs flex-1 truncate">{node.node_id}</span>
                <span className="text-xs text-muted-foreground">{node.status}</span>
                {node.error && (
                  <span className="text-xs text-destructive truncate max-w-xs" title={node.error}>
                    {node.error}
                  </span>
                )}
              </div>
            )
          })}
          {(nodeStates?.length ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground">No node data yet.</p>
          )}
        </div>
      </section>

      {/* Execution logs */}
      <section>
        <h2 className="text-sm font-medium mb-2">Logs</h2>
        <div className="rounded-md border border-border bg-muted/30 p-3 font-mono text-xs space-y-0.5 max-h-96 overflow-auto">
          {logsError && (
            <span className="text-muted-foreground">Log streaming not available for this run.</span>
          )}
          {!logsError && (logs ?? []).map((log, i) => (
            <div
              key={i}
              className={`${
                log.level === 'ERROR' ? 'text-red-500' :
                log.level === 'WARN' ? 'text-yellow-600' : 'text-foreground'
              }`}
            >
              <span className="text-muted-foreground mr-2">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className="mr-2 font-semibold">[{log.level}]</span>
              {log.node_id && <span className="text-muted-foreground mr-2">{log.node_id}:</span>}
              {log.message}
            </div>
          ))}
          {!logsError && (logs?.length ?? 0) === 0 && (
            <span className="text-muted-foreground">No logs.</span>
          )}
        </div>
      </section>

      {/* Raw output */}
      {run?.output_data && (
        <section>
          <h2 className="text-sm font-medium mb-2">Output</h2>
          <pre className="rounded-md border border-border bg-muted/30 p-3 text-xs overflow-auto max-h-64">
            {JSON.stringify(run.output_data, null, 2)}
          </pre>
        </section>
      )}
    </div>
  )
}

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
