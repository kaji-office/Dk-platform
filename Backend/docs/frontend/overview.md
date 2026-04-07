## Frontend

> **Depends on:** E-1 (workflow-api) delivering stable API contracts
> UI shell (routing, auth pages, layout) can start in parallel with E-1.

| # | Task | Status | Assigned To | Started | Completed | Depends On |
|---|------|--------|-------------|---------|-----------|------------|
| F-1 | **Auth pages + shell layout** | ⏳ Pending | — | — | — | E-1 (auth routes) |
| F-2 | **Workflow canvas (React Flow)** | ⏳ Pending | — | — | — | F-1 |
| F-3 | **DynamicConfigForm + node panels** | ⏳ Pending | — | — | — | F-2 |
| F-4 | **Execution monitor + live updates** | ⏳ Pending | — | — | — | F-2, E-2 |
| F-5 | **TransformNode Monaco editor** | ⏳ Pending | — | — | — | F-3 |
| F-6 | **Usage / billing dashboard** | ⏳ Pending | — | — | — | F-1 |

### F-1 — Auth Pages + Shell Layout

**Deliverables:** Login, Register, Forgot Password, MFA Verify pages. App shell with sidebar nav, tenant switcher, user menu.

### F-2 — Workflow Canvas

**Deliverables:** React Flow canvas, drag-to-connect edges, node palette sidebar, pan/zoom, auto-save (debounce 2s), publish button. `WorkflowStore` (Zustand) with undo/redo.

### F-3 — DynamicConfigForm + Node Panels

**Deliverables:** Right-panel config form rendered from node JSON schema. Field renderers: text, number, select, toggle, code (Monaco), credential picker, jmespath editor.

### F-4 — Execution Monitor + Live Updates

**Deliverables:** Execution list page, run detail page showing node graph with live status overlays. WebSocket client consuming `WS /api/v1/ws/executions/{run_id}`. Log viewer with level filter.

### F-5 — TransformNode Monaco Editor

**Deliverables:** Full-screen Monaco editor for Python code, syntax highlighting, `Ctrl+S` saves to node config, read-only sandbox restriction hints shown in editor margin.

### F-6 — Usage / Billing Dashboard

**Deliverables:** Charts (recharts) for execution count, LLM token spend, cost by node type. Current period summary card. CSV export.

---

## Parallel Work Matrix

```
Week  | Engineer A              | Engineer B              | Engineer C (optional)
------|-------------------------|-------------------------|---------------------
1-2   | A-1 Models              | A-2 Errors + A-3 Ports  | —
3     | B-1 Graph Engine        | B-2 Node Framework      | D-1 Auth (can start)
4     | B-2 Node Types          | B-1 Graph (finish)      | D-2 Storage
5     | C-1 Execution Engine    | D-1 Auth (finish)       | D-2 Storage (finish)
6     | C-1 Execution (finish)  | D-2 Storage (finish)    | D-3 Billing + D-4 PII
7     | C-2 Scheduler           | D-6 Connectors          | D-3/D-4/D-5 (finish)
8     | E-1 workflow-api        | E-2 workflow-worker     | D-7 Cache + D-5 Obs
9     | E-1 (finish + tests)    | E-2 (finish + tests)    | E-3 CLI + G-1 Chat Models
10    | G-2 Requirement Engine  | G-3 DAG Generator       | F-1 + F-2 Canvas
11    | G-4 ChatOrchestrator    | G-5 Chat API routes     | F-3 + F-4 Monitor
12    | G-6 Chat UI             | F-5 + F-6               | G-5 (finish + tests)
```

---


# Frontend — Overview
## workflow-ui (Next.js 14) + @workflow/react

---

## 1. Technology Stack

| Concern | Technology | Rationale |
|---|---|---|
| Framework | Next.js 14 + App Router | SSR for auth pages, client components for interactive builder |
| Language | TypeScript 5.x | Full type safety; SDK response types generated as TS interfaces |
| Canvas / DAG | React Flow v12 | Node-based graph editor with custom node types |
| State Management | Zustand + TanStack Query v5 | Zustand for canvas state; TQ for server state + caching |
| Styling | Tailwind CSS + shadcn/ui | Utility-first; accessible component primitives |
| Code Editor | Monaco Editor | Syntax highlighting for Python/Jinja2 in node config panels |
| Forms | React Hook Form + Zod | Dynamic form generation from node JSON Schema |
| Real-time | Native WebSocket + custom hook | `useWebSocket` wrapping browser WebSocket API |
| Charts | Recharts | Execution metrics, token usage charts |
| Animations | Framer Motion | Page transitions, node status ring animations |
| Testing | Vitest + RTL + Playwright | Unit + integration + E2E |

---

## 2. Progressive Disclosure — Core UI Principle

Every node configuration panel operates in two modes. Users can switch at any time.

