// ─────────────────────────────────────────────────────────────────────────────
// WorkflowCanvas — React Flow canvas wrapper
// Registers all 17 custom node types from docs/frontend/handover.md §4
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useWorkflowStore } from '@/stores/workflowStore'
import { WorkflowNode } from '@/components/nodes/WorkflowNode'

// All 17 node types map to a single generic component that reads ui_config.
// Custom node components can be added here as the app grows.
const nodeTypes = {
  PromptNode: WorkflowNode,
  AgentNode: WorkflowNode,
  SemanticSearchNode: WorkflowNode,
  CodeExecutionNode: WorkflowNode,
  APIRequestNode: WorkflowNode,
  TemplatingNode: WorkflowNode,
  WebSearchNode: WorkflowNode,
  MCPNode: WorkflowNode,
  SetStateNode: WorkflowNode,
  CustomNode: WorkflowNode,
  NoteNode: WorkflowNode,
  OutputNode: WorkflowNode,
  ControlFlowNode: WorkflowNode,
  SubworkflowNode: WorkflowNode,
  ManualTriggerNode: WorkflowNode,
  ScheduledTriggerNode: WorkflowNode,
  IntegrationTriggerNode: WorkflowNode,
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
