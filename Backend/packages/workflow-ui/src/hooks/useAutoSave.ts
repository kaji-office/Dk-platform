// ─────────────────────────────────────────────────────────────────────────────
// useAutoSave — debounced workflow save
//
// Strategy (from docs/frontend/overview.md §9):
//   - Any canvas change: isDirty = true
//   - Debounce 2000ms
//   - PUT /api/v1/workflows/{id}  with full definition
//   - On success: saveStatus = 'saved', isDirty = false
//   - On failure: saveStatus = 'error', show toast (manual save available)
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { useEffect, useRef } from 'react'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useUIStore } from '@/stores/uiStore'
import { apiClient } from '@/api/client'
import type { WorkflowSaveRequest, Workflow, ApiResponse } from '@/types/api'
import { type Node, type Edge } from 'reactflow'

// Convert React Flow nodes/edges back to WorkflowDefinition format for the API
function flowToDefinition(nodes: Node[], edges: Edge[]) {
  const nodeMap: Record<string, unknown> = {}
  nodes.forEach((n) => {
    const { ui_config, _nodeType, ...config } = n.data as Record<string, unknown>
    nodeMap[n.id] = {
      type: _nodeType ?? n.type,
      config,
      position: n.position,
      ui_config,
    }
  })

  const edgeList = edges.map((e) => ({
    id: e.id,
    source_node_id: e.source,
    source_port: e.sourceHandle ?? 'default',
    target_node_id: e.target,
    target_port: e.targetHandle ?? 'default',
  }))

  return {
    nodes: nodeMap,
    edges: edgeList,
    ui_metadata: {
      layout: 'manual',
      version: '1.0',
      viewport: { x: 0, y: 0, zoom: 1 },
      generated_by_chat: false,
      chat_session_id: null,
    },
  }
}

export function useAutoSave(debounceMs = 2000) {
  const { workflowId, isDirty, nodes, edges, setSaveStatus, markSaved } = useWorkflowStore()
  const addToast = useUIStore((s) => s.addToast)
  const timer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (!isDirty || !workflowId) return

    setSaveStatus('saving')
    clearTimeout(timer.current)

    timer.current = setTimeout(async () => {
      try {
        const definition = flowToDefinition(nodes, edges)
        await apiClient.put<ApiResponse<Workflow>>(`/api/v1/workflows/${workflowId}`, {
          definition,
        } satisfies WorkflowSaveRequest)
        markSaved()
      } catch (err) {
        setSaveStatus('error')
        addToast({
          title: 'Auto-save failed',
          description: 'Changes are not saved. Click Save to retry.',
          variant: 'destructive',
        })
      }
    }, debounceMs)

    return () => clearTimeout(timer.current)
  }, [isDirty, workflowId, nodes, edges, debounceMs, setSaveStatus, markSaved, addToast])
}
