// ─────────────────────────────────────────────────────────────────────────────
// NodeConfigPanel — right-side overlay panel for editing selected node config
// Overlaps canvas (does NOT shrink it) — per docs/frontend/handover.md §9
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { useWorkflowStore } from '@/stores/workflowStore'
import { X } from 'lucide-react'
import type { NodeUIConfig } from '@/types/api'
import Editor from '@monaco-editor/react'

interface Props {
  nodeId: string
}

export function NodeConfigPanel({ nodeId }: Props) {
  const nodes = useWorkflowStore((s) => s.nodes)
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig)
  const setSelectedNode = useWorkflowStore((s) => s.setSelectedNode)

  const node = nodes.find((n) => n.id === nodeId)
  if (!node) return null

  const { ui_config, _nodeType, ...config } = node.data as {
    ui_config: NodeUIConfig
    _nodeType: string
    [key: string]: unknown
  }

  const configJson = JSON.stringify(config, null, 2)

  function handleEditorChange(value: string | undefined) {
    if (!value) return
    try {
      const parsed = JSON.parse(value)
      updateNodeConfig(nodeId, parsed)
    } catch {
      // Ignore parse errors during editing
    }
  }

  return (
    // Absolute overlay from right — does not shrink canvas
    <div className="absolute right-0 top-0 bottom-0 w-96 bg-background border-l border-border shadow-xl flex flex-col z-10">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b border-border"
        style={{ borderTopColor: ui_config?.color }}
      >
        <div>
          <p className="text-xs text-muted-foreground">{nodeId}</p>
          <p className="text-sm font-medium">{ui_config?.node_type_label ?? _nodeType}</p>
        </div>
        <button
          onClick={() => setSelectedNode(null)}
          className="p-1 rounded hover:bg-muted transition-colors"
        >
          <X size={15} />
        </button>
      </div>

      {/* Config editor — Monaco JSON */}
      <div className="flex-1 overflow-hidden">
        <Editor
          language="json"
          value={configJson}
          onChange={handleEditorChange}
          theme="vs-light"
          options={{
            minimap: { enabled: false },
            lineNumbers: 'off',
            folding: false,
            wordWrap: 'on',
            scrollBeyondLastLine: false,
            fontSize: 12,
            tabSize: 2,
          }}
        />
      </div>
    </div>
  )
}
