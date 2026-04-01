# Frontend Handover — Full Application UI/UX

> **Scope of this document.** Complete spec for every UI module in the application
> except the Chat-Driven DAG Builder, which is fully documented in
> `docs/frontend/chat-module.md`. Read that document alongside this one.
>
> **Related documents:**
> - `docs/frontend/overview.md` — tech stack, directory structure, workflowStore shape, auto-save, WebSocket schema
> - `docs/frontend/chat-module.md` — chat panel, ClarificationCard, streaming, DAG preview
> - `docs/frontend/handover.md` — schema corrections reference (authoritative node types, edge fields, API paths)
> - `docs/api/openapi.yaml` — single source of truth for all request/response schemas

---

## 1. Orientation

### What already exists in `docs/frontend/`

| Document | Covers |
|---|---|
| `overview.md` | Tech stack lock, full directory tree, workflowStore, node status styles, auth token flow, auto-save, WebSocket event types |
| `chat-module.md` | chatStore, useChatWebSocket, all chat components, ClarificationCard, ChatGeneratedNode, loadFromDefinition() |
| `handover.md` | Correct API paths, 17 node types table, edge schema, schema corrections from template |

### What this document adds

| Module | Route(s) | Section |
|---|---|---|
| Auth pages | `/login`, `/signup`, `/forgot-password`, `/reset-password/[token]`, `/verify-email/[token]` | §3 |
| App shell | All `(dashboard)` routes | §4 |
| Workflow dashboard | `/workflows` | §5 |
| Workflow canvas editor | `/workflows/[id]` | §6 |
| Node config panels | (panel inside editor) | §7 |
| Execution monitor | `/workflows/[id]/runs`, `/runs` | §8 |
| Log viewer | `/workflows/[id]/runs/[run_id]` | §9 |
| Settings — profile | `/settings/profile` | §10 |
| Settings — team | `/settings/team` | §11 |
| Settings — integrations | `/settings/integrations` | §12 |
| Settings — billing | `/settings/billing` | §13 |
| Templates gallery | `/templates` | §14 |
| Schedules | `/schedules` | §15 |
| Cross-cutting concerns | All modules | §16 |
| API integration map | All modules | §17 |

---

## 2. Design System

### 2.1 Colour Tokens

```css
/* tailwind.config.ts — extend theme.colors */

brand: {
  50:  '#f0f4ff',
  100: '#e0e9ff',
  500: '#6366f1',   /* primary actions */
  600: '#4f46e5',   /* hover */
  700: '#4338ca',   /* pressed */
}

/* Node category colours — matches ui_config.color from backend */
node: {
  ai:        '#6366f1',   /* ai_reasoning */
  data:      '#3b82f6',   /* execution_data */
  mgmt:      '#10b981',   /* workflow_management */
  logic:     '#f97316',   /* logic_orchestration */
  trigger:   '#22c55e',   /* triggers */
}

/* Execution status colours */
status: {
  queued:   '#94a3b8',
  running:  '#3b82f6',
  success:  '#22c55e',
  failed:   '#ef4444',
  waiting:  '#f97316',
  cancelled:'#64748b',
}
```

### 2.2 Typography

```
Font family: Inter (sans-serif fallback system-ui)
Code/Monaco: JetBrains Mono (fallback monospace)

Scale:
  xs  — 11px / line-height 16px   (badges, metadata)
  sm  — 13px / 20px               (sidebar items, table cells)
  base— 14px / 20px               (body)
  lg  — 16px / 24px               (panel headings)
  xl  — 18px / 28px               (page titles)
  2xl — 22px / 32px               (hero / modal headings)
```

### 2.3 Spacing & Layout Constants

```
Topbar height:        56px
Sidebar expanded:    240px
Sidebar collapsed:    48px
Config panel width:  380px   (overlaps canvas — does NOT shrink it)
Chat panel width:    380px   (collapsible to 48px)
Node palette width:  240px
Modal max-width:     560px   (standard) / 780px (wide, e.g. version history)
Drawer width:        480px
Page horizontal pad:  32px
Card border-radius:    8px
```

### 2.4 shadcn/ui Component Defaults

Use shadcn/ui primitives for all common UI. Do not build custom alternatives:
- Buttons → `Button` (variants: default / outline / ghost / destructive)
- Inputs → `Input`, `Textarea`, `Select`, `Switch`, `Checkbox`, `RadioGroup`
- Feedback → `Toast` (sonner), `AlertDialog` (destructive confirmations)
- Navigation → `Tabs`, `DropdownMenu`, `ContextMenu`
- Overlay → `Dialog`, `Sheet` (drawer), `Popover`, `Tooltip`
- Data → `Table`, `Badge`, `Avatar`, `Skeleton`
- Forms → React Hook Form + Zod; bind via `useForm` + `zodResolver`

---

## 3. Auth Module

> **Route group:** `app/(auth)/` — no sidebar, centred card layout, dark-mode aware.

### 3.1 Page Map

| Page | Route | API call |
|---|---|---|
| Login | `/login` | `POST /auth/login` |
| Register | `/signup` | `POST /auth/register` |
| MFA Verify | `/login` (step 2 overlay) | `POST /auth/mfa/verify` |
| Forgot Password | `/forgot-password` | `POST /auth/password/reset-request` |
| Reset Password | `/reset-password/[token]` | `POST /auth/password/reset` |
| Verify Email | `/verify-email/[token]` | `POST /auth/email/verify` |

### 3.2 Login Page

**Layout:** Centred card (400px wide) on a dark gradient background. Logo top of card.

**Form fields:**
- `email` — type email, required, autofocus
- `password` — type password, required, min 8 chars, show/hide toggle
- `Remember me` — checkbox (extends session — UI only, no API effect in v1)
- Submit: `Sign in` button (full width, primary)
- Link below: `Forgot password?` → `/forgot-password`
- Separator: `or`
- Google OAuth button: `Continue with Google` → `GET /auth/oauth/google`
- Footer link: `Don't have an account? Sign up` → `/signup`

**MFA step (inline — not a separate page):**
When `POST /auth/login` returns HTTP 200 with `mfa_required: true`, replace the form with:
- 6-digit TOTP input — auto-advance on 6th digit
- `Verify` button
- `Back` link clears the step
- API call: `POST /auth/mfa/verify` with `{ totp_code }`

**Error handling:**
- HTTP 401 → `"Invalid email or password"` inline below password field
- HTTP 429 → `"Too many attempts. Try again in 60 seconds."` with countdown timer
- Network error → Toast: `"Connection error — check your internet connection"`

