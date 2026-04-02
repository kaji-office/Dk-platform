// ─────────────────────────────────────────────────────────────────────────────
// Chat types — from docs/frontend/chat-module.md §3 + docs/frontend/handover.md §3
// ─────────────────────────────────────────────────────────────────────────────

import type { WorkflowDefinition } from './api'

export type ConversationPhase =
  | 'GATHERING'
  | 'CLARIFYING'
  | 'FINALIZING'
  | 'GENERATING'
  | 'COMPLETE'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  ts: string
}

export interface ClarificationQuestion {
  id: string
  question: string
  // 5 types — "input_type" is the real field name (not "type")
  input_type: 'text' | 'select' | 'multiselect' | 'boolean' | 'number'
  options: string[]            // for select / multiselect
  hint?: string
  required: boolean
  maps_to_field?: string
}

export interface ClarificationBlock {
  type: 'clarification'
  questions: ClarificationQuestion[]
}

export interface RequirementSpec {
  goal?: string
  trigger_type?: 'manual' | 'scheduled' | 'webhook'
  trigger_config?: Record<string, unknown>
  input_sources?: string[]
  processing_steps?: Array<{
    description: string
    suggested_node_type?: string
    config_hints?: Record<string, unknown>
  }>
  integrations?: string[]
  output_format?: string
  constraints?: Record<string, unknown>
}

// Response from POST /api/v1/chat/sessions/{id}/message
// Field is "message" (NOT "reply") — verified against live API
export interface ChatMessageResponse {
  session_id: string
  phase: ConversationPhase
  message: string
  clarification: ClarificationBlock | null
  requirement_spec: RequirementSpec | null
  workflow_preview: WorkflowDefinition | null
  workflow_id: string | null
}

export interface ChatSession {
  session_id: string
  phase: ConversationPhase
  clarification_round: number
  generated_workflow_id: string | null
  created_at: string
  updated_at: string
}

// ── WebSocket — Chat ──────────────────────────────────────────────────────────
// WS endpoint: /api/v1/chat/sessions/ws/chat/{session_id}?token=<jwt>
// IMPORTANT: WS sends lightweight phase signals only.
//            Rich payload (clarification questions, WorkflowDefinition) always
//            comes from REST GET /sessions/{id} — never from WS.

export interface ChatWsClientMessage {
  type: 'message'
  content: string
}

export type ChatWsEvent =
  | { type: 'status';   phase: 'PROCESSING' }
  | { type: 'phase';    phase: 'CLARIFYING' | 'GENERATING' }
  | { type: 'response'; phase: 'COMPLETE'; message: string; workflow_id: string | null }
