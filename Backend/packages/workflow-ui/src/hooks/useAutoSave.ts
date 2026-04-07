// ─────────────────────────────────────────────────────────────────────────────
// useAutoSave — debounced workflow save
//
// Strategy (from docs/frontend/overview.md §9):
//   - Any canvas change: isDirty = true
//   - Debounce 2000ms
//   - PATCH /api/v1/workflows/{id} with flat { nodes, edges, ui_metadata }
//   - On success: saveStatus = 'saved', isDirty = false
//   - On failure: saveStatus = 'error', show toast
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { useEffect, useRef } from 'react'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useUIStore } from '@/stores/uiStore'
import { apiClient } from '@/api/client'
import type { Workflow, ApiResponse, NodeDefinition, EdgeDefinition } from '@/types/api'
import { type Node, type Edge } from '@xyflow/react'

// Convert React Flow nodes/edges back to the flat API format for PATCH
function flowToApiShape(nodes: Node[], edges: Edge[]) {
  const nodesMap: Record<string, Partial<NodeDefinition>> = {}
  nodes.forEach((n) => {
    const { ui_config, _nodeType, ...config } = n.data as Record<string, unknown>
    nodesMap[n.id] = {
      type: (_nodeType ?? n.type) as NodeDefinition['type'],
      config: config as Record<string, unknown>,
      position: n.position,
      ui_config: ui_config as NodeDefinition['ui_config'],
    }
  })

  const edgeList: EdgeDefinition[] = edges.map((e) => ({
    id: e.id,
    source_node_id: e.source,
    source_port: e.sourceHandle ?? 'default',
    target_node_id: e.target,
    target_port: e.targetHandle ?? 'default',
  }))

  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    nodes: nodesMap as any,
    edges: edgeList,
    ui_metadata: {
      layout: 'manual' as const,
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
        const body = flowToApiShape(nodes, edges)
        await apiClient.patch<ApiResponse<Workflow>>(`/api/v1/workflows/${workflowId}`, body)
        markSaved()
      } catch {
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