**On success:** Store `access_token` in memory (`authStore.setToken(token)`), redirect to `/workflows`.

### 3.3 Register Page

**Form fields:**
- `name` — text, required
- `email` — email, required
- `password` — password, min 8 chars, strength indicator (weak / fair / strong)
- `tenant_name` — text, required, placeholder `"Your company or project name"`
- Terms checkbox: `"I agree to the Terms of Service and Privacy Policy"`
- Submit: `Create account`
- Footer: `Already have an account? Sign in` → `/login`

**Schema (`RegisterRequest`):**
```typescript
{ email: string; password: string; name: string; tenant_name: string }
```

**On success:** Show email verification banner, redirect to `/workflows` with toast `"Check your email to verify your account"`.

### 3.4 Forgot / Reset Password

**Forgot (`/forgot-password`):** Single email field. On submit → `POST /auth/password/reset-request`. Show confirmation message regardless of whether email exists (prevents enumeration). Link back to login.

**Reset (`/reset-password/[token]`):** Two fields — `new_password` + `confirm_password` (client-side match validation). On success → redirect to `/login` with toast `"Password updated — please sign in"`.

### 3.5 Auth Store Shape

```typescript
// stores/authStore.ts
interface AuthStore {
  user: User | null            // from /users/me after login
  accessToken: string | null   // memory only — never persisted
  isAuthenticated: boolean
  isLoading: boolean

  setToken: (token: string) => void
  setUser: (user: User) => void
  clearAuth: () => void
}
```

Axios interceptor in `api/client.ts`:
```typescript
// On every request: add Authorization header from authStore.accessToken
// On 401 response: POST /auth/token/refresh (sends HttpOnly cookie)
//   → success: store new access_token, retry original request
//   → failure: clearAuth() + redirect to /login
```

---

## 4. App Shell

> **Route group:** `app/(dashboard)/layout.tsx` — wraps all authenticated pages.

### 4.1 Layout Structure

```
┌── TopBar (56px, full width) ──────────────────────────────────────────────┐
│  [logo 32px]  [breadcrumb]              [run-status pill] [notif] [user]  │
├── Sidebar (240px / 48px) ──┬── Main Content (flex-1) ─────────────────────┤
│                             │                                               │
│  Navigation items           │  <children />                                 │
│                             │                                               │
│  [collapse toggle]          │                                               │
└─────────────────────────────┴───────────────────────────────────────────────┘
```

Config panel and chat panel overlay inside specific children — they never affect the shell.

### 4.2 Sidebar Navigation

```
[DK Logo]

MAIN
  Workflows         /workflows          icon: layout-grid
  Runs              /runs               icon: activity
  Templates         /templates          icon: copy
  Schedules         /schedules          icon: clock

SETTINGS
  Settings          /settings/profile   icon: settings
  Billing           /settings/billing   icon: credit-card

WORKSPACE
  [TenantSwitcher dropdown]
```

Active item: `bg-brand-50 text-brand-600 font-medium`.
Collapsed state (48px): show only icons, no labels. Tooltip on hover shows label.
Collapse toggle: chevron button at bottom of sidebar, persisted in `uiStore.sidebarCollapsed`.

### 4.3 TopBar

**Breadcrumb:** Auto-generated from route segments. Examples:
- `/workflows` → `Workflows`
- `/workflows/wf_abc` → `Workflows / My Workflow Name`
- `/workflows/wf_abc/runs/run_xyz` → `Workflows / My Workflow Name / Run #42`

**Run status pill:** Shows active runs for the tenant. Clicking opens a popover with the last 5 runs. Driven by `useActiveRuns` hook (polls `GET /executions?status=RUNNING&page_size=5` every 10s).

**Notifications bell:** In v1, badge shows count of WAITING_HUMAN runs. Clicking opens a Sheet listing them.

**User menu (avatar + name):**
```
  [Avatar]  User Name ▾
  ─────────────────────
  Profile           /settings/profile
  Team              /settings/team
  Billing           /settings/billing
  ─────────────────────
  Sign out          → POST /auth/logout + clearAuth()
```

### 4.4 uiStore Shape

```typescript
// stores/uiStore.ts
interface UIStore {
  sidebarCollapsed: boolean
  activeRunIds: string[]          // tenant-level active run IDs
  theme: 'light' | 'dark' | 'system'

  toggleSidebar: () => void
  setActiveRuns: (ids: string[]) => void
}
```

---

## 5. Workflow Dashboard

**Route:** `/workflows`
**API:** `GET /v1/workflows?page=1&page_size=20&search=&tags=&is_active=`

### 5.1 Page Layout

```
┌── Page header ──────────────────────────────────────────────────────┐
│  Workflows                    [Search input]  [Filter ▾] [+ New]    │
├── Workflow cards grid (3 col) ──────────────────────────────────────┤
│  [WorkflowCard] [WorkflowCard] [WorkflowCard]                       │
│  [WorkflowCard] [WorkflowCard] [WorkflowCard]                       │
│  ...                                                                 │
├── Pagination ───────────────────────────────────────────────────────┤
│                          < 1 2 3 ... >                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 WorkflowCard

```
┌─────────────────────────────────────┐
│  [Trigger icon]  My Workflow Name   [⋮ menu]
│  ─────────────────────────────────  │
│  Last run: 2 hours ago — SUCCESS ●  │
│  3 nodes  •  webhook trigger        │
│  ─────────────────────────────────  │
│  [Run ▶]              [Edit →]      │
└─────────────────────────────────────┘
```

Fields from `WorkflowSummary`:
- `metadata.name` — title
- `metadata.description` — truncated to 2 lines
- `metadata.tags` — tag badges (max 3 shown, `+N more` chip)
- `metadata.is_active` — green/grey dot indicator
- `updated_at` — relative timestamp (`2 hours ago`)
- Last run status: fetched from `GET /v1/executions?workflow_id=&page_size=1&sort=started_at:desc`

**Context menu (⋮):**
- Edit → `/workflows/[id]`
- Duplicate → `POST /v1/workflows` with cloned definition (client-side)
- View runs → `/workflows/[id]/runs`
- Activate / Deactivate → `POST /v1/workflows/[id]/activate`
- Delete → `DELETE /v1/workflows/[id]` (AlertDialog confirmation)

**New workflow button:** Opens a modal with two options:
1. **Start with AI** — navigates to `/workflows/new` (chat-first, G-6 flow)
2. **Blank canvas** — `POST /v1/workflows` with empty definition, navigate to `/workflows/[id]`

### 5.3 Filter Panel

Dropdown from `Filter` button:
- Tags multiselect (autocomplete from existing tags)
- Status: All / Active / Inactive
- Trigger type: All / Manual / Scheduled / Webhook
- Sort: Last modified / Created / Name (A-Z)

All filters drive query params — shareable URLs.

### 5.4 Empty State

```
[illustration: empty canvas]
No workflows yet
Create your first workflow with AI chat or start from a blank canvas.
  [Start with AI]   [Blank canvas]
