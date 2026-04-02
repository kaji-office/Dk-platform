// ─────────────────────────────────────────────────────────────────────────────
// Workflow store — canvas state + execution state
// From: docs/frontend/overview.md §4, docs/frontend/handover.md §6
//
// IMPORTANT: workflowStore and chatStore are separate (do NOT merge).
// The only coupling point: chatStore calls workflowStore.loadFromDefinition()
// when the chat phase reaches COMPLETE.
// ─────────────────────────────────────────────────────────────────────────────

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import {
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
} from 'reactflow'
import type {
  WorkflowDefinition,
  NodeDefinition,
  EdgeDefinition,
  ExecutionStatus,
  NodeStatus,
  ExecutionWsEvent,
} from '@/types/api'

// ── Node status styling map (used by all custom node components) ──────────────

export const NODE_STATUS_STYLES: Record<NodeStatus, {
  ring: string
  dot: string
  animate?: string
  opacity?: string
}> = {
  PENDING:   { ring: 'ring-gray-300',   dot: 'bg-gray-400' },
  RUNNING:   { ring: 'ring-blue-400',   dot: 'bg-blue-500',   animate: 'animate-pulse' },
  SUCCESS:   { ring: 'ring-green-400',  dot: 'bg-green-500' },
  FAILED:    { ring: 'ring-red-400',    dot: 'bg-red-500' },
  RETRYING:  { ring: 'ring-yellow-400', dot: 'bg-yellow-500', animate: 'animate-spin' },
  SKIPPED:   { ring: 'ring-gray-200',   dot: 'bg-gray-300',   opacity: 'opacity-50' },
  SUSPENDED: { ring: 'ring-orange-400', dot: 'bg-orange-400', animate: 'animate-bounce' },
}

// ── Conversion: WorkflowDefinition → React Flow nodes/edges ──────────────────
// WorkflowDefinition.nodes is a Record<string, NodeDefinition> (keyed by node_id).
// React Flow expects Node[] with an `id` field.

function definitionToFlow(definition: WorkflowDefinition): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = Object.entries(definition.nodes).map(([id, nodeDef]: [string, NodeDefinition]) => ({
    id,
    type: nodeDef.type,          // maps to our custom node component registry
    position: nodeDef.position,
    data: {
      ...nodeDef.config,
      ui_config: nodeDef.ui_config,
      _nodeType: nodeDef.type,
    },
  }))

  // Edge fields: source_node_id / target_node_id / source_port / target_port
  const edges: Edge[] = definition.edges.map((e: EdgeDefinition) => ({
    id: e.id,
    source: e.source_node_id,
    sourceHandle: e.source_port,
    target: e.target_node_id,
    targetHandle: e.target_port,
  }))

  return { nodes, edges }
}

// ── Store shape ───────────────────────────────────────────────────────────────

interface WorkflowStore {
  // Graph state (React Flow)
  nodes: Node[]
  edges: Edge[]
  selectedNodeId: string | null

  // Persistence
  workflowId: string | null
  workflowName: string
  isDirty: boolean
  lastSavedAt: Date | null
  saveStatus: 'idle' | 'saving' | 'saved' | 'error'

  // Execution
  runId: string | null
  runStatus: ExecutionStatus | null
  nodeStatuses: Record<string, NodeStatus>
  nodeLogs: Record<string, string[]>

  // React Flow handlers
  onNodesChange: OnNodesChange
  onEdgesChange: OnEdgesChange
  onConnect: OnConnect

  // Actions
  setSelectedNode: (id: string | null) => void
  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => void
  setSaveStatus: (status: WorkflowStore['saveStatus']) => void
  setWorkflowMeta: (id: string, name: string) => void
  markSaved: () => void

  // Called by chatStore when workflow generation completes
  loadFromDefinition: (definition: WorkflowDefinition, workflowId?: string) => void

  // Called by useWebSocket hook when events arrive
  applyWsEvent: (event: ExecutionWsEvent) => void

  // Reset execution state before a new run
  startRun: (runId: string) => void
}

export const useWorkflowStore = create<WorkflowStore>()(
  devtools(
    (set, get) => ({
      nodes: [],
      edges: [],
      selectedNodeId: null,

      workflowId: null,
      workflowName: 'Untitled Workflow',
      isDirty: false,
      lastSavedAt: null,
      saveStatus: 'idle',

      runId: null,
      runStatus: null,
      nodeStatuses: {},
      nodeLogs: {},

      // React Flow change handlers
      onNodesChange: (changes) =>
        set(
          (s) => ({ nodes: applyNodeChanges(changes, s.nodes), isDirty: true }),
          false,
          'workflow/onNodesChange',
        ),

      onEdgesChange: (changes) =>
        set(
          (s) => ({ edges: applyEdgeChanges(changes, s.edges), isDirty: true }),
          false,
          'workflow/onEdgesChange',
        ),

      onConnect: (connection) =>
        set(
          (s) => ({ edges: addEdge(connection, s.edges), isDirty: true }),
          false,
          'workflow/onConnect',
        ),

      setSelectedNode: (id) =>
        set({ selectedNodeId: id }, false, 'workflow/setSelectedNode'),

      updateNodeConfig: (nodeId, config) =>
        set(
          (s) => ({
            nodes: s.nodes.map((n) =>
              n.id === nodeId ? { ...n, data: { ...n.data, ...config } } : n,
            ),
            isDirty: true,
          }),
          false,
          'workflow/updateNodeConfig',
        ),

      setSaveStatus: (status) =>
        set({ saveStatus: status }, false, 'workflow/setSaveStatus'),

      setWorkflowMeta: (id, name) =>
        set({ workflowId: id, workflowName: name }, false, 'workflow/setMeta'),

      markSaved: () =>
        set(
          { saveStatus: 'saved', isDirty: false, lastSavedAt: new Date() },
          false,
          'workflow/markSaved',
        ),

      loadFromDefinition: (definition, workflowId) => {
        const { nodes, edges } = definitionToFlow(definition)
        set(
          {
            nodes,
            edges,
            workflowId: workflowId ?? get().workflowId,
            isDirty: false,
            saveStatus: 'saved',
          },
          false,
          'workflow/loadFromDefinition',
        )
      },

      startRun: (runId) =>
        set(
          { runId, runStatus: 'RUNNING', nodeStatuses: {}, nodeLogs: {} },
          false,
          'workflow/startRun',
        ),

      applyWsEvent: (event) =>
        set(
          (s) => {
            switch (event.type) {
              case 'RUN_STARTED':
                return { runStatus: 'RUNNING' }
              case 'RUN_COMPLETED':
                return { runStatus: event.status }
              case 'NODE_STARTED':
                return {
                  nodeStatuses: { ...s.nodeStatuses, [event.node_id]: 'RUNNING' },
                }
              case 'NODE_COMPLETED':
                return {
                  nodeStatuses: { ...s.nodeStatuses, [event.node_id]: event.status },
                }
              case 'NODE_FAILED':
                return {
                  nodeStatuses: { ...s.nodeStatuses, [event.node_id]: 'FAILED' },
                }
              case 'NODE_LOG': {
                const existing = s.nodeLogs[event.node_id] ?? []
                return {
                  nodeLogs: {
                    ...s.nodeLogs,
                    [event.node_id]: [
                      ...existing,
                      `[${event.level}] ${event.message}`,
                    ],
                  },
                }
              }
              default:
                return {}
            }
          },
          false,
          'workflow/applyWsEvent',
        ),
    }),
    { name: 'WorkflowStore' },
  ),
)
