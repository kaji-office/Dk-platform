'use client'

import Link from 'next/link'
import { useWorkflows, useDeleteWorkflow } from '@/api/workflows'
import { Plus, Trash2, ExternalLink, Play } from 'lucide-react'
import { useTriggerWorkflow } from '@/api/workflows'

export default function WorkflowsPage() {
  const { data: workflows, isLoading } = useWorkflows()
  const deleteMutation = useDeleteWorkflow()
  const triggerMutation = useTriggerWorkflow()

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Workflows</h1>
        <Link
          href="/workflows/new"
          className="flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:opacity-90"
        >
          <Plus size={14} /> New Workflow
        </Link>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      <div className="space-y-2">
        {(workflows ?? []).map((wf) => (
          <div
            key={wf.id}
            className="flex items-center justify-between rounded-lg border border-border px-4 py-3"
          >
            <div className="min-w-0">
              <Link
                href={`/workflows/${wf.id}`}
                className="font-medium text-sm hover:underline truncate block"
              >
                {wf.name}
              </Link>
              {wf.description && (
                <p className="text-xs text-muted-foreground truncate">{wf.description}</p>
              )}
            </div>

            <div className="flex items-center gap-2 ml-4 shrink-0">
              {/* Quick-trigger run */}
              <button
                onClick={() => triggerMutation.mutate({ workflowId: wf.id })}
                disabled={triggerMutation.isPending}
                title="Trigger run"
                className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
              >
                <Play size={14} />
              </button>

              {/* Open in editor */}
              <Link
                href={`/workflows/${wf.id}`}
                title="Open editor"
                className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground"
              >
                <ExternalLink size={14} />
              </Link>

              {/* Delete */}
              <button
                onClick={() => {
                  if (confirm('Delete this workflow?')) {
                    deleteMutation.mutate(wf.id)
                  }
                }}
                title="Delete"
                className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-destructive"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}

        {!isLoading && (workflows?.length ?? 0) === 0 && (
          <div className="text-center py-12 text-sm text-muted-foreground">
            No workflows yet.{' '}
            <Link href="/workflows/new" className="hover:underline text-foreground">
              Create your first one
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