```

### 5.5 TanStack Query Hooks

```typescript
// api/workflows.ts

useWorkflows(params)         // GET /v1/workflows — paginated list
useCreateWorkflow()          // POST /v1/workflows
useDeleteWorkflow()          // DELETE /v1/workflows/{id}
useActivateWorkflow()        // POST /v1/workflows/{id}/activate
```

---

## 6. Workflow Canvas Editor

**Route:** `/workflows/[id]`
**The most complex page in the application.**

### 6.1 Three-Panel Layout

```
┌── EditorTopBar (56px) ────────────────────────────────────────────────────┐
│  ← Workflows / [name] (editable)  [Undo] [Redo]  [●Saving] [Run ▶] [Pub]│
├── NodePalette ────┬── WorkflowCanvas (flex-1) ──── (ConfigPanel overlay) ─┤
│  (240px)          │                                  (380px, right edge)   │
│  [Palette items]  │  React Flow canvas               [NodeConfigPanel]     │
│                   │  (pan, zoom, connect)             (slides in on select)│
└───────────────────┴──────────────────────────────────────────────────────  ┘
```

ConfigPanel overlaps canvas with drop shadow — it does **not** shrink the canvas.

### 6.2 EditorTopBar

- **Back arrow** → `/workflows` (with unsaved-changes guard)
- **Workflow name** — inline editable (click to edit, blur to save)
- **Undo / Redo** — driven by `workflowStore` history (immer patches)
- **Save status indicator:**
  - Idle: no indicator
  - Saving: `● Saving…` (grey spinner dot)
  - Saved: `✓ Saved` (green, fades after 2s)
  - Error: `⚠ Save failed` (red, persistent, click to retry)
- **Run ▶ button** → opens `RunInputModal` then `POST /v1/workflows/{id}/trigger`
- **Publish button** → `PUT /v1/workflows/{id}` with `publish: true`, opens version note modal

### 6.3 NodePalette

Left sidebar. Nodes grouped by category. Each item is a **draggable chip** — drag onto canvas to add node.

```
TRIGGERS
  [▶ Manual]   [⏱ Scheduled]   [⚡ Webhook]

AI & REASONING
  [✦ AI Prompt]   [🤖 Agent]   [🔍 Semantic Search]

EXECUTION & DATA
  [</> Run Code]   [🌐 HTTP Request]   [📄 Template]
  [🔍 Web Search]  [🔌 MCP Tool]

WORKFLOW MANAGEMENT
  [🗄 Set State]   [🔧 Custom]   [📝 Note]   [→ Output]

LOGIC & ORCHESTRATION
  [⑂ Control Flow]   [⊟ Sub-Workflow]
```

Each chip shows:
- Category colour dot
- Lucide icon (from `handover.md` §4 icon column)
- Display label

**Search box** at top of palette filters by name.

### 6.4 WorkflowCanvas

Built with React Flow v12. Key implementation notes:

**Initialisation:**
```typescript
// On mount: GET /v1/workflows/{id}
// workflowStore.loadFromDefinition(workflow.definition)
// Restore viewport from ui_metadata.viewport
```

**Node types registered:**
```typescript
const nodeTypes = {
  prompt:              AINode,
  agent:               AINode,
  semantic_search:     AINode,
  code_execution:      TransformNode,
  api_request:         APINode,
  templating:          TransformNode,
  web_search:          APINode,
  mcp:                 MCPNode,
  set_state:           BaseNode,
  custom:              BaseNode,
  note:                NoteNode,
  output:              OutputNode,
  control_flow:        LogicNode,
  subworkflow:         BaseNode,
  manual_trigger:      TriggerNode,
  scheduled_trigger:   TriggerNode,
  integration_trigger: TriggerNode,
}
```

**BaseNode component** (all others extend this):
```
┌── node header (8px height, background = ui_config.color) ──────────────┐
│  [Lucide icon 14px]  [node_type_label]           [status dot]          │
├── node body ────────────────────────────────────────────────────────────┤
│  Node label (user-editable, defaults to type label)                     │
│  [config preview — 2 key fields shown as pills]                         │
└─────────────────────────────────────────────────────────────────────────┘
  [input port ●]                                       [output port ●]