```
┌─────────────────────────────────────────────────────┐
│  AI Node                            [Form] [Code]   │
├─────────────────────────────────────────────────────┤
│  FORM MODE (default — business user)                │
│                                                     │
│  Model:      [ Claude Haiku        ▼ ]              │
│  Prompt:     ┌─────────────────────────────────┐   │
│              │ Write a summary of {{input.text}}│   │
│              └─────────────────────────────────┘   │
│  Max tokens: [ 500    ]  Temperature: [ 0.7    ]    │
│                                                     │
│  ✦ Generate prompt with AI                          │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  AI Node                            [Form] [Code]   │
├─────────────────────────────────────────────────────┤
│  CODE MODE (developer / advanced user)              │
│                                                     │
│  1  {                                               │
│  2    "model": "claude-haiku-3-5",                  │
│  3    "prompt_template": "Summarise: {{input.text}}",│
│  4    "max_tokens": 500,                            │
│  5    "temperature": 0.7                            │
│  6  }                                               │
│                                                     │
│  ✦ Generate config with AI                          │
└─────────────────────────────────────────────────────┘
```

---

## 3. Application Module Structure

```
packages/workflow-ui/
├── package.json
├── next.config.ts
└── src/
    ├── app/                          # Next.js App Router
    │   ├── (auth)/                   # Auth pages (public — no sidebar)
    │   │   ├── login/page.tsx
    │   │   ├── signup/page.tsx
    │   │   ├── forgot-password/page.tsx
    │   │   ├── reset-password/[token]/page.tsx
    │   │   └── verify-email/[token]/page.tsx
    │   │
    │   └── (dashboard)/              # Protected pages (with sidebar)
    │       ├── layout.tsx            # AppShell with sidebar + topbar
    │       ├── page.tsx              # Dashboard home
    │       ├── workflows/
    │       │   ├── page.tsx          # Workflow list
    │       │   ├── new/page.tsx      # Blank canvas
    │       │   └── [id]/
    │       │       ├── page.tsx      # Workflow editor
    │       │       └── runs/
    │       │           ├── page.tsx  # Run history for this workflow
    │       │           └── [run_id]/page.tsx  # Execution detail
    │       ├── runs/page.tsx         # All runs across all workflows
    │       ├── templates/page.tsx    # Template gallery
    │       ├── schedules/page.tsx    # Scheduled workflows
    │       ├── logs/page.tsx         # Observability + log search
    │       └── settings/
    │           ├── profile/page.tsx
    │           ├── team/page.tsx
    │           ├── integrations/page.tsx
    │           └── billing/page.tsx
    │
    ├── components/
    │   ├── auth/                     # Auth forms
    │   ├── dashboard/                # Dashboard widgets
    │   ├── nodes/                    # React Flow custom node components
    │   │   ├── BaseNode.tsx          # Shared: port handles, status ring, glow
    │   │   ├── TriggerNode.tsx       # Orange, webhook/cron icon
    │   │   ├── AINode.tsx            # Purple, sparkle icon, cache indicator
    │   │   ├── APINode.tsx           # Green, globe icon, method badge
    │   │   ├── LogicNode.tsx         # Yellow, branch icon
    │   │   ├── TransformNode.tsx     # Teal, code icon, Monaco preview
    │   │   ├── MCPNode.tsx           # Blue, tool icon
    │   │   └── HumanNode.tsx         # Red, person icon
    │   ├── builder/                  # Workflow builder components
    │   │   ├── WorkflowCanvas.tsx    # React Flow canvas wrapper
    │   │   ├── NodePalette.tsx       # Left sidebar — draggable nodes
    │   │   ├── NodeConfigPanel.tsx   # Right sidebar — node configuration
    │   │   ├── EditorTopBar.tsx      # Save, Run, Version buttons
    │   │   ├── ValidationOverlay.tsx # Inline error bubbles on invalid nodes
    │   │   ├── RunInputModal.tsx     # Input form before triggering run
    │   │   └── DynamicConfigForm.tsx # JSON Schema → React form renderer
    │   ├── monitoring/               # Execution monitoring components
    │   ├── observability/            # Log viewer, metrics charts
    │   └── shared/                   # Reusable UI primitives
    │
    ├── hooks/
    │   ├── useWebSocket.ts           # WebSocket connection + event routing
    │   ├── useActiveRuns.ts          # Tenant-level run status stream
    │   ├── useAutoSave.ts            # Debounced workflow save
    │   └── useNodeSchema.ts          # Fetch + cache node config schemas
    │
    ├── stores/
    │   ├── authStore.ts              # Zustand — user, tenant, tokens, roles
    │   ├── workflowStore.ts          # Zustand — canvas nodes, edges, run state
    │   └── uiStore.ts                # Zustand — sidebar state, theme, panels
    │
    ├── api/                          # TanStack Query hooks + API client
    │   ├── client.ts                 # Axios instance with auth interceptor
    │   ├── workflows.ts              # useWorkflows, useWorkflow, useSaveWorkflow
    │   ├── executions.ts             # useTriggerExecution, useExecution
    │   ├── nodes.ts                  # useNodeTypes, useNodeSchema
    │   └── auth.ts                   # useLogin, useSignup, useRefreshToken
    │
    └── types/
        └── api.ts                    # TypeScript types matching SDK response schemas
```

---

## 4. Workflow Canvas — State Model

