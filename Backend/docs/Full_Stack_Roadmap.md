# AI Workflow Builder Platform — Full-Stack Development Roadmap
### Complete System Design: SDK · Backend · Frontend
> **Platform Vision:** A production-grade AI workflow automation platform (comparable to n8n + Vellum) built on an engine-first SDK. Users visually compose DAG-based AI pipelines; the SDK executes them with full observability.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [SDK Refinement & Updates](#2-sdk-refinement--updates)
3. [Backend Architecture — All Services](#3-backend-architecture--all-services)
4. [Frontend Architecture — Full End-to-End](#4-frontend-architecture--full-end-to-end)
5. [Sample Project Structures](#5-sample-project-structures)
6. [Development Phases](#6-development-phases)

---

## 1. System Architecture Overview

### 1.1 End-to-End Architecture

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║  EXTERNAL ACTORS                                                                      ║
║                                                                                      ║
║  Browser User          Developer (CLI)         External Webhooks      Cron Clock     ║
║      │                      │                        │                    │           ║
╚══════╪══════════════════════╪════════════════════════╪════════════════════╪═══════════╝
       │ HTTPS                │ Local + HTTP           │ HTTPS POST         │ Beat tick
       ▼                      │                        ▼                    ▼
╔══════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 5 — PRESENTATION (Next.js 14 + App Router)                                    ║
║                                                                                      ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐     ║
║  │  workflow-ui                                                                │     ║
║  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐    │     ║
║  │  │  Auth    │ │Dashboard │ │ Builder  │ │ Monitor   │ │  Observ.     │    │     ║
║  │  │  /login  │ │  /home   │ │/workflows│ │ /runs/{id}│ │  /logs       │    │     ║
║  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘ └──────────────┘    │     ║
║  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐    │     ║
║  │  │ Sandbox  │ │Scheduler │ │ Settings │ │  @wf/react│ │ Zustand/TQ   │    │     ║
║  │  │ /sandbox │ │/schedules│ │/settings │ │ comp lib  │ │ state mgmt   │    │     ║
║  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘ └──────────────┘    │     ║
║  └─────────────────────────────────────────────────────────────────────────────┘     ║
║   Communicates ONLY via HTTP/WebSocket. Never imports the SDK directly.               ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 4 — DELIVERY (Backend for Frontend + API Gateway)                             ║
║                                                                                      ║
║  ┌──────────────────────────────────────────────────────────────────────────────┐    ║
║  │  workflow-api (FastAPI — primary API gateway)                                │    ║
║  │  routes: /workflows  /executions  /nodes  /schedules  /logs  /settings      │    ║
║  │  auth: JWT validator │ API key validator │ OAuth2 flow                       │    ║
║  │  ws: WebSocket hub (Redis pub/sub → browser)                                │    ║
║  └───────────────────────────────────┬──────────────────────────────────────────┘    ║
║                                       │ Dispatches via Redis/Celery                  ║
║  ┌──────────────────┐  ┌─────────────▼──────────┐  ┌────────────────────────────┐   ║
║  │  workflow-worker  │  │  workflow-scheduler     │  │  workflow-cli              │   ║
║  │  (Celery tasks)  │  │  (Celery beat)          │  │  (Click CLI)               │   ║
║  └──────────────────┘  └─────────────────────────┘  └────────────────────────────┘   ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 3 — SDK CORE (workflow-engine Python library)  ◄── THE PRODUCT               ║
║                                                                                      ║
║  Sub-Layer A: engine.models  engine.config                                           ║
║  Sub-Layer B: engine.dag  engine.nodes  engine.validation                            ║
║  Sub-Layer C: engine.executor  engine.state  engine.context                          ║
║  Sub-Layer D: engine.providers  engine.integrations  engine.sandbox                  ║
║               engine.cache  engine.versioning  engine.privacy  engine.events         ║
║               engine.health  engine.scheduler  engine.billing  [NEW]                 ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 2 — MESSAGE BUS & ASYNC TRANSPORT                                             ║
║                                                                                      ║
║  Redis (Celery broker + pub/sub + rate limits + semaphores + context store)          ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 1 — PERSISTENCE & EXTERNAL SERVICES                                           ║
║                                                                                      ║
║  MongoDB        PostgreSQL+pgvector       GCS              LLM APIs                  ║
║  (workflows,    (users, tenants,          (large outputs,  (Gemini, Claude,          ║
║   executions,    billing, embeddings,      files)           OpenAI)                  ║
║   audit logs)    OAuth creds)                                                         ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
```

---

### 1.2 Communication Patterns

#### REST (Synchronous — UI/CLI → API)
All CRUD operations, workflow saves, execution triggers, settings management. Every request authenticated via JWT Bearer or X-API-Key header. API gateway returns structured JSON. 422 on SDK validation failure, mapped directly from `ValidationError.errors`.

#### WebSocket (Real-time — API → UI)
`WS /api/v2/ws/runs/{run_id}` — SDK EventBus publishes to Redis `ws:run:{id}`, WebSocketHub subscribes per-connection and fans out typed events to the browser. Heartbeat every 30s, auto-reconnect on browser with exponential backoff.

#### Celery/Redis Message Queue (Async — API → Worker)
`orchestrate_run.delay(run_id, definition_dict)` fires after API creates ExecutionRun record. Worker receives, builds SDK objects, drives RunOrchestrator. Parallel branches use Celery `group/chord`. Three queues: `default`, `ai-heavy`, `critical`.

#### Server-Sent Events (SSE — API → UI for logs)
`GET /api/v2/logs/stream?run_id=X` — streaming log endpoint using SSE for the Observability page log tail. Fallback for environments where WebSocket is blocked.

---

### 1.3 Full Execution Lifecycle (Save → Execute → Observe)

```
User Action         Frontend               API                  Worker/SDK
───────────         ────────               ───                  ──────────
Design workflow  →  React Flow graph  →  POST /workflows    →  SDK validate + version
                    serialize JSON        422 if invalid        MongoDB insert
                    show errors inline    201 with version_no

Trigger run      →  POST /executions  →  Acquire semaphore  →  Celery: orchestrate_run
                    open WebSocket        pin version            DAGParser.parse()
                    show QUEUED badge     MongoDB insert         state → RUNNING
                                          dispatch to queue      EventBus → Redis → WS → UI
                                                                 NodeExecutor per node
                                                                 context.store_output()
                                                                 state → SUCCESS/FAILED
                                                                 cleanup_run.delay()

Monitor          →  WS events update  →  WebSocket hub       →  events published
                    node colors           Redis pub/sub          per node completion
                    log stream            forward to client

View logs        →  GET /logs/stream  →  SSE/cursor query    →  Audit log tail
                    infinite scroll       MongoDB tail           MongoDB append-only
```

---

## 2. SDK Refinement & Updates

### 2.1 New SDK Modules Required

The following modules are **not in the current SDK plan** but are required by the full frontend + backend:

#### `engine.auth` (NEW — Sub-Layer D)
The authentication service needs SDK-level primitives that can be tested without FastAPI:

```
engine/auth/
  token.py          TokenGenerator — generate/validate JWT access + refresh tokens
  password.py       PasswordHasher — bcrypt hash + verify
  api_key.py        APIKeyManager — generate, hash (SHA-256), validate API keys
  session.py        SessionManager — Redis-backed session store for web UI
  mfa.py            MFAManager — TOTP generation/validation (Google Authenticator)
  models.py         AuthUser, AuthSession, APIKey, OAuthToken models
```

**Why SDK-level?** The CLI needs to validate tokens locally. Workers need to resolve API key tenants. A shared primitive prevents duplication.

#### `engine.notifications` (NEW — Sub-Layer D)
Workflow completion notifications (email, Slack, webhook) need to be driven by the SDK EventBus, not hard-coded in the API:

```
engine/notifications/
  dispatcher.py     NotificationDispatcher — routes DomainEvents to channels
  channels/
    email.py        EmailChannel — SMTP/SendGrid integration
    slack.py        SlackChannel — Slack webhook/bot integration
    webhook.py      WebhookChannel — outbound POST on run completion
  models.py         NotificationConfig, NotificationEvent, NotificationChannel
```

#### `engine.templates` (NEW — Sub-Layer D)
Users need a gallery of starter workflow templates. Template logic belongs in the SDK:

```
engine/templates/
  registry.py       TemplateRegistry — built-in + tenant-custom templates
  models.py         WorkflowTemplate, TemplateCategory, TemplateMetadata
  bundler.py        TemplateBundler — export/import workflow bundles (ZIP + JSON manifest)
```

---

### 2.2 SDK Interface Updates

#### `engine.models.requests` + `engine.models.responses`
The API and CLI share request/response contracts. Add to SDK models:

```python
# engine/models/responses.py — NEW
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool

class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: str
    validation_errors: list[str] | None = None

class HealthResponse(BaseModel):
    overall: HealthStatus
    dependencies: list[DependencyStatus]
    version: str
    checked_at: datetime
```

#### `engine.models.errors` — HTTP-mappable exceptions
Every SDK exception needs `http_status_code` for the API's global exception handler:

```python
class EngineError(Exception):
    http_status_code: int = 500

class ValidationError(EngineError):    http_status_code = 422
class NotFoundError(EngineError):      http_status_code = 404
class ConflictError(EngineError):      http_status_code = 409
class ForbiddenError(EngineError):     http_status_code = 403
class QuotaExceededError(EngineError): http_status_code = 429
class AuthenticationError(EngineError):http_status_code = 401
```

#### `engine.context.trace` — OTel propagation
Workers need to continue API traces across the Celery message boundary:

```python
# engine/context/trace.py — NEW
def propagate_to_task(task_kwargs: dict) -> None: ...   # inject W3C traceparent
def extract_from_task(task_kwargs: dict) -> Context: ... # reconstruct span context
```

---

### 2.3 Updated SDK Module Table

| Module | Sub-layer | Status | Notes |
|---|---|---|---|
| `engine.config` | A | Existing | No change |
| `engine.models` | A | **Updated** | Add responses.py, requests.py, new error types |
| `engine.dag` | B | Existing | No change |
| `engine.nodes` | B | Existing | No change |
| `engine.validation` | B | Existing | No change |
| `engine.executor` | C | Existing | No change |
| `engine.state` | C | Existing | No change |
| `engine.context` | C | **Updated** | Add trace.py |
| `engine.sandbox` | D | Existing | No change |
| `engine.providers` | D | Existing | No change |
| `engine.integrations` | D | Existing | No change |
| `engine.cache` | D | Existing | No change |
| `engine.versioning` | D | **Updated** | Add get_version(), get_latest() |
| `engine.privacy` | D | Existing | No change |
| `engine.events` | D | Existing | No change |
| `engine.health` | D | **NEW** | HealthChecker + HealthReport |
| `engine.scheduler` | D | **NEW** | CronEvaluator + TriggerFinder |
| `engine.billing` | D | **NEW** | UsageTracker + QuotaChecker |
| `engine.auth` | D | **NEW** | Token, password, API key, MFA |
| `engine.notifications` | D | **NEW** | Email, Slack, webhook channels |
| `engine.templates` | D | **NEW** | Workflow template registry |

---

## 3. Backend Architecture — All Services

### 3.1 workflow-api (FastAPI — Primary Gateway)

**Principle:** Thin shell. All logic in SDK. Routes are ≤30 lines each.

#### 3.1.1 Complete Route Surface

| Route Group | Endpoints | SDK Modules |
|---|---|---|
| **Auth** | POST /auth/login, POST /auth/signup, POST /auth/refresh, POST /auth/logout, POST /auth/mfa/setup, POST /auth/mfa/verify | `engine.auth` |
| **OAuth** | GET /auth/oauth/{provider}, GET /auth/oauth/{provider}/callback | `engine.auth` |
| **Workflows** | CRUD + duplicate + export + import | `validation`, `versioning` |
| **Executions** | trigger + status + cancel + retry + list | `state`, `versioning`, `privacy` |
| **Versions** | list + get + diff + rollback | `versioning` |
| **Nodes** | list types + schema + validate-config | `nodes.registry` |
| **Schedules** | CRUD schedules + pause + resume | `engine.scheduler` |
| **Logs** | GET /logs (paginated) + GET /logs/stream (SSE) | MongoDB tail |
| **Templates** | list + get + clone + publish | `engine.templates` |
| **Settings** | GET/PUT /settings/profile, /settings/team, /settings/integrations, /settings/billing | `engine.billing`, `engine.auth` |
| **API Keys** | list + create + revoke | `engine.auth.api_key` |
| **Webhooks** | inbound webhook receiver | `engine.integrations` |
| **Health** | GET /health + /readyz + /livez | `engine.health` |
| **Admin** | tenant CRUD + quota + GDPR delete | `engine.billing`, `engine.privacy` |

#### 3.1.2 Auth Service Integration

The API includes a full auth subsystem built on `engine.auth`:

```
auth/
  jwt.py            JWTValidator — RS256, extract tenant_id + user_id + roles
  api_key.py        APIKeyValidator — SHA-256 hash → PostgreSQL lookup
  oauth.py          OAuthFlow — Google, GitHub, Microsoft providers
  mfa.py            MFAHandler — TOTP setup/verify flow
  signup.py         SignupHandler — email verification, password setup
  password_reset.py PasswordResetHandler — token generation + email send
```

**JWT Claims Structure:**
```json
{
  "sub": "user_id",
  "tenant_id": "tenant_uuid",
  "roles": ["owner", "editor", "viewer"],
  "plan": "PRO",
  "exp": 1735000000,
  "iat": 1734990000,
  "jti": "unique_token_id"
}
```

#### 3.1.3 Middleware Stack (in order)

```
Request
  → RequestIDMiddleware        (inject X-Request-ID)
  → OTelTracingMiddleware      (create root span)
  → StructuredLoggingMiddleware (JSON log per request, PII-masked)
  → CORSMiddleware             (configured origins)
  → TenantContextMiddleware    (JWT/API key → Tenant into request.state)
  → APIRateLimitMiddleware     (Redis per-tenant RPM)
  → Route Handler
Response
  → GZipMiddleware
```

#### 3.1.4 Scalability
- Stateless instances — all state in Redis/MongoDB
- Connection pooling: motor pool_size=20, asyncpg min=5 max=20, aioredis pool=10
- HPA: min=2, max=10, scale on CPU>70%
- WebSocket fan-out: multiple API instances all subscribe to same Redis channel

---

### 3.2 workflow-worker (Celery Task Workers)

**Principle:** Tasks are thin wrappers. SDK does all work.

#### 3.2.1 Task Inventory

| Task | Queue | Responsibility |
|---|---|---|
| `orchestrate_run` | default | Deserialize → build SDK objects → RunOrchestrator.run() → cleanup.delay() |
| `execute_single_node` | ai-heavy | Per-node parallel execution for Celery group/chord |
| `cleanup_run` | default | Release semaphore, delete Redis ctx keys, record billing |
| `scheduler_fire_cron` | scheduled | Find due triggers → create ExecutionRun → orchestrate_run.delay() |
| `handle_human_callback` | critical | Resume HumanNode after form submission |
| `send_notification` | default | Post-run email/Slack/webhook via engine.notifications |
| `cleanup_stale_semaphores` | scheduled | Beat task: reset leaked semaphore counters every 5min |
| `export_workflow_bundle` | default | Pack workflow + versions into ZIP bundle → GCS upload |

#### 3.2.2 Parallel Execution Pattern

```python
# When RunOrchestrator signals PARALLEL step:
parallel_group = group(
    execute_single_node.s(run_id, nid, definition_dict, trace_ctx)
    for nid in step.node_ids
)
chord(parallel_group)(
    execute_single_node.s(run_id, fan_in_node_id, definition_dict, trace_ctx)
)
```

#### 3.2.3 Dead Letter Queue
Failed tasks after all retries: `Redis SET dlq:{task_id} {task_kwargs + error + traceback}`. Admin UI can inspect and manually re-trigger from DLQ.

---

### 3.3 workflow-scheduler (Celery Beat)

**Separate deployment** from workers to ensure exactly-one beat process.

#### 3.3.1 Architecture
```
celery beat (single replica)
  → every minute: scheduler_fire_cron task
     → engine.scheduler.trigger_finder.find_due_triggers(now)
     → for each: engine.scheduler.dispatcher.dispatch(trigger) → run_id
     → orchestrate_run.delay(run_id, ...)
  → every 5min: cleanup_stale_semaphores
  → every hour: cleanup_expired_context_keys (Redis ctx:* TTL enforcement)
```

#### 3.3.2 Schedule Storage
Cron schedules stored in MongoDB `schedules` collection:
```json
{
  "schedule_id": "uuid",
  "workflow_id": "uuid",
  "tenant_id": "uuid",
  "cron_expr": "0 9 * * 1-5",
  "timezone": "Asia/Kolkata",
  "is_active": true,
  "last_fired_at": "2024-01-15T09:00:00Z",
  "next_fire_at": "2024-01-16T09:00:00Z",
  "trigger_input": {}
}
```

---

### 3.4 Missing Backend Services — New Additions

#### 3.4.1 Auth Service (Standalone — optional microservice pattern)

For large-scale deployments, authentication can be extracted into a dedicated service. For the initial build, it lives inside `workflow-api` but is structured to be extractable:

```
services/auth-service/  (future microservice separation)
  handlers/
    login.py            Email+password login → JWT pair
    signup.py           Register → email verification → activate
    oauth.py            Social login callback handlers
    mfa.py              TOTP setup, QR code generation, verify
    password_reset.py   Token generation, email send, reset handler
    token_refresh.py    Refresh token rotation
  repositories/
    user_repo.py        PostgreSQL user CRUD
    session_repo.py     Redis session store
    api_key_repo.py     PostgreSQL API key CRUD
```

**User model in PostgreSQL:**
```sql
users: id, email, password_hash, is_verified, mfa_enabled, mfa_secret,
       tenant_id, role, plan_tier, created_at, last_login_at

tenants: id, name, slug, plan_tier, max_workflows, max_executions_per_day,
         max_concurrent_runs, created_at, billing_email

api_keys: id, user_id, tenant_id, key_hash, name, scopes, last_used_at,
          expires_at, is_active, created_at
```

#### 3.4.2 Notification Service

Built on top of `engine.notifications`. Triggered by the EventBus on RunCompleted/RunFailed events:

```
services/notification-service/  (runs as worker task)
  channels/
    email_sender.py     SendGrid/SMTP async sender
    slack_sender.py     Slack Web API integration
    webhook_sender.py   Outbound webhook with HMAC signing
  template_engine.py   Jinja2 email/Slack template rendering
  routing.py           Map tenant notification config to channels
```

**Notification config per workflow:**
```json
{
  "on_success": [{"channel": "email", "to": "user@example.com"}],
  "on_failure": [
    {"channel": "slack", "webhook_url": "https://hooks.slack.com/..."},
    {"channel": "email", "to": "ops@example.com"}
  ]
}
```

#### 3.4.3 Sandbox Service

The existing `engine.sandbox` handles Tier-1 (RestrictedPython). A proper sandbox service is needed for Tier-2 (isolated container execution):

```
services/sandbox-service/
  container_manager.py  Spin up ephemeral Docker/gVisor containers
  input_injector.py     Inject user code + input vars into container
  output_collector.py   Collect stdout/stderr + output dict from container
  resource_limiter.py   CPU/memory/network limits via cgroup2
  cleanup.py            Destroy container after execution (max 60s)
```

**Execution flow:**
```
TransformNode (code mode)
  → engine.sandbox.manager → tier selection
  → Tier 1: RestrictedPython (in-process, fast, limited)
  → Tier 2: HTTP POST sandbox-service/execute {code, input, limits}
            → spin ephemeral container → run code → return output
            → destroy container
```

#### 3.4.4 Log Aggregation Service

A log tailing and search service for the Observability UI:

```
services/log-service/  (thin wrapper around MongoDB + OpenSearch)
  ingester.py          Structured log ingestion from SDK EventBus
  query_engine.py      Full-text search over execution logs
  tail.py              Cursor-based log tailing for SSE streaming
  retention.py         Log retention policy enforcement (30/90/365 days)
```

MongoDB `audit_log` serves as the primary store. For full-text search, logs are also forwarded to OpenSearch (optional, enterprise tier).

---

## 4. Frontend Architecture — Full End-to-End

### 4.1 Technology Stack

| Concern | Technology | Rationale |
|---|---|---|
| Framework | Next.js 14 + App Router | SSR for auth pages, client components for interactive UI |
| Language | TypeScript 5.x | Full type safety; SDK response schemas generated as TS types |
| Canvas / DAG | React Flow v12 | Node-based graph editor with custom node types |
| State Management | Zustand + TanStack Query v5 | Zustand for canvas state; TQ for server state + caching |
| Styling | Tailwind CSS + shadcn/ui | Utility-first; accessible components |
| Code Editor | Monaco Editor | Syntax highlighting for Python in TransformNode config |
| Forms | React Hook Form + Zod | Dynamic form generation from SDK JSON Schema |
| Real-time | Native WebSocket + custom hook | `useWebSocket` hook wrapping WS API |
| Charts | Recharts | Execution metrics, token usage charts |
| Animations | Framer Motion | Page transitions, node status transitions |
| Testing | Vitest + React Testing Library + Playwright | Unit + integration + E2E |

---

### 4.2 Module Breakdown

#### 4.2.1 Auth Module (`/app/(auth)/`)

**Pages:**
- `/login` — Email/password login + social OAuth buttons + MFA verify step
- `/signup` — Multi-step: email → password → team/solo → plan selection
- `/forgot-password` — Email input → confirmation
- `/reset-password/[token]` — New password form
- `/verify-email/[token]` — Email verification landing

**Components:**
```
components/auth/
  LoginForm.tsx           Email + password + "remember me" + OAuth buttons
  SignupWizard.tsx         Multi-step wizard (4 steps)
  MFAVerifyForm.tsx        6-digit TOTP input with auto-submit
  OAuthButton.tsx          Google / GitHub / Microsoft with loading state
  PasswordStrengthMeter.tsx  Real-time strength indicator
  EmailVerificationBanner.tsx  Top banner if email not verified
```

**State:** `useAuthStore` (Zustand) — user, tenant, tokens, roles, isAuthenticated

**Token Management:**
- Access token (15min): stored in memory (React state)
- Refresh token (7 days): HttpOnly cookie
- Auto-refresh: axios interceptor calls `/auth/refresh` on 401
- Logout: clears memory + expires cookie + calls `/auth/logout`

---

#### 4.2.2 Dashboard Module (`/app/(dashboard)/`)

**Page: `/` (Home)**

```
DashboardPage
  ├── DashboardHeader (greeting, quick actions)
  ├── StatsGrid
  │   ├── StatCard (Total Workflows)
  │   ├── StatCard (Runs Today)
  │   ├── StatCard (Success Rate %)
  │   └── StatCard (Token Cost Today)
  ├── RecentWorkflows (last 5, with status badges)
  ├── ExecutionTimeline (bar chart — last 7 days)
  ├── ActiveRunsPanel (live WebSocket status for in-flight runs)
  └── QuickStartBanner (for new users)
```

**Components:**
```
components/dashboard/
  StatsGrid.tsx           4-up metric grid with trend indicators
  RecentWorkflows.tsx      Compact list with last-run status + run button
  ExecutionTimeline.tsx    Recharts BarChart, run count per day per status
  ActiveRunsPanel.tsx      Real-time list of RUNNING executions (WS)
  QuickStartBanner.tsx     Template gallery for new users
```

**Data fetching:**
- `useQuery(['dashboard-stats'])` → GET /api/v2/stats
- `useQuery(['recent-workflows'])` → GET /api/v2/workflows?limit=5&sort=updated
- `useActiveRuns()` — WebSocket hook subscribing to tenant-level run updates

---

#### 4.2.3 Workflow Builder Module (`/app/(dashboard)/workflows/`)

This is the **core product** — the DAG editor.

**Pages:**
- `/workflows` — Workflow list + search + filters + create button
- `/workflows/new` — Blank canvas
- `/workflows/[id]` — Editor canvas (existing workflow)
- `/workflows/[id]/runs` — Run history for this workflow
- `/workflows/[id]/runs/[run_id]` — Execution detail

**Canvas Architecture:**
```
WorkflowEditorPage
  ├── EditorTopBar
  │   ├── WorkflowNameInput (inline edit)
  │   ├── SaveButton (debounced auto-save)
  │   ├── RunButton → trigger execution
  │   ├── VersionBadge → opens VersionHistory panel
  │   └── EditorActions (export, duplicate, delete, share)
  ├── NodePalette (left sidebar)
  │   ├── PaletteSearch
  │   ├── PaletteCategory (AI, Logic, Integration, Data, Human)
  │   └── PaletteNode[] (draggable to canvas)
  ├── WorkflowCanvas (main area — React Flow)
  │   ├── CustomNode[] (7 types, each with visual style)
  │   ├── CustomEdge[] (typed ports, animated data flow)
  │   ├── MiniMap
  │   └── Controls (zoom, fit, lock)
  ├── NodeConfigPanel (right sidebar — conditional)
  │   ├── NodeTypeHeader
  │   ├── DynamicConfigForm (from JSON Schema)
  │   └── NodeTestPanel (test single node with mock input)
  └── ValidationOverlay
      └── ErrorBubble[] (inline on invalid nodes)
```

**Canvas State Management (Zustand `useWorkflowStore`):**
```typescript
interface WorkflowStore {
  // Graph state
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;

  // Persistence state
  workflowId: string;
  workflowName: string;
  isDirty: boolean;
  lastSavedVersion: number;
  saveStatus: 'idle' | 'saving' | 'saved' | 'error';

  // Execution state
  runId: string | null;
  runStatus: ExecutionStatus | null;
  nodeStatuses: Record<string, NodeStatus>;  // Updated by WebSocket
  nodeLogs: Record<string, string[]>;

  // Actions
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  setSelectedNode: (id: string | null) => void;
  updateNodeConfig: (nodeId: string, config: Partial<NodeConfig>) => void;
  triggerSave: () => Promise<void>;
  triggerRun: (input: Record<string, unknown>) => Promise<string>;
  applyNodeStatus: (event: WsEvent) => void;
}
```

**Custom Node Components (React Flow):**
```
components/nodes/
  TriggerNode.tsx         Orange, webhook/cron icon, single output port
  AINode.tsx              Purple, sparkle icon, prompt preview, cache indicator
  MCPNode.tsx             Blue, tool icon, tool name display
  APINode.tsx             Green, globe icon, method badge (GET/POST)
  LogicNode.tsx           Yellow, branch icon, condition preview
  TransformNode.tsx       Teal, code icon, Monaco preview (first 2 lines)
  HumanNode.tsx           Red, person icon, assignee display
  BaseNode.tsx            Shared: port handles, status ring, selection glow
```

**Node Status Visualization:**
```typescript
const nodeStatusStyles = {
  PENDING:   { ring: 'ring-gray-300',  dot: 'bg-gray-400' },
  RUNNING:   { ring: 'ring-blue-400',  dot: 'bg-blue-500', animate: 'animate-pulse' },
  SUCCESS:   { ring: 'ring-green-400', dot: 'bg-green-500' },
  FAILED:    { ring: 'ring-red-400',   dot: 'bg-red-500' },
  RETRYING:  { ring: 'ring-yellow-400',dot: 'bg-yellow-500', animate: 'animate-spin' },
  SKIPPED:   { ring: 'ring-gray-200',  dot: 'bg-gray-300', opacity: 'opacity-50' },
}
```

**Dynamic Config Form (from SDK JSON Schema):**
```typescript
// NodeConfigPanel uses react-jsonschema-form or custom renderer
// Renders different field types:
// string → TextInput or Textarea (based on x-widget annotation)
// number → NumericInput with min/max
// boolean → Toggle
// enum → Select dropdown
// object → Nested card
// Special: prompt_template → Monaco Editor (Monaco with Jinja2 syntax)
// Special: model → ModelPicker (shows provider + tier)
```

**Auto-save strategy:**
- Debounce 2000ms on any canvas change
- Optimistic UI: show "Saving..." immediately
- On save error: toast + "Manual save" button
- Offline: queue saves in Zustand, flush on reconnect

---

#### 4.2.4 Execution Monitoring Module (`/runs/`)

**Pages:**
- `/runs` — All executions across all workflows (filterable, sortable)
- `/workflows/[id]/runs/[run_id]` — Single execution detail

**Run Detail Page Architecture:**
```
ExecutionDetailPage
  ├── RunHeader
  │   ├── StatusBadge (RUNNING → animated, SUCCESS → green, FAILED → red)
  │   ├── RunMeta (workflow name, version, triggered by, duration)
  │   └── RunActions (cancel, retry, share)
  ├── ExecutionCanvas (read-only React Flow, same nodes coloured by status)
  │   └── RunMonitor overlay (node status rings from WS)
  ├── TabBar (Log | Timeline | Context | Input/Output)
  │   ├── ExecutionLogTab
  │   │   ├── NodeFilter (show logs for all nodes or specific node)
  │   │   └── LogStream (auto-scrolling, coloured by level)
  │   ├── TimelineTab
  │   │   └── GanttChart (node execution timeline, parallelism visible)
  │   ├── ContextTab
  │   │   └── NodeOutputExplorer (tree view of each node's stored output)
  │   └── IOTab
  │       ├── TriggerInputView (formatted JSON)
  │       └── FinalOutputView (last node's output)
  └── RunSidebar
      ├── NodeList (click to jump to node in canvas)
      └── RetryPolicy display
```

**WebSocket Integration:**
```typescript
// useRunWebSocket hook
const { status, nodeStatuses, logLines } = useRunWebSocket(run_id);
// Connects to WS /api/v2/ws/runs/{run_id}
// Events: RunStarted, NodeStarted, NodeCompleted, NodeFailed, RunCompleted
// Auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s)
// Disconnect when run reaches terminal state (SUCCESS/FAILED/CANCELLED)
```

---

#### 4.2.5 Sandbox Module (`/sandbox`)

An interactive code playground for testing TransformNode Python code before embedding in a workflow.

**Page Structure:**
```
SandboxPage
  ├── SandboxHeader (title, save-to-node, clear)
  ├── SandboxEditor (Monaco Editor — Python, full LSP)
  │   ├── InputPanel (JSON input editor, left split)
  │   └── CodePanel (Python code editor, right split)
  ├── RunButton → POST /api/v2/sandbox/execute
  ├── OutputPanel
  │   ├── OutputJSON (parsed output dict)
  │   ├── StdoutPanel (print statements)
  │   ├── ErrorPanel (traceback with line highlighting)
  │   └── MetricsRow (execution_ms, memory_kb)
  └── ExamplesLibrary (saved code snippets)
```

**Backend sandbox endpoint:**
```
POST /api/v2/sandbox/execute
Body: { code: string, input: dict, timeout_seconds: int }
Response: { output: dict, stdout: string, error?: string, metrics: {...} }
```

This calls `engine.sandbox.manager.execute()` directly (Tier 1 RestrictedPython for sandbox UI, Tier 2 container for production workflows).

---

#### 4.2.6 Scheduler Module (`/schedules`)

**Page Structure:**
```
SchedulesPage
  ├── ScheduleList
  │   ├── ScheduleCard[] (cron expr, workflow, next fire, active toggle)
  │   └── CreateScheduleButton → opens modal
  └── CreateScheduleModal
      ├── WorkflowPicker
      ├── CronBuilder (visual cron expression builder)
      │   ├── CronPresets (every hour, daily, weekly, etc.)
      │   └── CronInput (raw expression + human-readable preview)
      ├── TimezoneSelector
      ├── TriggerInputEditor (JSON for workflow input)
      └── NotificationSettings
```

**Cron Expression Builder:**
Visual builder (UI component, no SDK needed):
- Tabs: Minutes | Hours | Day | Month | Weekday
- Human preview: "At 09:00, Monday through Friday"
- Next 5 fire times shown in user's timezone

---

#### 4.2.7 Observability & Logs Module (`/logs`, `/metrics`)

**Pages:**
- `/logs` — System-wide log stream with filters
- `/metrics` — Execution metrics + token costs dashboard

**Logs Page:**
```
LogsPage
  ├── LogFilters
  │   ├── WorkflowFilter (multi-select)
  │   ├── StatusFilter (SUCCESS/FAILED/RUNNING)
  │   ├── DateRangePicker
  │   └── SearchBar (full-text across log lines)
  ├── LogTable
  │   ├── timestamp | run_id | workflow | node | level | message
  │   └── infinite scroll (cursor-based pagination)
  └── LogDetailDrawer (click row → full log entry + context)
```

**Metrics Page:**
```
MetricsPage
  ├── TimeRangeSelector (1h, 6h, 24h, 7d, 30d)
  ├── MetricsGrid
  │   ├── ExecutionVolume (line chart, success vs failed)
  │   ├── AvgDuration (line chart, p50/p95 per workflow)
  │   ├── TokenUsage (area chart, by model + by workflow)
  │   └── CacheHitRate (bar chart, semantic cache hits)
  ├── CostBreakdown
  │   ├── CostByWorkflow (pie chart)
  │   └── CostByModel (bar chart)
  └── ProviderHealth
      ├── ProviderLatency (Gemini, Claude, OpenAI — real-time gauges)
      └── RateLimitEvents (timeline of rate limit hits)
```

---

#### 4.2.8 Settings Module (`/settings`)

**Pages (tab layout):**
```
SettingsPage
  ├── /settings/profile
  │   ├── AvatarUpload
  │   ├── ProfileForm (name, email, timezone)
  │   └── PasswordChangeForm
  ├── /settings/security
  │   ├── MFASetupPanel (QR code → verify → enable)
  │   ├── ActiveSessionsList (revoke individual sessions)
  │   └── LoginHistoryTable
  ├── /settings/team
  │   ├── MemberList (role badges, remove button)
  │   ├── InviteMemberForm (email + role selector)
  │   └── PendingInvitesList
  ├── /settings/api-keys
  │   ├── ApiKeyList (name, last used, scopes, created)
  │   ├── CreateApiKeyModal (name + scopes → show once)
  │   └── RevokeKeyConfirmDialog
  ├── /settings/integrations
  │   ├── IntegrationCard[] (Slack, Google, GitHub, Notion...)
  │   └── ConnectOAuthFlow (per provider)
  ├── /settings/notifications
  │   ├── GlobalNotificationToggle
  │   └── ChannelConfig (email/Slack per event type)
  └── /settings/billing
      ├── CurrentPlanCard (plan name, limits, usage bars)
      ├── UsageMetrics (executions used / quota)
      └── BillingHistory (invoice list)
```

---

#### 4.2.9 Templates Gallery Module (`/templates`)

```
TemplatesPage
  ├── TemplateSearch
  ├── CategoryFilter (AI, Automation, Data, Integrations)
  ├── TemplateGrid
  │   └── TemplateCard[] (thumbnail, name, node count, clone button)
  └── TemplateDetailModal
      ├── TemplatePreviewCanvas (read-only React Flow diagram)
      ├── TemplateDescription
      ├── RequiredIntegrations (what you need to connect)
      └── CloneButton → POST /api/v2/templates/{id}/clone
```

---

### 4.3 State Management Architecture

```
Global State (Zustand stores)
  ├── useAuthStore          user, tenant, tokens, isAuthenticated
  ├── useWorkflowStore      canvas nodes/edges, execution state, WS events
  ├── useUIStore            sidebar open, theme, active panel
  └── useNotificationStore  toast messages queue

Server State (TanStack Query v5)
  ├── workflows             list + individual (auto-revalidate on focus)
  ├── executions            list + individual (15s polling when RUNNING)
  ├── nodeTypes             static (1h cache — rarely changes)
  ├── schedules             list (manual invalidate on CRUD)
  ├── logs                  infinite query (cursor-based)
  └── metrics               time-range query (refetch on range change)

Real-time State (WebSocket)
  ├── useRunWebSocket(run_id)  → updates useWorkflowStore.nodeStatuses
  └── useActiveRunsSocket()   → dashboard panel
```

---

### 4.4 API Integration Layer

```typescript
// lib/api-client.ts — base client
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  timeout: 30000,
});

// Request interceptor: inject access token from auth store
// Response interceptor: catch 401 → call /auth/refresh → retry
// Response interceptor: catch 422 → extract validation_errors → throw typed error

// lib/api/
  workflows.ts    createWorkflow, getWorkflow, listWorkflows, updateWorkflow, deleteWorkflow
  executions.ts   triggerExecution, getExecution, cancelExecution, listExecutions
  nodes.ts        listNodeTypes, getNodeSchema, validateNodeConfig
  schedules.ts    listSchedules, createSchedule, updateSchedule, deleteSchedule
  sandbox.ts      executeSandbox
  auth.ts         login, signup, logout, refreshToken, setupMFA, verifyMFA
  templates.ts    listTemplates, cloneTemplate
  settings.ts     getProfile, updateProfile, createApiKey, listApiKeys
```

---

### 4.5 Real-time Strategy

| Signal | Technology | Component |
|---|---|---|
| Execution node status | WebSocket (WS /ws/runs/{id}) | WorkflowCanvas, RunDetail |
| Dashboard active runs | WebSocket (WS /ws/runs/active) | Dashboard |
| Log stream | SSE (GET /logs/stream) | LogsPage, RunDetail LogTab |
| Metrics refresh | TanStack Query polling (30s) | MetricsPage |
| Save status | Optimistic UI + debounce | EditorTopBar |

**WebSocket hook pattern:**
```typescript
function useRunWebSocket(runId: string) {
  const ws = useRef<WebSocket>();
  const setNodeStatus = useWorkflowStore(s => s.applyNodeStatus);

  useEffect(() => {
    ws.current = new WebSocket(`${WS_URL}/api/v2/ws/runs/${runId}`);
    ws.current.onmessage = (e) => {
      const event: WsEvent = JSON.parse(e.data);
      setNodeStatus(event);
    };
    ws.current.onclose = () => {
      // exponential backoff reconnect
    };
    return () => ws.current?.close();
  }, [runId]);
}
```

---

### 4.6 UI/UX Considerations for the Workflow Builder

| Concern | Solution |
|---|---|
| Canvas performance | React Flow virtualization; max 200 visible nodes, virtual scroll for large DAGs |
| Node config complexity | Progressive disclosure: basic → advanced toggle per field |
| Validation feedback | Inline error bubbles on nodes + summary in sidebar; real-time as user types |
| Undo/redo | Custom Zustand undo stack (last 50 states) |
| Keyboard shortcuts | Ctrl+S save, Ctrl+Z undo, Ctrl+Shift+Z redo, Delete remove node, Ctrl+D duplicate |
| Mobile | Builder is desktop-only (min-width: 1024px). Other pages are responsive. |
| Empty states | Illustrated empty states for no workflows, no runs, no logs |
| Loading | Skeleton screens (not spinners) for list pages; canvas loads with shimmer |
| Error boundaries | Per-section React error boundaries; canvas error shows "reload canvas" option |
| Accessibility | ARIA roles on all interactive elements; keyboard navigation for node palette |

---

## 5. Sample Project Structures

### 5.1 Monorepo Root

```
ai-workflow-platform/
├── packages/
│   ├── workflow-engine/         # SDK — Python core library
│   ├── workflow-api/            # FastAPI service
│   ├── workflow-worker/         # Celery workers
│   ├── workflow-scheduler/      # Celery beat (separate deployment)
│   └── workflow-cli/            # Click CLI tool
├── apps/
│   ├── workflow-ui/             # Next.js frontend
│   └── workflow-storybook/      # Component documentation
├── deploy/
│   ├── docker/                  # Dockerfiles per service
│   ├── k8s/                     # Kubernetes manifests
│   └── terraform/               # IaC (GKE, CloudSQL, Memorystore, GCS)
├── .github/
│   └── workflows/               # CI/CD pipelines
├── docs/                        # Architecture docs, ADRs
└── scripts/                     # Dev setup, migration scripts
```

---

### 5.2 workflow-engine (SDK) — Updated Structure

```
packages/workflow-engine/
├── pyproject.toml
├── CHANGELOG.md
├── README.md
└── src/workflow_engine/
    ├── __init__.py
    ├── config.py                    # EngineConfig
    ├── models/
    │   ├── workflow.py, node.py, execution.py, version.py
    │   ├── trigger.py, context.py, events.py, tenant.py
    │   ├── provider.py, errors.py
    │   ├── responses.py             # NEW: PaginatedResponse, ErrorResponse
    │   └── requests.py              # NEW: API request schemas
    ├── dag/          (parser, topo_sort, parallel, plan)
    ├── nodes/        (registry, base, 7 types, custom)
    ├── validation/   (pipeline, 7 checkers)
    ├── executor/     (orchestrator, node_executor, dispatcher, retry, timeout)
    ├── state/        (machine, transitions, persistence)
    ├── context/
    │   ├── manager.py, redis_store.py, gcs_store.py, resolver.py
    │   └── trace.py                 # NEW: OTel propagation
    ├── sandbox/      (manager, restricted, container, limits)
    ├── providers/    (base, registry, router, 3 providers, tool_calling, rate_limiter)
    ├── integrations/ (mcp_client, tool_executor, rest_adapter, webhook_handler, oauth_manager)
    ├── cache/        (semantic, mcp_cache, key_schema)
    ├── versioning/   (manager, snapshot, diff, pinning)
    ├── privacy/      (detector, masker, gdpr)
    ├── events/       (bus, handlers, audit)
    ├── health/                      # NEW
    ├── scheduler/                   # NEW
    ├── billing/                     # NEW
    ├── auth/                        # NEW
    ├── notifications/               # NEW
    └── templates/                   # NEW
```

---

### 5.3 workflow-api Structure

```
packages/workflow-api/
├── pyproject.toml
├── Dockerfile
└── src/workflow_api/
    ├── main.py
    ├── dependencies.py
    ├── config.py
    ├── routes/
    │   ├── auth.py, workflows.py, executions.py, versions.py
    │   ├── nodes.py, schedules.py, logs.py, sandbox.py
    │   ├── templates.py, settings.py, api_keys.py
    │   ├── webhooks.py, health.py, admin.py, metrics.py
    ├── websocket/
    │   ├── hub.py, events.py
    ├── auth/
    │   ├── jwt.py, api_key.py, oauth.py, mfa.py
    │   ├── signup.py, password_reset.py
    ├── middleware/
    │   ├── tenant.py, rate_limit.py, cors.py
    │   ├── logging.py, tracing.py, semaphore.py
    └── tests/
        ├── conftest.py
        ├── test_routes/, test_auth/, test_middleware/
        └── test_integration/
```

---

### 5.4 workflow-worker Structure

```
packages/workflow-worker/
├── pyproject.toml
├── Dockerfile
└── src/workflow_worker/
    ├── celery_app.py
    ├── config.py
    ├── context_builder.py           # Build SDK objects from config
    ├── tasks/
    │   ├── orchestrator.py, node_runner.py, cleanup.py
    │   ├── scheduler.py, human_callback.py, notifications.py
    │   └── export.py
    ├── signals.py
    └── tests/
        ├── conftest.py
        └── test_tasks/
```

---

### 5.5 workflow-ui (Frontend) Structure

```
apps/workflow-ui/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── src/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   ├── signup/page.tsx
│   │   │   ├── forgot-password/page.tsx
│   │   │   ├── reset-password/[token]/page.tsx
│   │   │   └── verify-email/[token]/page.tsx
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx            # Sidebar + topbar layout
│   │   │   ├── page.tsx              # Dashboard home
│   │   │   ├── workflows/
│   │   │   │   ├── page.tsx          # Workflow list
│   │   │   │   ├── new/page.tsx      # New workflow
│   │   │   │   └── [id]/
│   │   │   │       ├── page.tsx      # Workflow editor
│   │   │   │       └── runs/
│   │   │   │           ├── page.tsx  # Run history
│   │   │   │           └── [run_id]/page.tsx
│   │   │   ├── runs/page.tsx         # All runs
│   │   │   ├── sandbox/page.tsx
│   │   │   ├── schedules/page.tsx
│   │   │   ├── logs/page.tsx
│   │   │   ├── metrics/page.tsx
│   │   │   ├── templates/page.tsx
│   │   │   └── settings/
│   │   │       ├── layout.tsx        # Settings tab layout
│   │   │       ├── profile/page.tsx
│   │   │       ├── security/page.tsx
│   │   │       ├── team/page.tsx
│   │   │       ├── api-keys/page.tsx
│   │   │       ├── integrations/page.tsx
│   │   │       ├── notifications/page.tsx
│   │   │       └── billing/page.tsx
│   │   ├── api/                      # Next.js API routes (BFF)
│   │   │   └── auth/[...nextauth]/route.ts
│   │   ├── error.tsx
│   │   ├── loading.tsx
│   │   └── layout.tsx
│   ├── components/
│   │   ├── auth/        (LoginForm, SignupWizard, MFAVerifyForm...)
│   │   ├── dashboard/   (StatsGrid, RecentWorkflows, ExecutionTimeline...)
│   │   ├── nodes/       (TriggerNode, AINode, MCPNode, APINode, LogicNode, TransformNode, HumanNode, BaseNode)
│   │   ├── canvas/      (WorkflowCanvas, NodePalette, NodeConfigPanel, VersionHistory)
│   │   ├── execution/   (RunMonitor, ExecutionLog, GanttChart, NodeOutputExplorer)
│   │   ├── sandbox/     (SandboxEditor, OutputPanel)
│   │   ├── scheduler/   (ScheduleCard, CronBuilder, CronPresets)
│   │   ├── logs/        (LogTable, LogFilters, LogDetailDrawer)
│   │   ├── metrics/     (ExecutionVolume, TokenUsage, CostBreakdown, ProviderHealth)
│   │   ├── settings/    (ApiKeyList, MFASetup, MemberList, BillingCard...)
│   │   ├── templates/   (TemplateCard, TemplatePreviewCanvas)
│   │   └── ui/          (shadcn components, custom primitives)
│   ├── hooks/
│   │   ├── useRunWebSocket.ts
│   │   ├── useAutoSave.ts
│   │   ├── useNodeConfig.ts
│   │   ├── useUndoRedo.ts
│   │   └── useSSEStream.ts
│   ├── stores/
│   │   ├── authStore.ts
│   │   ├── workflowStore.ts
│   │   ├── uiStore.ts
│   │   └── notificationStore.ts
│   ├── lib/
│   │   ├── api-client.ts
│   │   ├── api/             (workflows, executions, nodes, auth, sandbox...)
│   │   ├── schema-to-form.ts  (JSON Schema → React Hook Form fields)
│   │   └── workflow-serializer.ts  (React Flow ↔ WorkflowDefinition JSON)
│   └── types/
│       ├── api.ts           (generated from SDK response schemas)
│       ├── workflow.ts
│       └── execution.ts
├── public/
│   ├── fonts/, icons/, images/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/                  (Playwright)
```

---

## 6. Development Phases

### Phase 1 — Foundation: SDK + Core Backend (Weeks 1–6)

**Goal:** SDK complete with all 20 modules. API scaffold with auth and workflow CRUD. Workers process basic executions.

**SDK Deliverables:**
- All existing 14 modules fully implemented and tested
- 6 new modules: `engine.health`, `engine.scheduler`, `engine.billing`, `engine.auth`, `engine.notifications`, `engine.templates`
- Model updates: `responses.py`, `requests.py`, new error types, HTTP-mappable exceptions
- 80%+ unit test coverage on SDK

**Backend Deliverables:**
- `workflow-api`: Auth routes (login/signup/JWT/refresh), Workflow CRUD, Executions trigger + status
- `workflow-worker`: `orchestrate_run`, `execute_single_node`, `cleanup_run`
- PostgreSQL schema: users, tenants, api_keys
- MongoDB collections: workflows, workflow_versions, execution_runs, audit_log
- Redis: broker, semaphore, rate limit counters configured

**Exit Criteria:** API can receive a workflow JSON, validate it via SDK, store it, trigger execution, worker runs it end-to-end with 3-node workflow (Trigger → AI → API).

---

### Phase 2 — Workflow Engine & Extended API (Weeks 7–10)

**Goal:** Full API surface. Scheduler operational. Notifications working. Observability instrumentation complete.

**Deliverables:**
- All API route groups: schedules, logs, sandbox, templates, settings, api_keys, webhooks, metrics
- MFA, OAuth login (Google, GitHub)
- Scheduler service with cron scheduling via Celery beat
- Notification service: email + Slack on run completion
- Sandbox endpoint using `engine.sandbox`
- OTel tracing end-to-end (API span → Worker span → SDK spans)
- Prometheus metrics exported; Grafana dashboards drafted

**Exit Criteria:** Developer can use CLI to deploy workflows, trigger them, schedule them, and receive Slack notifications on completion. All API endpoints tested.

---

### Phase 3 — Frontend Core (Weeks 11–16)

**Goal:** Login through workflow execution working in browser. Core user journey complete.

**Deliverables:**
- Auth flow: login, signup, email verification, password reset
- Dashboard home with real metrics
- Workflow list + create + delete
- Workflow builder canvas (all 7 node types draggable, configurable)
- Auto-save + validation inline
- Execution trigger + real-time WebSocket monitoring
- Run detail page with log stream and node output explorer
- Settings: profile, password, API keys

**Exit Criteria:** A user can sign up, create a workflow with 3 nodes, run it in the browser, and watch it execute node by node in real time.

---

### Phase 4 — Advanced Features (Weeks 17–20)

**Goal:** Platform feature-complete. All modules from Phase 1–3 polished.

**Deliverables:**
- Sandbox playground UI
- Scheduler UI (visual cron builder, schedule CRUD)
- Observability: structured logs with filtering, execution metrics charts, token cost tracking
- Templates gallery with clone-to-editor
- Settings: team members, integrations (OAuth connect), notifications, billing
- Version history with visual diff
- Workflow import/export (ZIP bundle)
- Human node approval UI (form submission from email link or web)

**Exit Criteria:** Platform is usable end-to-end by non-technical users. Feature parity with basic n8n/Zapier-style platforms.

---

### Phase 5 — Optimization, Scaling & Production Readiness (Weeks 21–24)

**Goal:** Production-hardened, load-tested, security-scanned, documented.

**Deliverables:**
- Kubernetes manifests for all services (GKE deployment)
- Terraform IaC for all cloud resources
- Load testing: Locust, 1000 concurrent executions
- Security: OWASP ZAP API scan, Snyk dependency audit
- Performance: API p99 < 200ms, builder canvas < 100ms interaction
- E2E tests: Playwright covering 15 critical user paths
- Runbooks: worker crash, Redis failover, MongoDB failover, provider outage
- API documentation (OpenAPI), user guide, admin guide

**Exit Criteria:** System passes load test, security scan, and all automated tests. Runbooks reviewed by ops team. Ready for first external users.

---

> **AI Workflow Builder Platform — Full-Stack Development Roadmap**
> 20 SDK modules · workflow-api · workflow-worker · workflow-scheduler · workflow-cli · workflow-ui
> 9 frontend modules · 5 backend services · 5 development phases
> Platform vision: Production-grade AI workflow automation (n8n + Vellum + internal SDK)