```

Port handles:
- All nodes: `input` handle (left, except triggers)
- `control_flow` node: `output` handle + `true` + `false` handles (right side, labelled)
- `is_terminal: true` nodes: no output handle rendered

**Connection rules (client-side validation before API call):**
- Cannot connect a node to itself
- Cannot create duplicate edges (same source_port → same target_port)
- Trigger nodes have no input handle

**Canvas events:**
- `onNodeClick` → `workflowStore.setSelectedNode(id)` → slides ConfigPanel open
- `onPaneClick` → `workflowStore.setSelectedNode(null)` → closes ConfigPanel
- `onConnect` → adds edge to store → debounced auto-save
- `onNodesChange` (drag) → updates positions → debounced auto-save
- `onEdgesDelete` → removes edge → debounced auto-save

**Auto-save:** Debounced 2000ms after any change → `PUT /v1/workflows/{id}` with full `WorkflowUpdate` body. See `overview.md §9` for the full state machine.

**Validation overlay:** After save, backend returns validation errors. Invalid nodes get a red ring + error tooltip. Invalid edges highlighted red. Errors cleared on next successful save.

### 6.5 RunInputModal

Opens when user clicks Run:

```
┌─ Trigger Workflow ────────────────────────────┐
│                                               │
│  Workflow: My Workflow Name                   │
│                                               │
│  Input payload (JSON):                        │
│  ┌─────────────────────────────────────────┐  │
│  │ {                                       │  │
│  │   "key": "value"                        │  │
│  │ }                                       │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  Version: ● Latest  ○ Pinned [select]         │
│                                               │
│           [Cancel]   [Run workflow ▶]          │
└───────────────────────────────────────────────┘
```

On Run → `POST /v1/workflows/{id}/trigger` → navigate to run detail page.

### 6.6 Version History Panel

Triggered by `History` button in EditorTopBar (secondary action). Opens a Sheet (right drawer):
- `GET /v1/workflows/{id}/versions` — lists `WorkflowVersionSummary[]`
- Each row: version number, created by, date, change summary
- `Restore` button → `GET /v1/workflows/{id}/versions/{version_id}` → load definition into canvas (with unsaved-changes guard)

---

## 7. Node Config Panel

**Location:** 380px panel that slides in from the right edge of the canvas when a node is selected. Overlaps canvas (does not shrink it).

### 7.1 Panel Structure

```
┌── Panel header ────────────────────────────────────┐
│  [category colour bar, 4px]                        │
│  [Lucide icon]  Node Type Label        [✕ close]   │
│  [editable node display name]                      │
│  [is_editable = false → read-only banner]          │
├────────────────────────────────────────────────────┤
│  [Form] [Code]  ← toggle                          │
├── Config form (scrollable) ─────────────────────────┤
│  <DynamicConfigForm nodeType={type} config={config}│
│    onChange={updateNodeConfig} />                  │
├── Output preview (collapsed by default) ────────────┤
│  Last run output: {...}                            │
│  duration: 234ms  isolation_tier: 2               │
└────────────────────────────────────────────────────┘
```

`is_editable` comes from `ui_config.editable`. When `false`, entire form is read-only and a banner reads `"This node was configured by the AI — edit carefully"`.

### 7.2 Config Forms by Node Type

All forms are generated by `DynamicConfigForm` from the node's JSON Schema config. Below are the key fields per type — implement as custom field renderers (registered via `x-widget` annotation):

#### `prompt` — AI Prompt

| Field | Widget | Notes |
|---|---|---|
| `model` | `ModelPickerField` | Grouped by provider: Gemini, OpenAI, Anthropic |
| `prompt_template` | `PromptEditorField` | Monaco with Jinja2 `{{ variable }}` highlighting |
| `system_prompt` | `PromptEditorField` | Collapsible (optional) |
| `temperature` | Slider (0–2) + number input | |
| `max_tokens` | NumberField | |
| `output_key` | StringField | Variable name downstream nodes reference |

#### `agent` — AI Agent

| Field | Widget |
|---|---|
| `model` | `ModelPickerField` |
| `instructions` | `PromptEditorField` (multi-line) |
| `tools` | CheckboxGroup — list of available MCP tools |
| `max_iterations` | NumberField (default 10) |
| `output_key` | StringField |

#### `semantic_search` — Semantic Search

| Field | Widget |
|---|---|
| `query_template` | `PromptEditorField` |
| `collection` | Select (from tenant's vector collections) |
| `top_k` | NumberField |
| `score_threshold` | Slider (0–1) |
| `output_key` | StringField |

#### `code_execution` — Run Code

| Field | Widget | Notes |
|---|---|---|
| `code` | `CodeEditorField` | Monaco, Python syntax |
| `isolation_tier` | RadioGroup `1 / 2 / 3` | Tier 2/3 show gVisor badge |
| `timeout_seconds` | NumberField |  |
| `packages` | TagInput | e.g. `pandas, requests` |
| `output_key` | StringField |

Show read-only warning: `"Code runs in an isolated gVisor container. os, subprocess, socket are blocked at Tier 2+."`

#### `api_request` — HTTP Request

| Field | Widget |
|---|---|
| `method` | Select: GET / POST / PUT / PATCH / DELETE |
| `url` | StringField (supports `{{ variable }}`) |
| `headers` | KeyValueTable |
| `body` | `CodeEditorField` (JSON mode) |
| `auth_type` | Select: None / Bearer / API Key / Basic |
| `credential_ref` | `ConnectorPickerField` (when auth_type ≠ None) |
| `timeout_seconds` | NumberField |
| `output_key` | StringField |

#### `templating` — Template

| Field | Widget |
|---|---|
| `template` | `PromptEditorField` (Jinja2 mode) |
| `output_format` | Select: text / json / html |
| `output_key` | StringField |

#### `web_search` — Web Search

| Field | Widget |
|---|---|
| `query_template` | StringField |
| `engine` | Select: google / bing / serpapi |
| `result_count` | NumberField |
| `output_key` | StringField |

#### `mcp` — MCP Tool

| Field | Widget |
|---|---|
| `server_id` | `ConnectorPickerField` (filtered to MCP servers) |
| `tool_name` | Select (populated after server_id chosen) |
| `input_mapping` | KeyValueTable (maps node inputs → tool args) |
| `output_key` | StringField |

#### `control_flow` — Control Flow

| Field | Widget | Notes |
|---|---|---|
| `condition` | `CodeEditorField` (Python expression) | e.g. `input.score > 0.8` |
| `true_label` | StringField | Label on the `true` edge |
| `false_label` | StringField | Label on the `false` edge |

Canvas renders 3 output handles: `output`, `true`, `false`.

#### `manual_trigger` — Manual Trigger

| Field | Widget |
|---|---|
| `input_schema` | JSON Schema editor (Monaco) |

#### `scheduled_trigger` — Scheduled

| Field | Widget |
|---|---|
| `cron_expression` | `CronEditorField` (visual builder + raw expression) |
| `timezone` | TimezoneSelect (IANA) |
| `trigger_input` | `CodeEditorField` (static JSON payload) |

#### `integration_trigger` — Webhook

| Field | Widget | Notes |
|---|---|---|
| `webhook_url` | Read-only text + copy button | Auto-generated, shown after save |
| `secret` | Read-only masked text + reveal | HMAC signing secret |
| `payload_schema` | JSON Schema editor | Optional validation |

#### `set_state`, `custom`, `note`, `output`, `subworkflow`

- `set_state`: `key` (StringField) + `value` (CodeEditorField)
- `custom`: `handler_module` (StringField) + `config` (CodeEditorField, JSON)
- `note`: `text` (Textarea) — cosmetic only, no execution
- `output`: `output_key` (StringField) + `transform` (optional CodeEditorField)
- `subworkflow`: `workflow_id` (WorkflowPickerField — searchable list of `/v1/workflows`) + `input_mapping` (KeyValueTable)

### 7.3 ModelPickerField Component

```
┌── Model picker ─────────────────────────────────────────────────┐
│  [Google Gemini ▾]                                              │
│  ┌── Dropdown ──────────────────────────────────────────────┐   │
│  │  GOOGLE GEMINI                                           │   │
│  │    gemini-2.0-flash       Fast · Cheap   [default badge] │   │
│  │    gemini-1.5-pro         Balanced                       │   │
│  │  OPENAI                                                  │   │
│  │    gpt-4o                 Best · Expensive               │   │
│  │    gpt-4o-mini            Fast · Cheap                   │   │
│  │  ANTHROPIC                                               │   │
│  │    claude-sonnet-4-6      Balanced                       │   │
│  │    claude-haiku-4-5       Fast · Cheap                   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

