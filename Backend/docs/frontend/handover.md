# Frontend Handover — Chat-Driven AI Workflow Builder

> **Authoritative reference.** The generic handover template circulated earlier contains
> incorrect API paths, wrong node types, and an incomplete edge schema. Use this document.
>
> Detailed specs live in:
> - `docs/frontend/overview.md` — tech stack, directory structure, auth, auto-save, WebSocket events
> - `docs/frontend/chat-module.md` — Chat store, components, WebSocket hook, all TypeScript interfaces
> - `docs/api/openapi.yaml` — single source of truth for every request/response schema

---

## 1. System Flow

```
User types in ChatPanel
  └─ POST /v1/chat/sessions/{id}/message
       │
       ├─ phase = CLARIFYING → ClarificationCard (typed input widgets)
       │    └─ User answers → next POST /message with serialised answers
       │
       └─ phase = COMPLETE  → WorkflowDefinition JSON with ui_config per node
            └─ workflowStore.loadFromDefinition() → React Flow canvas renders
                 └─ User edits canvas → PUT /v1/chat/sessions/{id}/workflow
                      └─ Validation result + optional suggestions returned
```

---

## 2. Correct API Paths

> The template used `/chat/query`, `/chat/clarify`, `/workflow/generate` — **these do not exist**.
> The real paths are below. All routes are prefixed `/v1`.

### Chat

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/chat/sessions` | Create session — returns `{session_id, phase}` |
| `GET` | `/v1/chat/sessions` | List tenant sessions |
| `GET` | `/v1/chat/sessions/{session_id}` | Get session + full message history |
| `POST` | `/v1/chat/sessions/{session_id}/message` | Send message → AI reply + optional DAG |
| `POST` | `/v1/chat/sessions/{session_id}/generate` | Force DAG generation (EDITOR role) |
| `PUT` | `/v1/chat/sessions/{session_id}/workflow` | Submit canvas edits → validation |
| `WS` | `/ws/chat/{session_id}` | Stream LLM tokens in real-time |

### Workflow CRUD

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/workflows` | List workflows |
| `POST` | `/v1/workflows` | Create blank workflow |
| `GET` | `/v1/workflows/{id}` | Get workflow definition |
| `PUT` | `/v1/workflows/{id}` | Save workflow edits |
| `DELETE` | `/v1/workflows/{id}` | Delete workflow |
| `POST` | `/v1/workflows/{id}/trigger` | Execute workflow |
| `POST` | `/v1/workflows/{id}/activate` | Activate scheduled/webhook workflow |

### Execution

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/executions` | List runs (filterable by workflow) |
| `GET` | `/v1/executions/{run_id}` | Get run detail |
| `POST` | `/v1/executions/{run_id}/cancel` | Cancel run |
| `GET` | `/v1/executions/{run_id}/nodes` | Per-node execution states |
| `GET` | `/v1/executions/{run_id}/logs` | Execution logs |
| `WS` | `/ws/executions/{run_id}` | Stream node status updates |

---

## 3. Correct Schemas

### 3.1 ChatMessageResponse — what `POST /message` returns

```typescript
interface ChatMessageResponse {
  session_id: string
  phase: 'GATHERING' | 'CLARIFYING' | 'FINALIZING' | 'GENERATING' | 'COMPLETE'
  reply: string                          // assistant text — always present

  // CLARIFYING phase only — render as form cards
  clarification: {
    type: 'clarification'
    questions: ClarificationQuestion[]
  } | null

  // Available after extraction starts
  requirement_spec: RequirementSpec | null

  // Populated when phase = GENERATING or COMPLETE
  workflow_preview: WorkflowDefinition | null

  // Set when phase = COMPLETE
  workflow_id: string | null
}
```

### 3.2 ClarificationQuestion — drives the input widget type

```typescript
interface ClarificationQuestion {
  id: string                                           // stable key
  question: string                                     // display text
  input_type: 'text' | 'select' | 'multiselect' | 'boolean' | 'number'
  options: string[]                                    // for select / multiselect
  hint?: string                                        // placeholder text
  required: boolean
  maps_to_field?: string                               // e.g. "trigger_type"
}
```

> **Note:** The template used `type: "text | select | boolean"` — the real field is `input_type`
> and it has 5 values including `multiselect` and `number`.

### 3.3 WorkflowDefinition — the wire format fed to React Flow

```typescript
interface WorkflowDefinition {
  nodes: Record<string, NodeDefinition>   // keyed by node_id — NOT an array
  edges: EdgeDefinition[]
  ui_metadata: WorkflowUIMetadata
}

