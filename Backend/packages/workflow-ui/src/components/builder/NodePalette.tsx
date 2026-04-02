// ─────────────────────────────────────────────────────────────────────────────
// NodePalette — left sidebar with draggable node type tiles
// Node type catalogue from docs/frontend/handover.md §4
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import type { NodeType, NodeCategory } from '@/types/api'

interface NodeEntry {
  type: NodeType
  label: string
  icon: string
  color: string
  category: NodeCategory
}

// Complete 17-node catalogue (exact PascalCase type strings)
const NODE_CATALOGUE: NodeEntry[] = [
  { type: 'ManualTriggerNode',      label: 'Manual Trigger',  icon: 'play',              color: '#22c55e', category: 'triggers' },
  { type: 'ScheduledTriggerNode',   label: 'Scheduled',       icon: 'clock',             color: '#22c55e', category: 'triggers' },
  { type: 'IntegrationTriggerNode', label: 'Webhook',         icon: 'zap',               color: '#22c55e', category: 'triggers' },
  { type: 'PromptNode',             label: 'AI Prompt',       icon: 'sparkles',          color: '#6366f1', category: 'ai_reasoning' },
  { type: 'AgentNode',              label: 'AI Agent',        icon: 'cpu',               color: '#8b5cf6', category: 'ai_reasoning' },
  { type: 'SemanticSearchNode',     label: 'Semantic Search', icon: 'search',            color: '#a855f7', category: 'ai_reasoning' },
  { type: 'APIRequestNode',         label: 'HTTP Request',    icon: 'globe',             color: '#3b82f6', category: 'execution_data' },
  { type: 'CodeExecutionNode',      label: 'Run Code',        icon: 'code',              color: '#f59e0b', category: 'execution_data' },
  { type: 'TemplatingNode',         label: 'Template',        icon: 'file-text',         color: '#06b6d4', category: 'execution_data' },
  { type: 'WebSearchNode',          label: 'Web Search',      icon: 'search-check',      color: '#0ea5e9', category: 'execution_data' },
  { type: 'MCPNode',                label: 'MCP Tool',        icon: 'plug',              color: '#64748b', category: 'execution_data' },
  { type: 'SetStateNode',           label: 'Set State',       icon: 'database',          color: '#10b981', category: 'workflow_management' },
  { type: 'OutputNode',             label: 'Output',          icon: 'arrow-right-circle',color: '#14b8a6', category: 'workflow_management' },
  { type: 'NoteNode',               label: 'Note',            icon: 'sticky-note',       color: '#e2e8f0', category: 'workflow_management' },
  { type: 'CustomNode',             label: 'Custom',          icon: 'wrench',            color: '#84cc16', category: 'workflow_management' },
  { type: 'ControlFlowNode',        label: 'Control Flow',    icon: 'git-branch',        color: '#f97316', category: 'logic_orchestration' },
  { type: 'SubworkflowNode',        label: 'Sub-Workflow',    icon: 'layers',            color: '#ec4899', category: 'logic_orchestration' },
]

const CATEGORY_LABELS: Record<NodeCategory, string> = {
  triggers:             'Triggers',
  ai_reasoning:         'AI',
  execution_data:       'Data & Execution',
  workflow_management:  'Workflow',
  logic_orchestration:  'Logic',
}

function onDragStart(e: React.DragEvent, node: NodeEntry) {
  e.dataTransfer.setData('application/reactflow/type', node.type)
  e.dataTransfer.setData('application/reactflow/color', node.color)
  e.dataTransfer.setData('application/reactflow/label', node.label)
  e.dataTransfer.effectAllowed = 'move'
}

export function NodePalette() {
  const categories = [...new Set(NODE_CATALOGUE.map((n) => n.category))] as NodeCategory[]

  return (
    <aside className="w-52 shrink-0 border-r border-border overflow-y-auto bg-background py-2">
      {categories.map((cat) => (
        <div key={cat} className="mb-3">
          <p className="px-3 py-1 text-[10px] uppercase tracking-widest font-semibold text-muted-foreground">
            {CATEGORY_LABELS[cat]}
          </p>
          {NODE_CATALOGUE.filter((n) => n.category === cat).map((node) => (
            <div
              key={node.type}
              draggable
              onDragStart={(e) => onDragStart(e, node)}
              className="mx-2 mb-1 flex items-center gap-2 rounded-md px-2 py-1.5 cursor-grab hover:bg-muted transition-colors"
            >
              <span
                className="w-2.5 h-2.5 rounded-sm shrink-0"
                style={{ backgroundColor: node.color }}
              />
              <span className="text-xs truncate">{node.label}</span>
            </div>
          ))}
        </div>
      ))}
    </aside>
  )
}
