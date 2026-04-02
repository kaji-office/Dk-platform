// ─────────────────────────────────────────────────────────────────────────────
// WorkflowNode — generic React Flow node for all 17 node types
//
// Reads ui_config from node data to set color, icon, label, status ring.
// Status ring is driven by nodeStatuses in workflowStore (WebSocket updates).
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { useWorkflowStore, NODE_STATUS_STYLES } from '@/stores/workflowStore'
import type { NodeUIConfig, NodeStatus } from '@/types/api'
import * as LucideIcons from 'lucide-react'

interface NodeData {
  ui_config: NodeUIConfig
  [key: string]: unknown
}

export const WorkflowNode = memo(function WorkflowNode({ id, data }: NodeProps<NodeData>) {
  const nodeStatuses = useWorkflowStore((s) => s.nodeStatuses)
  const status = nodeStatuses[id] as NodeStatus | undefined
  const styles = status ? NODE_STATUS_STYLES[status] : null

  const { ui_config } = data
  if (!ui_config) return null

  const Icon = (LucideIcons as Record<string, unknown>)[toPascalCase(ui_config.icon)] as
    | React.FC<{ size?: number; className?: string }>
    | undefined

  return (
    <div
      className={`
        relative rounded-lg border-2 bg-background shadow-sm min-w-[160px] max-w-[200px]
        ${styles ? `ring-2 ${styles.ring}` : 'border-border'}
        ${styles?.opacity ?? ''}
      `}
    >
      {/* Colored header strip */}
      <div
        className="rounded-t-md px-3 py-2 flex items-center gap-2"
        style={{ backgroundColor: ui_config.color + '20', borderBottom: `2px solid ${ui_config.color}` }}
      >
        {Icon && (
          <Icon size={14} className="shrink-0" style={{ color: ui_config.color }} />
        )}
        <span className="text-xs font-medium truncate" style={{ color: ui_config.color }}>
          {ui_config.node_type_label}
        </span>
        {/* Status dot */}
        {styles && (
          <span
            className={`ml-auto w-2 h-2 rounded-full shrink-0 ${styles.dot} ${styles.animate ?? ''}`}
          />
        )}
      </div>

      {/* Node ID */}
      <div className="px-3 py-2">
        <span className="font-mono text-xs text-muted-foreground truncate block">{id}</span>
      </div>

      {/* Input handle — left */}
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-muted-foreground" />

      {/* Output handle — right (hidden if is_terminal) */}
      {!ui_config.is_terminal && (
        <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-muted-foreground" />
      )}
    </div>
  )
})

// Convert "arrow-right-circle" → "ArrowRightCircle" for Lucide lookup
function toPascalCase(str: string): string {
  return str
    .split('-')
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join('')
}