interface NodeDefinition {
  type: NodeType        // one of 17 types — see §4
  config: object        // node-type-specific config
  position: { x: number; y: number }
  ui_config: NodeUIConfig
}

interface NodeUIConfig {
  editable: boolean
  node_type_label: string   // e.g. "AI Prompt", "HTTP Request"
  icon: string              // Lucide icon name, e.g. "sparkles"
  color: string             // hex, e.g. "#6366f1"
  category: 'ai_reasoning' | 'execution_data' | 'workflow_management'
             | 'logic_orchestration' | 'triggers'
  is_terminal: boolean      // true → no delete handle shown on the node
}

interface EdgeDefinition {
  id: string                // e.g. "edge_node1_output__node2_input"
  source_node_id: string
  source_port: string       // e.g. "output", "true_branch", "false_branch"
  target_node_id: string
  target_port: string       // e.g. "input"
}

interface WorkflowUIMetadata {
  layout: 'auto' | 'manual'
  version: string
  viewport: { x: number; y: number; zoom: number }
  generated_by_chat: boolean
  chat_session_id: string | null
}
```

> **Note:** The template used `nodes: []` (array) — the real format is `nodes: {}` (object keyed
> by node_id). Edge fields are `source_node_id / target_node_id`, not `source / target`.

### 3.4 Workflow Update Request/Response

```typescript
// PUT /v1/chat/sessions/{id}/workflow
interface WorkflowUpdateRequest {
  workflow_id?: string
  updated_nodes: Record<string, NodeDefinition>
  updated_edges: EdgeDefinition[]
  ui_metadata: WorkflowUIMetadata
}

interface WorkflowUpdateResponse {
  valid: boolean
  workflow: WorkflowDefinition
  validation_errors?: Array<{
    code: string
    message: string
    node_id: string | null
  }>
  suggestions?: string[]   // optional AI improvement hints
}
```

---

## 4. Node Types — Complete List

> The template used 6 generic types (`input | api | llm | transform | condition | output`).
> The platform has **17 specific types** across 5 categories. Use these exact string values.

| `type` value | Display Label | Icon | Hex Colour | Category |
|---|---|---|---|---|
| `prompt` | AI Prompt | `sparkles` | `#6366f1` | `ai_reasoning` |
| `agent` | AI Agent | `cpu` | `#8b5cf6` | `ai_reasoning` |
| `semantic_search` | Semantic Search | `search` | `#a855f7` | `ai_reasoning` |
| `code_execution` | Run Code | `code` | `#f59e0b` | `execution_data` |
| `api_request` | HTTP Request | `globe` | `#3b82f6` | `execution_data` |
| `templating` | Template | `file-text` | `#06b6d4` | `execution_data` |
| `web_search` | Web Search | `search-check` | `#0ea5e9` | `execution_data` |
| `mcp` | MCP Tool | `plug` | `#64748b` | `execution_data` |
| `set_state` | Set State | `database` | `#10b981` | `workflow_management` |
| `custom` | Custom | `wrench` | `#84cc16` | `workflow_management` |
| `note` | Note | `sticky-note` | `#e2e8f0` | `workflow_management` |
| `output` | Output | `arrow-right-circle` | `#14b8a6` | `workflow_management` |
| `control_flow` | Control Flow | `git-branch` | `#f97316` | `logic_orchestration` |
| `subworkflow` | Sub-Workflow | `layers` | `#ec4899` | `logic_orchestration` |
| `manual_trigger` | Manual Trigger | `play` | `#22c55e` | `triggers` |
| `scheduled_trigger` | Scheduled | `clock` | `#22c55e` | `triggers` |
| `integration_trigger` | Webhook | `zap` | `#22c55e` | `triggers` |

---

## 5. WebSocket Protocols

### Chat WebSocket — `/ws/chat/{session_id}`

```typescript
// Server → Client only (client sends messages via REST, not WS)
type ChatWsEvent =
  | { type: 'token';          content: string }
  | { type: 'done';           phase: ConversationPhase; full_response: ChatMessageResponse }
  | { type: 'phase_change';   from: ConversationPhase; to: ConversationPhase }
  | { type: 'workflow_ready'; workflow_id: string; workflow_preview: WorkflowDefinition }
```

### Execution WebSocket — `/ws/executions/{run_id}`

