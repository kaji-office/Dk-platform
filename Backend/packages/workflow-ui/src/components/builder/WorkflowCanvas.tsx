// ─────────────────────────────────────────────────────────────────────────────
// WorkflowCanvas — React Flow canvas wrapper
// Registers all 17 custom node types from docs/frontend/handover.md §4
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { ReactFlow, Background, Controls, MiniMap, BackgroundVariant, type NodeTypes } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useWorkflowStore } from '@/stores/workflowStore'
import { WorkflowNode } from '@/components/nodes/WorkflowNode'

// All 17 node types map to a single generic component that reads ui_config.
// Cast as NodeTypes to satisfy @xyflow/react v12 strict generics.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const nodeTypes: NodeTypes = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  PromptNode: WorkflowNode as any,
  AgentNode: WorkflowNode as any,
  SemanticSearchNode: WorkflowNode as any,
  CodeExecutionNode: WorkflowNode as any,
  APIRequestNode: WorkflowNode as any,
  TemplatingNode: WorkflowNode as any,
  WebSearchNode: WorkflowNode as any,
  MCPNode: WorkflowNode as any,
  SetStateNode: WorkflowNode as any,
  CustomNode: WorkflowNode as any,
  NoteNode: WorkflowNode as any,
  OutputNode: WorkflowNode as any,
  ControlFlowNode: WorkflowNode as any,
  SubworkflowNode: WorkflowNode as any,
  ManualTriggerNode: WorkflowNode as any,
  ScheduledTriggerNode: WorkflowNode as any,
  IntegrationTriggerNode: WorkflowNode as any,
}

export function WorkflowCanvas() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, setSelectedNode } =
    useWorkflowStore()

  return (
    <div className="flex-1 min-w-0 h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => setSelectedNode(node.id)}
        onPaneClick={() => setSelectedNode(null)}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        deleteKeyCode="Delete"
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        <Controls />
        <MiniMap nodeStrokeWidth={2} zoomable pannable />
      </ReactFlow>
    </div>
  )
}