Default model: `gemini-2.0-flash` (matches backend `prompt.py` default).

### 7.4 ConnectorPickerField Component

Calls `GET /v1/integrations/connections` (filtered by type). Shows provider logo + connection name + status dot. `+ Add connection` link opens the integrations settings page in a new tab.

---

## 8. Execution Monitor

### 8.1 Run List — `/workflows/[id]/runs` and `/runs`

**API:** `GET /v1/executions?workflow_id=[id]&page=1&page_size=20&status=`

**Table layout:**

| Column | Source | Notes |
|---|---|---|
| Run ID | `run_id` | Truncated, click to detail |
| Status | `status` | Coloured badge |
| Triggered | `started_at` | Relative + absolute on hover |
| Duration | `ended_at - started_at` | Shown only when ended |
| Version | `version_no` | |
| Actions | — | Cancel button (only for RUNNING/QUEUED) |

**Status badge colours** (from design system §2.1):
- `QUEUED` → grey
- `RUNNING` → blue + `animate-pulse`
- `SUCCESS` → green
- `FAILED` → red
- `CANCELLED` → slate
- `WAITING_HUMAN` → orange + `animate-bounce`

**Filter bar:**
- Status multi-select
- Date range picker
- Search by run_id

**Cancel run:** `POST /v1/executions/{run_id}/cancel` — show AlertDialog: `"Cancel this run? The workflow will stop at the next node boundary."`

### 8.2 Run Detail — `/workflows/[id]/runs/[run_id]`

Split layout:

```
┌── RunDetailTopBar ──────────────────────────────────────────────────────────┐
│  Run #42 — SUCCESS ●        started 14:23:01   duration 4.2s   [Cancel]   │
├── Run Graph (flex-1, 60%) ──────────┬── LogPanel (40%) ────────────────────┤
│                                     │                                       │
│  React Flow (read-only)             │  [ALL] [INFO] [WARN] [ERROR]         │
│  Each node shows live status        │  ──────────────────────────────────  │
│  ring colour from nodeStatuses      │  14:23:01.012 INFO  prompt_1         │
│                                     │    "LLM called with 312 tokens"      │
│  Click node → detail popover:       │  14:23:01.234 INFO  prompt_1         │
│    - input / output JSON            │    "Response: ..."                   │
│    - duration_ms                    │  14:23:02.511 ERROR api_1             │
│    - isolation_tier badge           │    "HTTP 500 from upstream"          │
│    - error_message (if FAILED)      │                                       │
│                                     │  [↓ Follow tail]  [↑ Scroll top]     │
└─────────────────────────────────────┴───────────────────────────────────────┘
```

**Live updates via WebSocket:**
```typescript
// hooks/useExecutionWebSocket.ts
// WS /ws/executions/{run_id}
// Routes events → workflowStore.applyWebSocketEvent(event)
// NODE_STARTED  → nodeStatuses[node_id] = RUNNING
// NODE_COMPLETED→ nodeStatuses[node_id] = SUCCESS/FAILED/SKIPPED
// NODE_FAILED   → nodeStatuses[node_id] = FAILED, show error ring
// NODE_LOG      → append to logStream[]
// HUMAN_WAITING → open HumanInputModal
// RUN_COMPLETED → update run status, stop WebSocket
// HEARTBEAT     → no-op (resets reconnect timer)
```

**Run graph:** Uses the same React Flow canvas as the editor but:
- `nodesDraggable: false`
- `nodesConnectable: false`
- `elementsSelectable: true` (for node click → popover)
- Loads `GET /v1/executions/{run_id}/nodes` for initial node states
- Then overlays live updates from WebSocket

**Node status ring** (from `overview.md §5`):
```
PENDING   → ring-gray-300
RUNNING   → ring-blue-400 + animate-pulse
SUCCESS   → ring-green-400
FAILED    → ring-red-400
SKIPPED   → ring-gray-200 opacity-50
SUSPENDED → ring-orange-400 + animate-bounce
```

**Log panel:**
- Source: WebSocket `NODE_LOG` events (live) + `GET /v1/executions/{run_id}/logs` (initial load)
- Log entry structure: `{ timestamp, level, node_id, message }`
- Level filter tabs: ALL / INFO / WARN / ERROR
- Auto-scroll to bottom toggle
- `LogEntry.level` colour:
  - `INFO` → slate text
  - `WARN` → amber text
  - `ERROR` → red text, bold

### 8.3 HUMAN_WAITING — Human Input Modal

When WebSocket emits `HUMAN_WAITING`:

```
┌─ Human Input Required ──────────────────────────────┐
│  Node: approval_gate                               │
│  ─────────────────────────────────────────────────  │
│  [DynamicForm rendered from event.form_schema]     │
│                                                     │
│  [Reject ✗]                    [Approve ✓ Continue] │
└─────────────────────────────────────────────────────┘
```

Submit → `POST /v1/executions/{run_id}/human-input` with `{ run_id, node_id, response, approved }`.

---

## 9. Log Viewer

**Already covered within Run Detail (§8.2 Log Panel).** Accessible standalone at `/workflows/[id]/runs/[run_id]` (same page — the log panel is always visible in the split layout).

For a full-screen log view (e.g. when reached from sidebar `Runs`):
- Route: `/runs/[run_id]` — same page but without the workflow context, shows run graph full-width at top and log panel below
- `GET /v1/executions/{run_id}/logs?level=&node_id=&page=1` for historic logs with server-side filtering

---

## 10. Settings — Profile

**Route:** `/settings/profile`
**API:** `GET /v1/users/me`, `PUT /v1/users/{id}`

### Page Layout

