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
> All routes are prefixed `/api/v1`. Base URL: `http://localhost:8000` (local), `https://api.workflowplatform.io` (prod).

### Auth

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/auth/register` | Create tenant + owner — sends verification email |
| `POST` | `/api/v1/auth/login` | Email + password → `{access_token, refresh_token}` |
| `POST` | `/api/v1/auth/logout` | Revoke refresh token |
| `POST` | `/api/v1/auth/token/refresh` | Rotate refresh token → new pair |
| `POST` | `/api/v1/auth/verify-email` | Verify email with token from link `{token}` |
| `POST` | `/api/v1/auth/password/reset-request` | Send password reset email `{email}` |
| `POST` | `/api/v1/auth/password/reset` | Set new password `{token, new_password}` |

### Chat

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/chat/sessions` | Create session — returns `{session_id, phase}` |
| `GET` | `/api/v1/chat/sessions` | List tenant sessions |
| `GET` | `/api/v1/chat/sessions/{session_id}` | Get session + full message history |
| `POST` | `/api/v1/chat/sessions/{session_id}/message` | Send message → AI reply + optional DAG |
| `POST` | `/api/v1/chat/sessions/{session_id}/generate` | Force DAG generation (EDITOR role) |
| `PUT` | `/api/v1/chat/sessions/{session_id}/workflow` | Submit canvas edits → validation |
| `WS` | `/api/v1/chat/sessions/ws/chat/{session_id}` | Real-time streaming (auth via `?token=<jwt>`) |

### Workflow CRUD

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/workflows` | List workflows |
| `POST` | `/api/v1/workflows` | Create blank workflow |
| `GET` | `/api/v1/workflows/{id}` | Get workflow definition |
| `PUT` | `/api/v1/workflows/{id}` | Save workflow `{workflow: WorkflowDefinition}` |
| `DELETE` | `/api/v1/workflows/{id}` | Delete workflow |
| `POST` | `/api/v1/workflows/{id}/trigger` | Execute workflow |
| `POST` | `/api/v1/workflows/{id}/activate` | Activate scheduled/webhook workflow |

### Execution

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/executions` | List runs (filterable by workflow) |
| `GET` | `/api/v1/executions/{run_id}` | Get run detail |
| `POST` | `/api/v1/executions/{run_id}/cancel` | Cancel run |
| `GET` | `/api/v1/executions/{run_id}/nodes` | Per-node execution states |
| `GET` | `/api/v1/executions/{run_id}/logs` | Execution logs |
| `WS` | `/api/v1/ws/executions/{run_id}` | Stream node status (auth via `?token=<jwt>`) |

### Inbound Webhooks

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/webhooks/inbound` | List registered inbound webhooks |
| `POST` | `/api/v1/webhooks/inbound` | Register new inbound webhook (get `endpoint_url` + `secret`) |
| `GET` | `/api/v1/webhooks/inbound/{id}` | Get inbound webhook details |
| `PATCH` | `/api/v1/webhooks/inbound/{id}` | Update / deactivate |
| `DELETE` | `/api/v1/webhooks/inbound/{id}` | Soft-delete |
| `POST` | `/api/v1/webhooks/inbound/{workflow_id}` | **External trigger** — HMAC-signed POST from external system |

---

## 3. Correct Schemas

### 3.1 ChatMessageResponse — what `POST /message` returns

```typescript
interface ChatMessageResponse {
  session_id: string
  phase: 'GATHERING' | 'CLARIFYING' | 'FINALIZING' | 'GENERATING' | 'COMPLETE'
  message: string                        // assistant text — always present (NOT "reply")

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

> **Correction:** The field is `message`, not `reply`. Verified against live API — `response.message` is the assistant text.

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
  source_node: string       // source node_id (NOT source_node_id)
  source_port: string       // "default" = pass all upstream outputs; named port = e.g. "true", "false", "rendered"
  target_node: string       // target node_id (NOT target_node_id)
  target_port: string       // "default" = spread all values as top-level template variables;
                            // named port = e.g. "input" nests them under that key
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
> by node_id). Edge fields are `source_node / target_node` (NOT `source_node_id / target_node_id`, NOT bare `source / target`).

### 3.4 Workflow Update Request/Response

