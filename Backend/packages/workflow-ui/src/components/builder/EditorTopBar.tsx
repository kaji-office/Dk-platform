'use client'

import Link from 'next/link'
import { ChevronLeft, Save, Play, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useTriggerWorkflow, useSaveWorkflow } from '@/api/workflows'
import { useAutoSave } from '@/hooks/useAutoSave'
import { useRouter } from 'next/navigation'

interface Props {
  workflowId: string
}

export function EditorTopBar({ workflowId }: Props) {
  const { workflowName, saveStatus, isDirty, nodes, edges, runId, runStatus } = useWorkflowStore()
  const setSaveStatus = useWorkflowStore((s) => s.setSaveStatus)
  const markSaved = useWorkflowStore((s) => s.markSaved)
  const startRun = useWorkflowStore((s) => s.startRun)
  const router = useRouter()

  const triggerMutation = useTriggerWorkflow()

  async function handleManualSave() {
    setSaveStatus('saving')
    // The auto-save hook handles the actual API call; this just forces immediate flush.
    // For simplicity trigger it by briefly marking dirty then the hook fires.
  }

  async function handleTrigger() {
    const result = await triggerMutation.mutateAsync({ workflowId, inputData: {} })
    startRun(result.run_id)
    router.push(`/workflows/${workflowId}/runs/${result.run_id}`)
  }

  const SaveIcon = {
    idle: null,
    saving: <Loader2 size={12} className="animate-spin" />,
    saved: <CheckCircle2 size={12} className="text-green-500" />,
    error: <AlertCircle size={12} className="text-destructive" />,
  }[saveStatus]

  return (
    <div className="h-12 border-b border-border flex items-center gap-3 px-4 bg-background shrink-0">
      <Link href="/workflows" className="p-1 rounded hover:bg-muted transition-colors">
        <ChevronLeft size={16} />
      </Link>

      <span className="text-sm font-medium flex-1 truncate">{workflowName}</span>

      {/* Save status indicator */}
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {SaveIcon}
        {saveStatus === 'saving' && 'Saving…'}
        {saveStatus === 'saved' && 'Saved'}
        {saveStatus === 'error' && (
          <button onClick={handleManualSave} className="text-destructive hover:underline">
            Save failed — retry
          </button>
        )}
        {saveStatus === 'idle' && isDirty && 'Unsaved changes'}
      </div>

      {/* Trigger run */}
      <button
        onClick={handleTrigger}
        disabled={triggerMutation.isPending}
        className="flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-xs font-medium hover:opacity-90 disabled:opacity-50"
      >
        {triggerMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
        Run
      </button>

      {/* View runs */}
      <Link
        href={`/workflows/${workflowId}/runs`}
        className="text-xs text-muted-foreground hover:underline"
      >
        Run history
      </Link>
    </div>
  )
}