```
┌── Profile ──────────────────────────────────────────────────┐
│  Personal Information                                        │
│  ┌─ Avatar ─┐  Name: [______________]                       │
│  │  [img]   │  Email: user@example.com  [Verified ✓]        │
│  │ [Change] │  Role: EDITOR (read-only)                     │
│  └──────────┘                                               │
│  [Save changes]                                             │
│  ─────────────────────────────────────────────────────────  │
│  Password                                                   │
│  Current: [__________]                                      │
│  New:      [__________]  Confirm: [__________]              │
│  [Update password]                                          │
│  ─────────────────────────────────────────────────────────  │
│  Two-Factor Authentication                                  │
│  [MFA enabled ✓]  [Disable 2FA]                            │
│  (or if disabled:)                                         │
│  [Enable 2FA] → QR code modal with TOTP secret              │
└─────────────────────────────────────────────────────────────┘
```

**MFA enable flow:**
1. `POST /auth/mfa/setup` → returns `{ qr_uri, secret }` (`MfaSetupResponse`)
2. Modal shows QR code (rendered from `qr_uri` using a QR library)
3. User scans, enters TOTP code
4. `POST /auth/mfa/verify` with `{ totp_code }`
5. On success: show backup codes modal, update profile UI

---

## 11. Settings — Team

**Route:** `/settings/team`
**API:** `GET /v1/users`, `POST /v1/users/invite`, `PUT /v1/users/{id}`, `DELETE /v1/users/{id}`
**Visible to:** ADMIN and OWNER roles only. EDITOR/VIEWER see read-only view.

### Page Layout

```
┌── Team ─────────────────────────────────────────────────────┐
│  Team Members                       [Invite member]         │
│  ─────────────────────────────────────────────────────────  │
│  [Avatar] Alice Smith     alice@example.com  OWNER    [⋮]  │
│  [Avatar] Bob Jones       bob@example.com    EDITOR   [⋮]  │
│  [Avatar] Carol Wu        carol@example.com  VIEWER   [⋮]  │
│  ─────────────────────────────────────────────────────────  │
│  Pending Invites                                            │
│  dave@example.com                  EDITOR   [Resend] [✕]   │
└─────────────────────────────────────────────────────────────┘
```

**Invite member modal:**
- Email field
- Role select: EDITOR / VIEWER (ADMIN cannot be invited — must be promoted)
- `POST /v1/users/invite` with `{ email, role }`

**Context menu (⋮) per member:**
- Change role → inline Select
- Remove from team → `DELETE /v1/users/{id}` with AlertDialog

**Role pills:**
- `OWNER` → purple badge (cannot be changed or removed)
- `ADMIN` → red badge
- `EDITOR` → blue badge
- `VIEWER` → grey badge

---

## 12. Settings — Integrations

**Route:** `/settings/integrations`
**Tab structure:** API Keys | Webhooks | Connections | OAuth Apps

### 12.1 API Keys Tab

**API:** `GET /v1/api-keys`, `POST /v1/api-keys`, `DELETE /v1/api-keys/{id}`

```
API Keys                                     [+ Create API key]

wfk_01JR...  My Integration Key   workflows:read  created 3 days ago  [✕ Revoke]
wfk_02JR...  CI Pipeline          executions:trigger               [✕ Revoke]
```

**Create API key modal:**
```
Name:   [_____________________________]
Scopes: ☑ workflows:read   ☐ workflows:write
        ☑ executions:read  ☑ executions:trigger
        ☐ executions:write ☐ logs:read
Expires: ○ Never  ● On date [date picker]
[Create]
```

**After creation:** Show the full key once in a modal with copy button and a bold warning: `"This key will not be shown again. Store it securely."`
(`ApiKeyCreated.key` — returned only on creation, field `key`.)

### 12.2 Webhooks Tab

**API:** `GET /v1/webhooks`, `POST /v1/webhooks`, `PUT /v1/webhooks/{id}`, `DELETE /v1/webhooks/{id}`

Table:
- Name, events (badges), target URL, status (active/inactive), last triggered

Create webhook drawer (Sheet):
- Name, target URL, events checkboxes (execution.started / succeeded / failed / cancelled / human_input.required)
- HMAC secret: auto-generated by backend, shown once on creation with copy

### 12.3 Connections Tab (OAuth / Credentials)

Lists third-party connections (Google, Slack, etc.) for use in `api_request`, `mcp` nodes.

Each row:
- Provider logo + name
- Connected account (email / workspace name)
- Status: Active / Expired / Error
- Actions: Reconnect / Remove

`+ Add connection` → OAuth redirect to provider.

---

## 13. Settings — Billing

**Route:** `/settings/billing`
**API:** `GET /v1/usage/summary`, `GET /v1/billing/plan`
**Visible to:** ADMIN and OWNER roles only.

### Page Layout

```
┌── Billing ──────────────────────────────────────────────────────────────┐
│  Current Plan: Pro  •  Next billing: April 1, 2026                      │
│  [Upgrade]  [Manage billing]                                             │
│  ─────────────────────────────────────────────────────────────────────  │
│  Usage — March 2026                                                      │
│                                                                          │
│  Executions        342 / 1,000    ████████░░░░░░  34%                   │
│  LLM Tokens        89,234 / 500k  ████░░░░░░░░░░  18%                   │
│  Compute Seconds   1,204 / 10,000 ██░░░░░░░░░░░░  12%                   │
│  ─────────────────────────────────────────────────────────────────────  │
│  Cost Breakdown (Recharts stacked bar — last 12 months)                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  $  │▓▓▓▒░│▓▓▓▒░│▓▓▓░│▓▓░│▓▓░│▓░│▓░│▓░│▓░│▓░│▓░│▓░│           │   │
│  │     │ Apr  May  Jun  Jul  Aug  ...                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ■ Executions   ■ LLM tokens   ■ Compute                               │
│  ─────────────────────────────────────────────────────────────────────  │
│  [Export CSV]           period selector: [This month ▾]                 │
└─────────────────────────────────────────────────────────────────────────┘
```

**Data sources:**
- `UsageSummary` schema: `execution_count`, `total_input_tokens`, `total_output_tokens`, `total_compute_secs`, `total_cost_usd`
- Chart data: `GET /v1/usage/summary?period=monthly&months=12`

**CSV export:** Downloads a CSV of the `UsageSummary` array for the selected period.

---

## 14. Templates Gallery

**Route:** `/templates`
**Purpose:** Browse pre-built workflow templates. Fork into tenant's workspace.