```typescript
// stores/workflowStore.ts

interface WorkflowStore {
  // Graph
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;

  // Persistence
  workflowId: string | null;
  workflowName: string;
  isDirty: boolean;
  lastSavedAt: Date | null;
  saveStatus: 'idle' | 'saving' | 'saved' | 'error';

  // Execution
  runId: string | null;
  runStatus: ExecutionStatus | null;
  nodeStatuses: Record<string, NodeStatus>;   // updated by WebSocket
  nodeLogs: Record<string, string[]>;         // updated by WebSocket

  // Actions
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  setSelectedNode: (id: string | null) => void;
  updateNodeConfig: (nodeId: string, config: Partial<NodeConfig>) => void;
  triggerSave: () => Promise<void>;
  triggerRun: (input: Record<string, unknown>) => Promise<string>;
  applyWebSocketEvent: (event: WsEvent) => void;
}
```

---

## 5. Node Status Visualization

```typescript
// Node/run statuses from RunStatus enum — these are the only valid values.
// There is no RETRYING, SKIPPED, or SUSPENDED status in the current implementation.
const nodeStatusStyles: Record<NodeStatus, NodeStyle> = {
  QUEUED:        { ring: 'ring-gray-300',   dot: 'bg-gray-400',   animate: null },
  RUNNING:       { ring: 'ring-blue-400',   dot: 'bg-blue-500',   animate: 'animate-pulse' },
  SUCCESS:       { ring: 'ring-green-400',  dot: 'bg-green-500',  animate: null },
  FAILED:        { ring: 'ring-red-400',    dot: 'bg-red-500',    animate: null },
  CANCELLED:     { ring: 'ring-gray-400',   dot: 'bg-gray-500',   animate: null },
  WAITING_HUMAN: { ring: 'ring-orange-400', dot: 'bg-orange-400', animate: 'animate-bounce' },
};
```

---

## 6. Authentication Flow

```
Access token (15 min)  → stored in React memory state (never localStorage)
Refresh token (7 days) → stored in HttpOnly cookie (not accessible to JS)

Auto-refresh:
  Axios interceptor catches 401
  → POST /auth/refresh (sends HttpOnly cookie automatically)
  → New access token stored in memory
  → Original request retried

Logout:
  Clear memory state (access token gone)
  POST /auth/logout (server expires HttpOnly cookie)
  Redirect to /login
```

---

## 7. WebSocket Event Schema

```typescript
// types/api.ts
// These match the exact payloads published by RunOrchestrator to
// Redis PubSub channel `run:{run_id}:events` and fanned out by the WS hub.

type WsEvent =
  | { type: 'node_state';        node_id: string; status: 'RUNNING' | 'SUCCESS' | 'FAILED'; ts: string }
  | { type: 'run_complete';      status: 'SUCCESS' | 'FAILED'; ts: string }
  | { type: 'run_waiting_human'; node_id: string; ts: string }
```

> **Event naming:** Types are lowercase snake_case. There is no `RUN_STARTED`, `NODE_LOG`, `HEARTBEAT`,
> or `HUMAN_WAITING` event in v1.0. The `node_state` event covers both node-started (status=RUNNING)
> and node-finished (status=SUCCESS or FAILED). `run_waiting_human` fires when a HumanInputNode
> pauses the run — the frontend should prompt the user to provide input via
> `POST /api/v1/executions/human-input`.

---

## 8. Dynamic Config Form — JSON Schema to React

Node configuration forms are generated automatically from the node's `config_schema` (JSON Schema). No hardcoded form per node type:

```typescript
// components/builder/DynamicConfigForm.tsx

const fieldRenderers: Record<string, React.FC<FieldProps>> = {
  string:   StringField,        // TextInput or Textarea based on x-widget annotation
  number:   NumberField,        // NumericInput with min/max
  boolean:  BooleanField,       // Toggle switch
  object:   ObjectField,        // Nested collapsible card
  array:    ArrayField,         // Dynamic list with add/remove
  // Custom x-widget annotations:
  'x-widget:model-picker':      ModelPickerField,    // Model selection with tier display
  'x-widget:prompt-editor':     PromptEditorField,   // Monaco with Jinja2 highlighting
  'x-widget:code-editor':       CodeEditorField,     // Monaco with Python highlighting
  'x-widget:connector-picker':  ConnectorPickerField,// Connector selection + OAuth
  'x-widget:cron-editor':       CronEditorField,     // Visual cron expression builder
};
```

---

## 9. Auto-Save Strategy

```
User makes any change to canvas
         │
         ▼
Zustand: isDirty = true, saveStatus = 'idle'
         │
         ▼
useAutoSave hook: debounce 2000ms
         │
         ▼
saveStatus = 'saving'
PUT /api/v1/workflows/{id} { name?: string, description?: string, definition?: WorkflowDefinition }
         │
    ┌────┴────┐
  success   failure
    │         │
saveStatus  saveStatus = 'error'
= 'saved'   show toast + manual save button
isDirty = false
```

Offline handling: changes queued in Zustand, flushed on reconnect.