```typescript
// PUT /api/v1/chat/sessions/{id}/workflow
// Body: complete WorkflowDefinition replacement — NOT a diff
interface WorkflowUpdateRequest {
  workflow: WorkflowDefinition   // full replacement (nodes + edges + ui_metadata)
}

// PUT /api/v1/workflows/{id}  (auto-save from canvas)
// Body: PatchWorkflowRequest — flat fields, not wrapped in {workflow:}
interface WorkflowSaveRequest {
  name?: string
  description?: string
  definition?: WorkflowDefinition   // full replacement (nodes + edges + ui_metadata)
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
>
> **Critical:** type values are PascalCase strings ending in `Node` — not snake_case.
> Sending `"manual_trigger"` or `"output"` will cause a 422 validation error.

| `type` value | Display Label | Icon | Hex Colour | Category |
|---|---|---|---|---|
| `PromptNode` | AI Prompt | `sparkles` | `#6366f1` | `ai_reasoning` |
| `AgentNode` | AI Agent | `cpu` | `#8b5cf6` | `ai_reasoning` |
| `SemanticSearchNode` | Semantic Search | `search` | `#a855f7` | `ai_reasoning` |
| `CodeExecutionNode` | Run Code | `code` | `#f59e0b` | `execution_data` |
| `APIRequestNode` | HTTP Request | `globe` | `#3b82f6` | `execution_data` |
| `TemplatingNode` | Template | `file-text` | `#06b6d4` | `execution_data` |
| `WebSearchNode` | Web Search | `search-check` | `#0ea5e9` | `execution_data` |
| `MCPNode` | MCP Tool | `plug` | `#64748b` | `execution_data` |
| `SetStateNode` | Set State | `database` | `#10b981` | `workflow_management` |
| `CustomNode` | Custom | `wrench` | `#84cc16` | `workflow_management` |
| `NoteNode` | Note | `sticky-note` | `#e2e8f0` | `workflow_management` |
| `OutputNode` | Output | `arrow-right-circle` | `#14b8a6` | `workflow_management` |
| `ControlFlowNode` | Control Flow | `git-branch` | `#f97316` | `logic_orchestration` |
| `SubworkflowNode` | Sub-Workflow | `layers` | `#ec4899` | `logic_orchestration` |
| `ManualTriggerNode` | Manual Trigger | `play` | `#22c55e` | `triggers` |
| `ScheduledTriggerNode` | Scheduled | `clock` | `#22c55e` | `triggers` |
| `IntegrationTriggerNode` | Webhook | `zap` | `#22c55e` | `triggers` |

---

## 5. WebSocket Protocols

### Chat WebSocket — `WS /api/v1/chat/sessions/ws/chat/{session_id}`

> **Auth:** Browsers cannot set `Authorization` headers on WebSocket connections.
> Pass the JWT as a query param: `?token=<access_token>`
> The server closes with code 4001 if token is missing or invalid.

```typescript
// Client → Server (send a chat message)
interface ChatWsClientMessage {
  type: 'message'
  content: string    // the user's text
}

// Server → Client events
type ChatWsEvent =
  | { type: 'status';   phase: 'PROCESSING' }           // orchestrator started
  | { type: 'phase';    phase: 'CLARIFYING' | 'GENERATING' }  // phase transition
  | { type: 'response'; phase: 'COMPLETE'; message: string; workflow_id: string | null }

// Connection lifecycle:
//   1. Connect with ?token=<jwt>
//   2. Send { type: "message", content: "..." } for each user turn
//   3. Server emits status/phase events during processing, then response when done
//   4. After receiving "response", fetch full ChatMessageResponse via
//      GET /api/v1/chat/sessions/{session_id} to get clarification questions,
//      requirement_spec, workflow_preview, etc.
```

> **Note:** The streaming WebSocket delivers lightweight phase signals only.
> Rich payload (clarification questions, WorkflowDefinition, RequirementSpec) always
> comes from the REST endpoints — never from the WebSocket. This keeps the WS lean and
> the REST API as the single source of truth for session state.

### Execution WebSocket — `WS /api/v1/ws/executions/{run_id}`

> **Auth:** Pass JWT as query param: `?token=<access_token>` (browsers cannot set Authorization headers on WS connections).

```typescript
// These are the exact event types published by RunOrchestrator to Redis PubSub channel
// `run:{run_id}:events`, then fanned out to the browser by the WebSocket hub.
type ExecutionWsEvent =
  | { type: 'node_state';        node_id: string; status: 'RUNNING' | 'SUCCESS' | 'FAILED'; ts: string }
  | { type: 'run_complete';      status: 'SUCCESS' | 'FAILED'; ts: string }
  | { type: 'run_waiting_human'; node_id: string; ts: string }
```