```typescript
type ExecutionWsEvent =
  | { type: 'RUN_STARTED';    run_id: string; started_at: string }
  | { type: 'RUN_COMPLETED';  run_id: string; status: 'SUCCESS' | 'FAILED'; ended_at: string }
  | { type: 'NODE_STARTED';   run_id: string; node_id: string; started_at: string }
  | { type: 'NODE_COMPLETED'; run_id: string; node_id: string; status: string; ended_at: string }
  | { type: 'NODE_FAILED';    run_id: string; node_id: string; error: string; retry_count: number }
  | { type: 'NODE_LOG';       run_id: string; node_id: string; level: 'INFO'|'WARN'|'ERROR'; message: string }
  | { type: 'HUMAN_WAITING';  run_id: string; node_id: string; form_schema: object }
  | { type: 'HEARTBEAT';      timestamp: string }
```

---

## 6. State Management

Two Zustand stores — do not merge them:

```
chatStore      — session, messages, streaming, clarification, requirementSpec, workflowPreview
workflowStore  — React Flow nodes[], edges[], selectedNodeId, runId, nodeStatuses, saveStatus
```

When chat generates a workflow, `chatStore` calls `workflowStore.loadFromDefinition(preview)` — the only coupling point between the two stores.

Full store shapes: `docs/frontend/chat-module.md` §4 (chatStore) and `docs/frontend/overview.md` §4 (workflowStore).

---

## 7. Authentication

```
Access token  (15 min) → React memory only — never localStorage
Refresh token (7 days) → HttpOnly cookie — never accessible to JS

All API requests: Authorization: Bearer <access_token>
Axios interceptor: catches 401 → POST /auth/token/refresh → retry
Logout: clear memory + POST /auth/logout (expires cookie server-side)
```

API key auth (for integrations): `X-API-Key: wfk_<key>` header instead of Bearer.

---

## 8. Required UI Modules — Priority Order

| # | Module | Route | Depends On |
|---|--------|-------|------------|
| 1 | Auth pages (login / register / MFA) | `/login`, `/signup` | — |
| 2 | App shell + sidebar | All protected routes | Auth |
| 3 | Workflow dashboard | `/workflows` | Auth |
| 4 | Chat-first creation | `/workflows/new` | Auth + Chat API |
| 5 | Workflow canvas editor | `/workflows/[id]` | Workflow API |
| 6 | Config panel (node edit) | (panel in editor) | Canvas |
| 7 | Execution monitor | `/workflows/[id]/runs` | Execution API |
| 8 | Log viewer | `/executions/[run_id]` | Execution API |
| 9 | Usage / billing dashboard | `/settings/billing` | Usage API |

---

## 9. Layout

```
┌── TopBar (56px) ─────────────────────────────────────────────────────┐
│  [logo]  [breadcrumb]                [run status] [user menu]        │
├── Sidebar ──┬── Main Content ────────────────────────────────────────┤
│  (240px,   │                                                          │
│  collapsed │  Route-specific content                                  │
│  to 48px)  │                                                          │
│            │  Workflow Editor:                                        │
│            │  [Chat 380px] | [Canvas flex-1] | [Config 380px overlay]│
└────────────┴──────────────────────────────────────────────────────────┘
```

Config panel overlaps canvas with drop shadow — it does **not** shrink the canvas width.

---

## 10. Tech Stack (Locked)

| Concern | Library | Version |
|---------|---------|---------|
| Framework | Next.js + App Router | 14 |
| Language | TypeScript | 5.x |
| DAG canvas | React Flow | v12 |
| Client state | Zustand | 4.x |
| Server state | TanStack Query | v5 |
| Styling | Tailwind CSS + shadcn/ui | latest |
| Forms | React Hook Form + Zod | latest |
| Code editor | Monaco Editor | latest |
| Animations | Framer Motion | latest |
| Icons | Lucide React | latest |
| Charts | Recharts | latest |
| Testing | Vitest + React Testing Library + Playwright | latest |

---

## 11. Key Corrections from Earlier Template

| Template said | Actual |
|---|---|
| `POST /chat/query` | `POST /v1/chat/sessions/{id}/message` |
| `POST /chat/clarify` | No separate endpoint — answered via next `/message` call |
| `POST /workflow/generate` | `POST /v1/chat/sessions/{id}/generate` |
| `PUT /workflow/update` | `PUT /v1/chat/sessions/{id}/workflow` |
| `nodes: []` (array) | `nodes: {}` (object keyed by node_id) |
| Edge fields `source / target` | `source_node_id / target_node_id` + `source_port / target_port` |
| `type: "text \| select \| boolean"` | `input_type: "text \| select \| multiselect \| boolean \| number"` |
| 6 generic node types | 17 specific node types (see §4) |
| Single global state object | Two stores: `chatStore` + `workflowStore` |
| `clarification_questions: string[]` | `clarification: ClarificationBlock` (structured, typed) |