```
┌── Templates ─────────────────────────────────────────────────────────────┐
│  [🔍 Search templates]                  [Category ▾]  [Sort ▾]          │
│  ─────────────────────────────────────────────────────────────────────  │
│  ┌── TemplateCard ──────┐  ┌── TemplateCard ──────┐                     │
│  │ ✦ AI Email Drafter   │  │ 🌐 API + Transform    │                     │
│  │ Drafts email replies  │  │ Fetch and summarise   │                     │
│  │ using LLM             │  │ any REST endpoint     │                     │
│  │ 4 nodes  • prompt     │  │ 3 nodes  • api_request│                     │
│  │ [Preview] [Use this ▶]│  │ [Preview] [Use this ▶]│                     │
│  └──────────────────────┘  └──────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

**TemplateCard actions:**
- `Preview` → modal showing the React Flow canvas of the template (read-only)
- `Use this` → `POST /v1/workflows` with template definition cloned, navigate to `/workflows/[new_id]`

Templates are either static JSON bundled with the frontend or fetched from `GET /v1/templates` (if endpoint added in future). In v1, implement as a static registry file: `src/data/templates.ts`.

---

## 15. Schedules Page

**Route:** `/schedules`
**API:** `GET /v1/schedules`, `POST /v1/workflows/{id}/schedules`, `PUT /v1/schedules/{id}`, `DELETE /v1/schedules/{id}`

```
┌── Schedules ────────────────────────────────────────────────────────────┐
│  Active Schedules                                [+ New schedule]        │
│  ─────────────────────────────────────────────────────────────────────  │
│  [⏱] Daily Report        Mon–Fri 09:00 ET    My Report Workflow   [⋮]  │
│       next: Tomorrow 09:00                                               │
│  [⏱] Hourly Sync         */1 * * * *         Data Sync Pipeline   [⋮]  │
│       next: in 34 minutes                                                │
│  ─────────────────────────────────────────────────────────────────────  │
│  Inactive Schedules (2)                                    [show ▾]      │
└─────────────────────────────────────────────────────────────────────────┘
```

**Create schedule drawer (Sheet):**
- Workflow picker (searchable `GET /v1/workflows`)
- `CronEditorField` (human-readable expression: "Every weekday at 9am" ↔ `0 9 * * MON-FRI`)
- Timezone: `TimezoneSelect` (IANA zones, searchable)
- Trigger input: static JSON payload (CodeEditorField, optional)
- Active toggle

**Schema:** `ScheduleCreate` → `{ cron_expression, timezone, trigger_input, is_active }`

**Context menu (⋮) per schedule:**
- Edit (open create drawer pre-filled)
- Pause / Resume → toggle `is_active` via `PUT /v1/schedules/{id}`
- Delete → `DELETE /v1/schedules/{id}` with AlertDialog

---

## 16. Cross-Cutting Concerns

### 16.1 Loading States

Every async data fetch uses React Suspense + skeleton screens. Use `Skeleton` from shadcn/ui:

- **Table rows:** Render 5 skeleton rows while loading
- **Cards:** Render 6 skeleton cards while loading
- **Canvas:** Show spinner overlay while `GET /v1/workflows/{id}` loads
- **Config panel:** Skeleton for form fields while schema loads

Never show an empty page — always show skeletons on first load.

### 16.2 Empty States

| Page | Empty state message | CTA |
|---|---|---|
| `/workflows` | `"No workflows yet"` | Create buttons |
| `/runs` | `"No runs yet"` | Link to workflows |
| `/schedules` | `"No schedules configured"` | `+ New schedule` |
| `/settings/integrations` (API keys) | `"No API keys"` | `+ Create API key` |
| `/settings/integrations` (webhooks) | `"No webhooks"` | `+ Add webhook` |
| Node palette (search) | `"No nodes match"` | Clear search |
| Log panel | `"No logs yet — run is waiting"` | — |

### 16.3 Error States

- **Network error (no response):** Persistent red banner at top of page with retry button
- **HTTP 403:** Inline message `"You don't have permission to view this"` — no redirect
- **HTTP 404:** Dedicated 404 page with back button
- **HTTP 500:** Toast `"Something went wrong — our team has been notified"` + retry where applicable
- **Form validation errors:** Inline below each field using React Hook Form `formState.errors`

### 16.4 Confirmation Dialogs

Use `AlertDialog` (shadcn) for all destructive actions:

| Action | Confirmation text |
|---|---|
| Delete workflow | `"Delete 'My Workflow'? This cannot be undone and will also delete all run history."` |
| Remove team member | `"Remove Alice from your team? They will lose access immediately."` |
| Revoke API key | `"Revoke this key? Any integrations using it will break immediately."` |
| Cancel run | `"Cancel this run? The workflow will stop at the next node boundary."` |
| Delete schedule | `"Delete this schedule? No future runs will be triggered."` |

All AlertDialogs: Cancel button (outline) + Destructive action button (destructive variant, explicit label — never `"OK"`).

### 16.5 Toast Notifications

Use `sonner` (shadcn toast). Placement: bottom-right. Duration: 4s (success) / 8s (error, persistent until dismissed).

| Event | Toast type | Message |
|---|---|---|
| Workflow saved | success | `"Saved"` |
| Workflow published | success | `"Published as v{n}"` |
| Run triggered | success | `"Run started"` + link to run detail |
| Run completed | success | `"Run completed in 4.2s"` |
| Run failed | error | `"Run failed at node 'api_request_1'"` |
| API error | error | Error message from `ErrorDetail.message` |
| MFA enabled | success | `"Two-factor authentication enabled"` |
| Invite sent | success | `"Invitation sent to dave@example.com"` |

### 16.6 Keyboard Shortcuts

| Shortcut | Action | Context |
|---|---|---|
| `Ctrl/⌘ + S` | Force save | Canvas editor |
| `Ctrl/⌘ + Z` | Undo | Canvas editor |
| `Ctrl/⌘ + Shift + Z` | Redo | Canvas editor |
| `Del` / `Backspace` | Delete selected node/edge | Canvas (when not in input) |
| `Ctrl/⌘ + A` | Select all nodes | Canvas |
| `Escape` | Close config panel / modal | Everywhere |
| `Ctrl/⌘ + Enter` | Submit form | Modals/chat input |
| `F` | Fit view (zoom to fit) | Canvas |
| `[` / `]` | Zoom in / out | Canvas |

### 16.7 Accessibility

- All interactive elements have `aria-label` or visible text
- Modals trap focus; restore focus to trigger on close
- Live regions: execution status updates use `aria-live="polite"`
- WCAG AA colour contrast for all text — use Tailwind `text-*` pairs that meet 4.5:1
- All form fields have associated `<label>` elements
- Keyboard-navigable dropdowns (arrow keys, Enter to select, Escape to close)
- Canvas: nodes are accessible via `Tab` in the React Flow canvas; node status announced to screen readers

### 16.8 Responsive Breakpoints

| Breakpoint | Layout changes |
|---|---|
| `< 640px` (sm) | Single column; sidebar hidden behind hamburger; canvas disabled (show message: "Use a larger screen to edit workflows") |
| `640–1024px` (md) | Sidebar collapsed (48px); two-panel dashboard; config panel as bottom sheet |
| `1024–1280px` (lg) | Full layout; sidebar expanded; config panel overlay |
| `> 1280px` (xl) | Full layout; wider chat/config panels |

---

## 17. API Integration Map

Complete mapping of every TQ hook to its API call, organised by module.

### Auth

```typescript
// api/auth.ts
useLogin()              // POST /auth/login
useRegister()           // POST /auth/register
useLogout()             // POST /auth/logout
useRefreshToken()       // POST /auth/token/refresh
useMFASetup()           // POST /auth/mfa/setup
useMFAVerify()          // POST /auth/mfa/verify
useMe()                 // GET  /users/me
useUpdateProfile()      // PATCH /users/me
usePasswordReset()      // POST /auth/password/reset-request
usePasswordResetConfirm() // POST /auth/password/reset
```

### Workflows

```typescript
// api/workflows.ts
useWorkflows(params)         // GET    /v1/workflows
useWorkflow(id)              // GET    /v1/workflows/{id}
useCreateWorkflow()          // POST   /v1/workflows
useSaveWorkflow()            // PUT    /v1/workflows/{id}
useDeleteWorkflow()          // DELETE /v1/workflows/{id}
useTriggerWorkflow()         // POST   /v1/workflows/{id}/trigger
useActivateWorkflow()        // POST   /v1/workflows/{id}/activate
useWorkflowVersions(id)      // GET    /v1/workflows/{id}/versions
useWorkflowVersion(id, vid)  // GET    /v1/workflows/{id}/versions/{vid}
```

### Executions

```typescript
// api/executions.ts
useExecutions(params)        // GET  /v1/executions
useExecution(run_id)         // GET  /v1/executions/{run_id}
useCancelExecution()         // POST /v1/executions/{run_id}/cancel
useNodeStates(run_id)        // GET  /v1/executions/{run_id}/nodes
useExecutionLogs(run_id)     // GET  /v1/executions/{run_id}/logs
useSubmitHumanInput()        // POST /v1/executions/{run_id}/human-input
```

### Chat

```typescript
// api/chat.ts (see docs/frontend/chat-module.md §5 for full spec)
useCreateChatSession()           // POST /v1/chat/sessions
useChatSessions()                // GET  /v1/chat/sessions
useChatSession(id)               // GET  /v1/chat/sessions/{id}
useSendMessage()                 // POST /v1/chat/sessions/{id}/message
useForceGenerate()               // POST /v1/chat/sessions/{id}/generate
useUpdateChatWorkflow()          // PUT  /v1/chat/sessions/{id}/workflow
```

### Schedules & Webhooks

```typescript
// api/schedules.ts
useSchedules(params?)            // GET    /v1/schedules                        (global tenant list)
useWorkflowSchedules(workflow_id)// GET    /v1/workflows/{id}/schedules         (per-workflow list)
useCreateSchedule(workflow_id)   // POST   /v1/workflows/{id}/schedules
useUpdateSchedule()              // PATCH  /v1/schedules/{schedule_id}
useDeleteSchedule()              // DELETE /v1/schedules/{schedule_id}

