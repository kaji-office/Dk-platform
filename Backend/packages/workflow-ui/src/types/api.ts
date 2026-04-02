// ─────────────────────────────────────────────────────────────────────────────
// API types — derived from docs/api/openapi.yaml + docs/frontend/handover.md
// These are the wire-format types.  Do NOT redefine locally.
// ─────────────────────────────────────────────────────────────────────────────

// ── Shared envelope ──────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean
  data: T
}

export interface ApiError {
  error: {
    code: string
    message: string
    request_id: string
  }
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface RegisterRequest {
  email: string
  password: string
  name: string
  tenant_name: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  expires_in: number
}

export interface User {
  id: string
  email: string
  name: string
  tenant_id: string
  role: 'owner' | 'admin' | 'editor' | 'viewer'
  is_verified: boolean
  created_at: string
}

// ── Node types (17 exact PascalCase values) ───────────────────────────────────

export type NodeType =
  | 'PromptNode'
  | 'AgentNode'
  | 'SemanticSearchNode'
  | 'CodeExecutionNode'
  | 'APIRequestNode'
  | 'TemplatingNode'
  | 'WebSearchNode'
  | 'MCPNode'
  | 'SetStateNode'
  | 'CustomNode'
  | 'NoteNode'
  | 'OutputNode'
  | 'ControlFlowNode'
  | 'SubworkflowNode'
  | 'ManualTriggerNode'
  | 'ScheduledTriggerNode'
  | 'IntegrationTriggerNode'

export type NodeCategory =
  | 'ai_reasoning'
  | 'execution_data'
  | 'workflow_management'
  | 'logic_orchestration'
  | 'triggers'

export interface NodeUIConfig {
  editable: boolean
  node_type_label: string    // e.g. "AI Prompt"
  icon: string               // Lucide icon name
  color: string              // hex, e.g. "#6366f1"
  category: NodeCategory
  is_terminal: boolean       // if true, no delete handle shown
}

// ── Workflow definition ───────────────────────────────────────────────────────
// IMPORTANT: nodes is a Record<string, NodeDefinition>, NOT an array

export interface NodeDefinition {
  type: NodeType
  config: Record<string, unknown>
  position: { x: number; y: number }
  ui_config: NodeUIConfig
}

export interface EdgeDefinition {
  id: string
  source_node_id: string
  source_port: string        // "default" = pass all upstream outputs
  target_node_id: string
  target_port: string        // "default" = spread all as top-level vars
}

export interface WorkflowUIMetadata {
  layout: 'auto' | 'manual'
  version: string
  viewport: { x: number; y: number; zoom: number }
  generated_by_chat: boolean
  chat_session_id: string | null
}

export interface WorkflowDefinition {
  nodes: Record<string, NodeDefinition>
  edges: EdgeDefinition[]
  ui_metadata: WorkflowUIMetadata
}

// ── Workflow CRUD ─────────────────────────────────────────────────────────────

export interface Workflow {
  id: string
  name: string
  description: string
  definition: WorkflowDefinition
  tenant_id: string
  created_at: string
  updated_at: string
  is_active: boolean
  version: number
}

export interface WorkflowSaveRequest {
  name?: string
  description?: string
  definition?: WorkflowDefinition
}

// ── Execution ─────────────────────────────────────────────────────────────────

export type ExecutionStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCESS'
  | 'FAILED'
  | 'CANCELLED'
  | 'SUSPENDED'

export type NodeStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCESS'
  | 'FAILED'
  | 'RETRYING'
  | 'SKIPPED'
  | 'SUSPENDED'

export interface ExecutionRun {
  run_id: string
  workflow_id: string
  tenant_id: string
  status: ExecutionStatus
  started_at: string
  ended_at: string | null
  input_data: Record<string, unknown>
  output_data: Record<string, unknown> | null
  error: string | null
}

export interface NodeExecution {
  node_id: string
  run_id: string
  status: NodeStatus
  started_at: string | null
  ended_at: string | null
  output_preview: string | null
  error: string | null
  retry_count: number
}

export interface ExecutionLog {
  timestamp: string
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG'
  node_id: string | null
  message: string
}

// ── WebSocket — Execution ─────────────────────────────────────────────────────
// WS endpoint: /api/v1/ws/executions/{run_id}?token=<jwt>

export type ExecutionWsEvent =
  | { type: 'RUN_STARTED';    run_id: string; started_at: string }
  | { type: 'RUN_COMPLETED';  run_id: string; status: 'SUCCESS' | 'FAILED'; ended_at: string }
  | { type: 'NODE_STARTED';   run_id: string; node_id: string; started_at: string }
  | { type: 'NODE_COMPLETED'; run_id: string; node_id: string; status: NodeStatus; ended_at: string; output_preview?: string }
  | { type: 'NODE_FAILED';    run_id: string; node_id: string; error: string; retry_count: number }
  | { type: 'NODE_LOG';       run_id: string; node_id: string; level: 'INFO' | 'WARN' | 'ERROR'; message: string }
  | { type: 'HUMAN_WAITING';  run_id: string; node_id: string; form_schema: object }
  | { type: 'HEARTBEAT';      timestamp: string }

// ── Schedules ─────────────────────────────────────────────────────────────────

export interface WorkflowSchedule {
  id: string
  workflow_id: string
  tenant_id: string
  cron_expression: string
  timezone: string
  is_active: boolean
  next_fire_at: string | null
  input_data: Record<string, unknown>
  created_at: string
}

export interface ScheduleCreateRequest {
  cron_expression: string
  timezone?: string
  is_active?: boolean
  input_data?: Record<string, unknown>
}

// ── Webhooks ──────────────────────────────────────────────────────────────────

export interface InboundWebhook {
  id: string
  name: string
  workflow_id: string
  tenant_id: string
  endpoint_url: string
  webhook_secret: string    // ⚠ only shown on creation
  is_active: boolean
  created_at: string
}

export interface InboundWebhookCreate {
  name: string
  workflow_id: string
  events?: string[]
  is_active?: boolean
}

// ── API Keys ──────────────────────────────────────────────────────────────────

export interface ApiKey {
  id: string
  name: string
  key_prefix: string        // e.g. "wfk_abc123..."  — full key only on create
  tenant_id: string
  created_at: string
  last_used_at: string | null
}

// ── Billing / Usage ───────────────────────────────────────────────────────────

export interface UsageSummary {
  period_start: string
  period_end: string
  total_executions: number
  successful_executions: number
  failed_executions: number
  total_llm_tokens: number
  estimated_cost_usd: number
  breakdown_by_node_type: Record<string, { count: number; tokens: number; cost_usd: number }>
}