> **Note:** Event types are lowercase snake_case (`node_state`, `run_complete`, `run_waiting_human`).
> NOT PascalCase (`RUN_STARTED`, `NODE_COMPLETED`, etc.) as the earlier template stated.
> There is no `NODE_LOG`, `HEARTBEAT`, or `RUN_STARTED` event in v1.0.

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

## 11. Email Verification & Password Reset Flow

These flows are fully implemented — the frontend pages for `/verify-email/[token]` and `/reset-password/[token]` just need to call the API.

```
Registration flow:
  POST /api/v1/auth/register { email, password, name, tenant_name }
    → 201 { access_token, refresh_token, expires_in }
    → verification email sent automatically (SMTP)
  
  User clicks link in email: /verify-email?token=<token>
    POST /api/v1/auth/verify-email { token }
    → 200 OK — email verified, user.is_verified = true

Password reset flow:
  POST /api/v1/auth/password/reset-request { email }
    → 204 always (no enumeration — response same whether account exists)
    → reset email sent if account found
  
  User clicks link in email: /reset-password?token=<token>
    POST /api/v1/auth/password/reset { token, new_password }
    → 200 OK — password updated, token marked used
    → 400 if token expired (24h TTL) or already used
```

Frontend notes:
- Show "Check your email" screen after register — don't auto-navigate to dashboard until verified
- `is_verified: false` on the `User` object → display persistent banner until verified
- Reset-request page: always show "Email sent" even if 204 (prevents account enumeration)

---

## 12. Rate Limiting

All API endpoints are rate-limited per tenant: **60 requests/minute**.

On limit exceeded the server returns `429 Too Many Requests`:
```json
{ "error": { "code": "RATE_LIMIT_EXCEEDED", "message": "...", "request_id": "..." } }
```

Headers on the 429 response:
```
Retry-After: 60          ← seconds until window resets
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
```

Frontend must handle 429 in the Axios interceptor — show a toast and retry after `Retry-After` seconds. Do NOT retry automatically for user-initiated actions.

---

## 13. Inbound Webhook Management (for `integration_trigger` nodes)

When a workflow uses an `integration_trigger` node, the user registers an inbound webhook so an external system can trigger it via HTTP POST.

```typescript
// POST /api/v1/webhooks/inbound
interface InboundWebhookCreate {
  name: string        // human-readable label
  workflow_id: string // workflow to trigger
  events?: string[]  // optional — for documentation only
  is_active?: boolean
}

interface InboundWebhook {
  id: string
  name: string
  workflow_id: string
  tenant_id: string
  endpoint_url: string    // share this with the external system
  webhook_secret: string  // ⚠ SHOWN ONCE — store it; HMAC-SHA256 signing key
  is_active: boolean
  created_at: string
}
```

UI behaviour:
- After creating, show `webhook_secret` in a copy-to-clipboard modal with "Store this now — it won't be shown again"
- The `endpoint_url` is always visible and safe to display
- On the workflow canvas, the `integration_trigger` node config panel should include a "Webhook" section that shows the registered endpoint URL and a "Regenerate Secret" button

External system signs requests:
```python
# How the external system must sign:
import hmac, hashlib
sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
headers["X-Webhook-Signature"] = f"sha256={sig}"
```

---

## 14. Key Corrections from Earlier Template

| Template said | Actual |
|---|---|
| `POST /chat/query` | `POST /api/v1/chat/sessions/{id}/message` |
| `POST /chat/clarify` | No separate endpoint — answered via next `/message` call |
| `POST /workflow/generate` | `POST /api/v1/chat/sessions/{id}/generate` |
| `PUT /workflow/update` | `PUT /api/v1/chat/sessions/{id}/workflow` |
| All paths prefixed `/v1/` | Prefix is `/api/v1/` |
| `nodes: []` (array) | `nodes: {}` (object keyed by node_id) |
| Edge fields `source / target` | `source_node / target_node` + `source_port / target_port` |
| `type: "text \| select \| boolean"` | `input_type: "text \| select \| multiselect \| boolean \| number"` |
| 6 generic node types | 17 specific node types (see §4) |
| Single global state object | Two stores: `chatStore` + `workflowStore` |
| `clarification_questions: string[]` | `clarification: ClarificationBlock` (structured, typed) |
| Chat WS sends `token/done/phase_change/workflow_ready` | Sends `status/phase/response` — no streaming tokens; fetch REST for full payload |
| `WorkflowUpdateRequest` has `updated_nodes`/`updated_edges` | Body is `{ workflow: WorkflowDefinition }` — full replacement |
| Auto-save to `PUT /api/v2/workflows/{id}` | `PUT /api/v1/workflows/{id}` |