// api/webhooks.ts
useWebhooks()                    // GET    /v1/webhooks
useCreateWebhook()               // POST   /v1/webhooks
useUpdateWebhook()               // PUT    /v1/webhooks/{webhook_id}
useDeleteWebhook()               // DELETE /v1/webhooks/{webhook_id}
```

### Users & Team

```typescript
// api/users.ts (ADMIN / OWNER only)
useTeamMembers()                 // GET    /v1/users
usePendingInvites()              // GET    /v1/users/invites
useInviteUser()                  // POST   /v1/users/invite
useRevokeInvite()                // DELETE /v1/users/invites/{invite_id}
useUpdateUserRole()              // PATCH  /v1/users/{user_id}
useRemoveUser()                  // DELETE /v1/users/{user_id}
```

### API Keys

```typescript
// api/apiKeys.ts
// Note: API keys are user-scoped, not tenant-scoped.
useAPIKeys()                     // GET    /v1/users/me/api-keys
useCreateAPIKey()                // POST   /v1/users/me/api-keys
useRevokeAPIKey()                // DELETE /v1/users/me/api-keys/{key_id}
```

### Integrations / Connections

```typescript
// api/integrations.ts
useConnections(provider?)        // GET    /v1/integrations/connections
useRevokeConnection()            // DELETE /v1/integrations/connections/{connection_id}
// OAuth initiation: redirect to GET /auth/oauth/{provider} (opens provider login)
```

### Usage & Billing

```typescript
// api/usage.ts
useUsageSummary(params?)         // GET /v1/usage
useUsageHistory(months)          // GET /v1/usage?granularity=month&period_start=...
```

---

## 18. Build Priority Order

Build in this sequence — each module unblocks the next:

| # | Module | Route(s) | Depends on |
|---|---|---|---|
| 1 | Auth store + Axios interceptor | — | — |
| 2 | Login page | `/login` | 1 |
| 3 | Register page | `/signup` | 1 |
| 4 | App shell (sidebar + topbar) | All protected | 2 |
| 5 | Workflow dashboard | `/workflows` | 4 |
| 6 | Blank canvas editor (no config panel) | `/workflows/[id]` | 5 |
| 7 | Node config panel (DynamicConfigForm) | (panel) | 6 |
| 8 | Execution monitor (run list + detail) | `/runs` | 6 |
| 9 | Chat-first creation (G-6) | `/workflows/new` | 6 |
| 10 | Log viewer | (in run detail) | 8 |
| 11 | Settings — profile + team | `/settings/*` | 4 |
| 12 | Settings — integrations | `/settings/integrations` | 4 |
| 13 | Billing dashboard | `/settings/billing` | 4 |
| 14 | Schedules | `/schedules` | 5 |
| 15 | Templates gallery | `/templates` | 5 |
| 16 | MFA setup flow | (in profile) | 11 |
| 17 | Version history panel | (in editor) | 6 |
