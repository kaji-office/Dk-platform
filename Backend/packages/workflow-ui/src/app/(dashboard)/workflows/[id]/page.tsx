'use client'

import { useEffect } from 'react'
import { useParams } from 'next/navigation'
import { useWorkflow } from '@/api/workflows'
import { useWorkflowStore } from '@/stores/workflowStore'
import { WorkflowCanvas } from '@/components/builder/WorkflowCanvas'
import { NodePalette } from '@/components/builder/NodePalette'
import { NodeConfigPanel } from '@/components/builder/NodeConfigPanel'
import { EditorTopBar } from '@/components/builder/EditorTopBar'
import { useAutoSave } from '@/hooks/useAutoSave'

export default function WorkflowEditorPage() {
  const { id } = useParams<{ id: string }>()
  const { data: workflow, isLoading } = useWorkflow(id)
  const loadFromDefinition = useWorkflowStore((s) => s.loadFromDefinition)
  const setWorkflowMeta = useWorkflowStore((s) => s.setWorkflowMeta)
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId)

  // Auto-save debounced 2s
  useAutoSave()

  // Load workflow definition into canvas on mount
  useEffect(() => {
    if (workflow) {
      loadFromDefinition(workflow.definition, workflow.id)
      setWorkflowMeta(workflow.id, workflow.name)
    }
  }, [workflow, loadFromDefinition, setWorkflowMeta])

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading workflow…</p>
      </div>
    )
  }

  return (
    // Remove default dashboard padding for full-height canvas editor
    <div className="absolute inset-0 flex flex-col">
      <EditorTopBar workflowId={id} />

      {/* Three-panel layout: NodePalette | Canvas | ConfigPanel */}
      <div className="flex flex-1 min-h-0">
        <NodePalette />
        <WorkflowCanvas />
        {selectedNodeId && <NodeConfigPanel nodeId={selectedNodeId} />}
      </div>
    </div>
  )
}
