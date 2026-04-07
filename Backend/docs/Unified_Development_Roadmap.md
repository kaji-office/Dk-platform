# AI Workflow Builder — Unified Development Roadmap
### workflow-api · workflow-worker · workflow-cli · SDK Alignment
> **Scope:** This document extends the existing SDK development plan with complete designs for workflow-api (FastAPI), workflow-worker (Celery), and workflow-cli (Click). All three components are thin consumers of the `workflow-engine` SDK. No workflow logic lives outside the SDK.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [SDK Alignment & Gap Analysis](#2-sdk-alignment--gap-analysis)
3. [workflow-api — FastAPI Backend](#3-workflow-api--fastapi-backend)
4. [workflow-worker — Celery Task Workers](#4-workflow-worker--celery-task-workers)
5. [workflow-cli — Click Interface](#5-workflow-cli--click-interface)
6. [Cross-Component Integration Patterns](#6-cross-component-integration-patterns)
7. [Project Structures](#7-project-structures)
8. [Development Phases](#8-development-phases)

---

## 1. System Architecture Overview

### 1.1 Component Interaction Map

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL ACTORS                                                                  │
│                                                                                  │
│   Browser (UI)          Developer (CLI)         External Systems (Webhooks)      │
│       │                      │                          │                        │
└───────┼──────────────────────┼──────────────────────────┼────────────────────────┘
        │ HTTPS/WSS            │ Local SDK import          │ HTTPS POST
        ▼                      │ + HTTP to API             ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — DELIVERY SERVICES                                                      │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐                 │
│  │  workflow-api (FastAPI + uvicorn)                           │                 │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────────┐  │                 │
│  │  │ routes/  │ │websocket/ │ │  auth/   │ │ middleware/ │  │                 │
│  │  │workflows │ │   hub.py  │ │ jwt.py   │ │ rate_limit  │  │                 │
│  │  │executions│ │ events.py │ │ api_key  │ │ tenant_ctx  │  │                 │
│  │  │versions  │ └───────────┘ │ oauth.py │ │  semaphore  │  │                 │
│  │  │nodes     │               └──────────┘ └─────────────┘  │                 │
│  │  │webhooks  │  Publishes to Redis ──────────────────────────┼──────────┐     │
│  │  └──────────┘  Dispatches to Celery ─────────────────────────────────┐ │     │
│  └─────────────────────────────────────────────────────────────┘       │ │     │
│                                                                          │ │     │
│  ┌─────────────────────────────────┐    ┌───────────────────────────┐   │ │     │
│  │  workflow-worker (Celery)       │    │  workflow-cli (Click)     │   │ │     │
│  │  ┌──────────────────────────┐   │    │  ┌──────────────────────┐ │   │ │     │
│  │  │ tasks/orchestrator.py   │◄──┼────┘  │ commands/validate    │ │   │ │     │
│  │  │ tasks/node_runner.py    │   │        │ commands/deploy       │ │   │ │     │
│  │  │ tasks/cleanup.py        │   │        │ commands/run          │ │   │ │     │
│  │  │ tasks/scheduler.py      │   │        │ commands/logs         │ │   │ │     │
│  │  └──────────────────────────┘   │        │ commands/versions     │ │   │ │     │
│  │  Publishes events to Redis ─────┼────────┼─────────────────────┘ │   │ │     │
│  └─────────────────────────────────┘        └───────────────────────┘   │ │     │
│                        │                                                  │ │     │
│                        │ imports                                          │ │     │
└────────────────────────┼──────────────────────────────────────────────────┼─┼────┘
                         ▼                                                  │ │
┌───────────────────────────────────────────────────────────────────────────┼─┼────┐
│  LAYER 3 — workflow-engine (SDK)                                          │ │    │
│                                                                            │ │    │
│  Sub-Layer A: engine.models  engine.config                                │ │    │
│  Sub-Layer B: engine.dag  engine.nodes  engine.validation                 │ │    │
│  Sub-Layer C: engine.executor  engine.state  engine.context               │ │    │
│  Sub-Layer D: engine.providers  engine.integrations  engine.sandbox       │ │    │
│               engine.cache  engine.versioning  engine.privacy  engine.events│    │
└────────────────────────────────────────────────────────────────────────────┼─┼────┘
                                                                             │ │
┌────────────────────────────────────────────────────────────────────────────┼─┼────┐
│  LAYER 2 — MESSAGE BUS & STORAGE                                           │ │    │
│                                                                            │ │    │
│  Redis ◄────────────────────────────────────────────────────────────────── │ │    │
│  (Celery broker, pub/sub, rate-limit counters, context store, semaphores)  │ │    │
│                                                                             │ │    │
│  MongoDB ─ Workflow defs, versions, execution runs, audit trail            │ │    │
│  PostgreSQL+pgvector ─ Users, tenants, embeddings, billing, OAuth creds    │ │    │
│  GCS ─ Large node outputs (>64KB), file uploads                            │ │    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 1.2 Communication Patterns

#### 1.2.1 REST API (Synchronous — UI/CLI → API)

| Path | Method | Consumer | SDK Calls Made |
|---|---|---|---|
| `/api/v2/workflows` | POST/GET/PUT/DELETE | UI, CLI | `validation.validate()`, `versioning.create_version()` |
| `/api/v2/executions` | POST | UI, CLI | `versioning.pin_for_execution()`, `privacy.scan_dict()` |
| `/api/v2/executions/{id}` | GET | UI, CLI | — (MongoDB read) |
| `/api/v2/executions/{id}/cancel` | POST | UI, CLI | `state.transition_run(CANCELLED)` |
| `/api/v2/nodes/types` | GET | UI | `nodes.registry.list_all()` |
| `/api/v2/nodes/types/{type}/schema` | GET | UI | `nodes.registry.get_config_schema()` |
| `/api/v2/workflows/{id}/versions` | GET | UI, CLI | `versioning.list_versions()` |
| `/api/v2/workflows/{id}/versions/{v}/rollback` | POST | UI, CLI | `versioning.rollback()` |
| `/api/v2/webhooks/{path}` | POST | External systems | `integrations.webhook_handler.validate()` |

#### 1.2.2 Message Queue (Async — API → Worker via Redis/Celery)

```
workflow-api                          Redis (Celery Broker)              workflow-worker
    │                                        │                                │
    │ orchestrate_run.delay(run_id, def)     │                                │
    │───────────────────────────────────────►│   Celery task message          │
    │                                        │──────────────────────────────►│
    │                                        │                         orchestrate_run()
    │                                        │                         calls SDK
    │                                        │                                │
    │                                        │   EventBus.publish(events)     │
    │           Redis Pub/Sub ◄──────────────┼────────────────────────────────│
    │ WebSocket hub subscribes               │
    │◄───────────────────────────────────────│
    │ forwards to browser                    │
```

**Queue routing:**
```
default  queue  → orchestrate_run, cleanup_run  (general workflows)
ai-heavy queue  → execute_single_node (AI/LLM nodes — GPU-adjacent workers)
critical queue  → webhook triggers, human node callbacks (always-on)
scheduled queue → cron trigger fire tasks (Celery beat)
```

#### 1.2.3 WebSocket (Real-time — API → UI)

```
Worker publishes event      Redis Pub/Sub          API WebSocket Hub      Browser
        │                       │                        │                   │
        │ EventBus.publish()    │                        │                   │
        │──────────────────────►│                        │                   │
        │                       │  PUBLISH ws:run:{id}   │                   │
        │                       │───────────────────────►│                   │
        │                       │                        │ SEND JSON event    │
        │                       │                        │──────────────────►│
        │                       │                        │                   │ update node colour
```

#### 1.2.4 CLI Interactions

```
CLI validate  →  workflow-engine SDK (local, no network)
CLI deploy    →  workflow-engine SDK (local validate) → workflow-api (HTTP PUT)
CLI run       →  workflow-api (HTTP POST /executions)
CLI logs      →  workflow-api (WebSocket /ws/runs/{id})
CLI versions  →  workflow-api (HTTP GET /versions)
```

---

### 1.3 Full Data Flow (Save → Execute → Complete)

```
Step  Component        Action                                          SDK Module Used
────  ─────────────    ──────────────────────────────────────────────  ────────────────
 1    CLI/UI           POST /api/v2/workflows {definition JSON}        —
 2    API              Auth: validate JWT / API key                    —
 3    API              Inject tenant from auth context                 —
 4    API              engine.validation.validate(definition, tenant)  validation
 5    API              engine.versioning.create_version(definition)    versioning
 6    API              MongoDB: upsert workflows collection            —
 7    CLI/UI           POST /api/v2/executions {workflow_id, input}    —
 8    API              Redis INCR tenant semaphore (concurrency check)  —
 9    API              engine.versioning.pin_for_execution(run_id)     versioning
10    API              engine.privacy.scan_dict(input)                 privacy
11    API              MongoDB insert ExecutionRun (QUEUED)            models
12    API              Celery: orchestrate_run.delay(run_id, def)       —
13    Worker           engine.dag.DAGParser().parse(definition)        dag
14    Worker           engine.state.transition_run(RUNNING)            state
15    Worker           engine.events.EventBus.publish(RunStarted)      events → Redis pub/sub → UI
16    Worker (loop)    engine.context.resolve_inputs(run_id, node_id)  context
17    Worker (loop)    engine.executor.NodeExecutor.execute(node, …)   executor
18    Worker (AI)      engine.cache.check_semantic(prompt, model)      cache
19    Worker (AI)      engine.providers.rate_limiter.acquire(model)    providers
20    Worker (AI)      engine.providers.router.route().generate(…)     providers → LLM API
21    Worker (tool)    engine.integrations.tool_executor.execute(…)    integrations → MCP/REST
22    Worker           engine.context.store_output(run_id, node_id, …) context → Redis/GCS
23    Worker           engine.state.transition_run(SUCCESS/FAILED)     state + events → UI
24    Worker           cleanup_run.delay() → release semaphore         —
```

---

## 2. SDK Alignment & Gap Analysis

### 2.1 Gaps Identified in Existing SDK Plan

After analyzing the SDK roadmap against the API, Worker, and CLI requirements, the following additions/refinements are needed in the SDK:

#### Gap 1 — Missing `engine.health` Module
**Problem:** The API's health check endpoint (`/health`, `/readyz`, `/livez`) needs to probe MongoDB, Redis, and PostgreSQL connectivity. This probing logic should live in the SDK, not the API.
**Fix:** Add `engine.health` sub-layer D module:

```
engine/health/
  checker.py    HealthChecker — async probe each storage dependency
  models.py     HealthStatus, DependencyStatus data models
  reporter.py   HealthReport — aggregates all dependency statuses
```

---

#### Gap 2 — Missing `engine.scheduler` Module  
**Problem:** Celery beat needs to fire cron-based TriggerNodeType executions. The scheduling logic (find workflows with cron triggers, compute next fire time, dispatch) must live in the SDK, not the worker.
**Fix:** Add `engine.scheduler` sub-layer D module:

```
engine/scheduler/
  cron_evaluator.py   CronEvaluator — parse cron_expr, compute next_fire
  trigger_finder.py   TriggerFinder — query MongoDB for due cron triggers
  dispatcher.py       SchedulerDispatcher — creates ExecutionRun and fires
```

---

#### Gap 3 — Missing `engine.billing` Module
**Problem:** The API and worker both need to track token usage and execution costs against tenant billing quotas. This belongs in the SDK.
**Fix:** Add `engine.billing` sub-layer D module:

```
engine/billing/
  usage_tracker.py    UsageTracker — record token counts per run per tenant
  quota_checker.py    QuotaChecker — validate tenant has remaining quota before execution
  cost_calculator.py  CostCalculator — compute cost from TokenUsage + model pricing
  report.py           BillingReport — monthly usage summary per tenant
```

---

#### Gap 4 — `engine.models` Missing API Response Schemas
**Problem:** The API needs typed response models (not just domain models) for HTTP responses: paginated lists, error envelopes, health responses. These should be defined in the SDK so the CLI's HTTP client can use the same types.
**Fix:** Add to `engine.models`:

```
engine/models/
  responses.py    PaginatedResponse[T], ErrorResponse, HealthResponse,
                  WorkflowSummary, ExecutionSummary, NodeTypeSummary
  requests.py     CreateWorkflowRequest, TriggerExecutionRequest,
                  RollbackRequest, ValidateRequest
```

---

#### Gap 5 — `engine.context` Missing Trace Propagation
**Problem:** OpenTelemetry trace IDs assigned at the API must propagate through the Celery task message to the worker. The SDK's executor needs to accept and continue a trace context.
**Fix:** Add to `engine.context`:

```
engine/context/
  trace.py    TraceContextCarrier — serialize/deserialize OTel context for Redis messages
              propagate_to_task(context, task_kwargs)
              extract_from_task(task_kwargs) → context
```

---

#### Gap 6 — `engine.models.errors` Missing HTTP-Mappable Errors
**Problem:** The API needs to map SDK errors to HTTP status codes. Each SDK exception needs an `http_status_code` attribute so the API's exception handler can respond correctly.
**Fix:** Update `engine.models.errors`:

```python
class EngineError(Exception):
    http_status_code: int = 500  # add to all exception classes

class ValidationError(EngineError):
    http_status_code = 422

class NotFoundError(EngineError):     # NEW
    http_status_code = 404

class ConflictError(EngineError):      # NEW — workflow already exists
    http_status_code = 409

class QuotaExceededError(EngineError): # NEW — billing quota
    http_status_code = 429

class ForbiddenError(EngineError):     # NEW — plan tier
    http_status_code = 403
```

---

#### Gap 7 — `engine.versioning` Missing `get_workflow_at_version()`
**Problem:** The CLI's `wf diff` command needs to load a specific workflow version without a running API. The versioning module needs a direct query method.
**Fix:** Add to `VersionManager`:

```python
async def get_version(self, workflow_id: str, version_number: int) -> WorkflowVersion: ...
async def get_latest(self, workflow_id: str) -> WorkflowVersion: ...
```

---

### 2.2 Updated SDK Module Table (with additions)

| Module | Sub-layer | Status | Notes |
|---|---|---|---|
| `engine.config` | A | Existing | No change |
| `engine.models` | A | **Updated** | Add responses.py, requests.py, new error types |
| `engine.dag` | B | Existing | No change |
| `engine.nodes` | B | Existing | No change |
| `engine.validation` | B | Existing | No change |
| `engine.executor` | C | Existing | No change |
| `engine.state` | C | Existing | No change |
| `engine.context` | C | **Updated** | Add trace.py for OTel propagation |
| `engine.sandbox` | D | Existing | No change |
| `engine.providers` | D | Existing | No change |
| `engine.integrations` | D | Existing | No change |
| `engine.cache` | D | Existing | No change |
| `engine.versioning` | D | **Updated** | Add get_version(), get_latest() |
| `engine.privacy` | D | Existing | No change |
| `engine.events` | D | Existing | No change |
| `engine.health` | D | **NEW** | HealthChecker, HealthReport |
| `engine.scheduler` | D | **NEW** | CronEvaluator, TriggerFinder, SchedulerDispatcher |
| `engine.billing` | D | **NEW** | UsageTracker, QuotaChecker, CostCalculator |

---

## 3. workflow-api — FastAPI Backend

### 3.1 Architecture Principles

- **Thin shell only.** Every non-transport concern delegates to the SDK.
- **Async throughout.** All route handlers, middleware, and DB operations are `async`.
- **Dependency injection.** FastAPI's `Depends()` system injects all SDK objects, DB clients, and auth context into route handlers.
- **Lifespan management.** Connections (MongoDB, PostgreSQL, Redis) opened on startup, closed on shutdown via `@asynccontextmanager` lifespan.
- **Structured error responses.** A global exception handler maps SDK exceptions to HTTP status codes using `exception.http_status_code`.

---

### 3.2 Module Breakdown

#### 3.2.1 Entry Point (`main.py`)

```python
# Responsibilities:
# 1. Create FastAPI(lifespan=lifespan) app instance
# 2. Include all routers with /api/v2 prefix
# 3. Register global exception handler
# 4. Mount CORS, GZip, request ID middleware
# 5. OpenAPI schema customization (title, version, security schemes)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP:
    # - Connect motor MongoDB client → test connectivity
    # - Create asyncpg PostgreSQL connection pool → run migrations check
    # - Connect redis[asyncio] → test PING
    # - Build EngineConfig from environment
    # - Initialize NodeTypeRegistry (register all 7 built-in nodes)
    # - Initialize TenantSemaphore
    # - Start WebSocket hub background task (Redis subscriber)
    yield
    # SHUTDOWN:
    # - Close MongoDB client
    # - Close PostgreSQL pool
    # - Close Redis connection
    # - Cancel WebSocket hub task
```

**Components:**

| Component | File | Responsibility |
|---|---|---|
| FastAPI app | `main.py` | App creation, router mounting, middleware registration |
| Lifespan manager | `main.py` | Startup/shutdown DB connections and SDK initialization |
| Global exception handler | `main.py` | Maps EngineError subclasses → HTTP status + structured error response |
| OpenAPI config | `main.py` | Custom schema title, version, security scheme definitions |
| Request ID middleware | `main.py` | Inject X-Request-ID header; propagate to logs and OTel spans |

---

#### 3.2.2 Dependencies (`dependencies.py`)

All SDK objects and DB clients are provided to route handlers via FastAPI's DI:

| Dependency Function | Returns | Scope |
|---|---|---|
| `get_engine_config()` | `EngineConfig` | Singleton (app-scoped) |
| `get_mongo_db()` | `AsyncIOMotorDatabase` | Per-request (from connection pool) |
| `get_pg_pool()` | `asyncpg.Pool` | Per-request (from connection pool) |
| `get_redis()` | `redis.asyncio.Redis` | Per-request (from connection pool) |
| `get_node_registry()` | `NodeTypeRegistry` | Singleton |
| `get_tenant_semaphore()` | `TenantSemaphore` | Singleton |
| `get_current_tenant()` | `Tenant` | Per-request (from JWT/API key auth) |
| `get_current_user_id()` | `str` | Per-request (from JWT) |
| `get_validation_pipeline()` | `ValidationPipeline` | Per-request (depends on registry) |
| `get_version_manager()` | `VersionManager` | Per-request (depends on mongo, config) |
| `get_state_machine()` | `StateMachine` | Per-request (depends on mongo) |

---

#### 3.2.3 Routes

##### `routes/workflows.py`

| Endpoint | Method | Handler Function | SDK Calls | DB Ops |
|---|---|---|---|---|
| `/api/v2/workflows` | POST | `create_workflow` | `validation.validate()`, `versioning.create_version()` | MongoDB insert |
| `/api/v2/workflows` | GET | `list_workflows` | — | MongoDB find (paginated, tenant-scoped) |
| `/api/v2/workflows/{workflow_id}` | GET | `get_workflow` | — | MongoDB findOne |
| `/api/v2/workflows/{workflow_id}` | PUT | `update_workflow` | `validation.validate()`, `versioning.create_version()` | MongoDB update |
| `/api/v2/workflows/{workflow_id}` | DELETE | `delete_workflow` | — | MongoDB soft-delete (set deleted_at) |
| `/api/v2/workflows/{workflow_id}/duplicate` | POST | `duplicate_workflow` | `versioning.create_version()` | MongoDB insert copy |

##### `routes/executions.py`

| Endpoint | Method | Handler Function | SDK Calls | DB Ops |
|---|---|---|---|---|
| `/api/v2/executions` | POST | `trigger_execution` | `versioning.pin_for_execution()`, `privacy.scan_dict()`, `billing.quota_checker.check()` | MongoDB insert ExecutionRun, Redis semaphore INCR |
| `/api/v2/executions` | GET | `list_executions` | — | MongoDB find (paginated, filterable by status/workflow) |
| `/api/v2/executions/{run_id}` | GET | `get_execution` | — | MongoDB findOne |
| `/api/v2/executions/{run_id}/cancel` | POST | `cancel_execution` | `state.transition_run(CANCELLED)` | — (state machine persists) |
| `/api/v2/executions/{run_id}/retry` | POST | `retry_execution` | `versioning.pin_for_execution()` | MongoDB insert new run |
| `/api/v2/executions/{run_id}/nodes` | GET | `get_execution_nodes` | — | MongoDB findOne → return node_states map |

##### `routes/versions.py`

| Endpoint | Method | Handler Function | SDK Calls |
|---|---|---|---|
| `/api/v2/workflows/{id}/versions` | GET | `list_versions` | `versioning.list_versions()` |
| `/api/v2/workflows/{id}/versions/{v}` | GET | `get_version` | `versioning.get_version()` |
| `/api/v2/workflows/{id}/versions/{v1}/diff/{v2}` | GET | `get_diff` | `versioning.compute_diff()` |
| `/api/v2/workflows/{id}/versions/{v}/rollback` | POST | `rollback_version` | `versioning.rollback()` |

##### `routes/nodes.py`

| Endpoint | Method | Handler Function | SDK Calls |
|---|---|---|---|
| `/api/v2/nodes/types` | GET | `list_node_types` | `nodes.registry.list_all()` |
| `/api/v2/nodes/types/{type}` | GET | `get_node_type` | `nodes.registry.get()` |
| `/api/v2/nodes/types/{type}/schema` | GET | `get_node_schema` | `nodes.registry.get_config_schema()` |
| `/api/v2/nodes/validate-config` | POST | `validate_node_config` | `nodes.registry.get().validate_config()` |

##### `routes/webhooks.py`

| Endpoint | Method | Handler Function | SDK Calls |
|---|---|---|---|
| `/api/v2/webhooks/{path}` | POST | `receive_webhook` | `integrations.webhook_handler.validate_signature()` → find trigger workflow → `trigger_execution()` |

##### `routes/health.py`

| Endpoint | Method | Handler Function | SDK Calls |
|---|---|---|---|
| `/health` | GET | `health_check` | `engine.health.checker.check_all()` |
| `/readyz` | GET | `readiness_check` | `engine.health.checker.check_all()` (strict) |
| `/livez` | GET | `liveness_check` | Simple 200 OK (process alive) |

##### `routes/admin.py` *(internal — not exposed to end users)*

| Endpoint | Method | Handler Function | Action |
|---|---|---|---|
| `/admin/tenants` | POST | `create_tenant` | PostgreSQL insert new tenant |
| `/admin/tenants/{id}/quota` | PUT | `update_quota` | PostgreSQL update billing quota |
| `/admin/gdpr/delete` | POST | `gdpr_delete` | `engine.privacy.gdpr.delete_user_data()` |

---

#### 3.2.4 WebSocket (`websocket/`)

| File | Class/Function | Responsibility |
|---|---|---|
| `hub.py` | `WebSocketHub` | Singleton. Manages all active WS connections. |
| `hub.py` | `connect(websocket, run_id, tenant_id)` | Accept WS, validate tenant owns run_id, subscribe to Redis channel |
| `hub.py` | `disconnect(websocket, run_id)` | Unsubscribe, remove from active connections |
| `hub.py` | `_redis_subscriber_task()` | Background asyncio task — listens to Redis pub/sub, fans out to WS clients |
| `hub.py` | `_heartbeat_task(websocket)` | Send `{"type":"ping"}` every 30s; disconnect if no pong within 10s |
| `events.py` | `WsEventSchema` | Pydantic models for each WS event type: `RunStarted`, `NodeStarted`, `NodeCompleted`, `NodeFailed`, `RunCompleted`, `RunFailed`, `Ping`/`Pong` |

---

#### 3.2.5 Auth (`auth/`)

| File | Class | Responsibility |
|---|---|---|
| `jwt.py` | `JWTValidator` | Decode and verify JWT (RS256). Extract tenant_id, user_id, roles. Handle expiry, signature failure. |
| `jwt.py` | `JWTConfig` | Algorithm, public key (loaded from GCP Secret Manager on startup). Audience validation. |
| `api_key.py` | `APIKeyValidator` | Hash incoming `X-API-Key` (SHA-256). Query PostgreSQL api_keys table. Return Tenant. Rate-limit API key lookups. |
| `oauth.py` | `OAuthFlow` | Authorization code flow for external integrations (Google, GitHub). Store credentials via `engine.integrations.oauth_manager`. |
| `permissions.py` | `PermissionChecker` | FastAPI dependency. Checks tenant plan tier against requested operation. Raises `ForbiddenError`. |

**Auth flow:**
```
Request → TenantContextMiddleware
            → X-API-Key header? → APIKeyValidator → get Tenant from PostgreSQL
            → Authorization header? → JWTValidator → decode → get Tenant
            → Neither? → 401 Unauthorized
          → Inject tenant into request.state.tenant
          → Route handler uses get_current_tenant() dependency
```

---

#### 3.2.6 Middleware (`middleware/`)

| File | Class | Responsibility |
|---|---|---|
| `tenant.py` | `TenantContextMiddleware` | Extract and validate auth on every request. Inject `request.state.tenant`. |
| `rate_limit.py` | `APIRateLimitMiddleware` | Per-tenant request rate limiting. Key: `api_rate:{tenant_id}:{window}`. Redis INCR. Return 429 on exceed. |
| `semaphore.py` | `TenantSemaphore` | Per-tenant concurrent execution limiter. Redis INCR/DECR. Return 429 if over `max_concurrent_runs`. |
| `cors.py` | CORS config | Allow configured origins. Expose headers: X-Request-ID, X-Run-ID. |
| `logging.py` | `StructuredLoggingMiddleware` | Emit request/response log as JSON with tenant_id, request_id, duration_ms. PII-mask via SDK. |
| `tracing.py` | `OTelTracingMiddleware` | Create root OTel span per request. Propagate trace context into Celery task kwargs. |

---

#### 3.2.7 Error Handling

**Global exception handler strategy:**

```python
@app.exception_handler(EngineError)
async def engine_error_handler(request: Request, exc: EngineError):
    return JSONResponse(
        status_code=exc.http_status_code,
        content={
            "error": type(exc).__name__,
            "message": str(exc),
            "request_id": request.state.request_id,
        }
    )
```

| SDK Exception | HTTP Status | API Response |
|---|---|---|
| `ValidationError` | 422 | `{"error": "ValidationError", "validation_errors": [...]}` |
| `NotFoundError` | 404 | Standard error envelope |
| `ConflictError` | 409 | Standard error envelope |
| `ForbiddenError` | 403 | Standard error envelope |
| `QuotaExceededError` | 429 | With `retry_after` header |
| `ProviderRateLimitError` | 429 | With `retry_after` from error |
| `EngineError` (base) | 500 | Internal server error (sanitized message) |
| `RequestValidationError` (FastAPI) | 422 | Pydantic field errors |

---

#### 3.2.8 Observability

| Signal | Implementation |
|---|---|
| **Traces** | OTelTracingMiddleware creates root span per request. Span attributes: tenant_id, workflow_id, run_id, route. Exported to GCP Trace. |
| **Metrics** | Prometheus `/metrics` endpoint. Track: `api_request_duration_seconds` histogram, `api_requests_total` counter (labels: route, status, tenant_plan). |
| **Logging** | StructuredLoggingMiddleware. JSON format: timestamp, level, request_id, tenant_id, method, path, status, duration_ms. PII-masked. |
| **Health** | `/health` probes all dependencies. `/readyz` for Kubernetes readiness. `/livez` for liveness. |

---

#### 3.2.9 Security Considerations

| Concern | Control |
|---|---|
| Auth bypass | Every route requires `get_current_tenant()` dependency (except `/health`, `/livez`, `/docs`) |
| Tenant data isolation | All MongoDB queries include `tenant_id` filter from auth context |
| API key brute force | Rate-limit API key validation endpoint; lock after N failures |
| Webhook replay | HMAC-SHA256 verification + timestamp check (reject if >5 minutes old) |
| SQL injection | asyncpg parameterized queries only; no string concatenation |
| Secrets in logs | PIIMasker applied in StructuredLoggingMiddleware before any output |
| CORS | Strict allowlist per environment; no wildcard in production |
| Admin endpoint protection | `/admin/*` routes protected by internal IP allowlist + service account JWT |

---

#### 3.2.10 Scalability

| Concern | Design |
|---|---|
| **Stateless instances** | All state in Redis/MongoDB — API instances are fully stateless |
| **Connection pooling** | Motor (MongoDB): pool_size=20. asyncpg (PG): min=5, max=20. redis[asyncio]: pool_size=10. |
| **HPA scaling** | Scale on CPU utilization > 70%. Min 2 replicas, max 10. |
| **WebSocket fan-out** | Hub uses Redis pub/sub — multiple API instances each subscribe to same channel; each serves its own WS clients |
| **Rate limiting** | Redis-based (not in-process) — consistent across all API instances |
| **Celery dispatch** | Fire-and-forget `.delay()` — API never blocks waiting for execution result |

---

## 4. workflow-worker — Celery Task Workers

### 4.1 Architecture Principles

- **Pure delegation.** Every task's body is ≤20 lines. All execution logic is in the SDK.
- **Graceful shutdown.** Workers handle SIGTERM by allowing in-flight tasks to complete before exit.
- **Idempotent tasks.** Each task can be safely retried — the SDK's state machine rejects duplicate transitions.
- **Trace propagation.** OTel trace context from the API is extracted and continued in every task.
- **Dead letter queue.** Failed tasks after all retries go to `dlq:{exec_id}` Redis key for manual inspection.

---

### 4.2 Module Breakdown

#### 4.2.1 Celery App (`celery_app.py`)

```python
# All configuration in one place.
# Never hardcode broker/backend URLs — read from EngineConfig.

celery_app = Celery("workflow-worker")
celery_app.config_from_object(CeleryConfig)  # defined in config.py

class CeleryConfig:
    broker_url: str                         # Redis URL from EngineConfig
    result_backend: str                     # Redis URL from EngineConfig
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: list = ["json"]
    task_track_started: bool = True
    task_acks_late: bool = True             # ACK only after completion (at-least-once)
    worker_prefetch_multiplier: int = 1     # One task at a time per process
    task_routes: dict = {                   # Queue routing
        "tasks.orchestrate_run":       {"queue": "default"},
        "tasks.execute_single_node":   {"queue": "ai-heavy"},
        "tasks.cleanup_run":           {"queue": "default"},
        "tasks.scheduler_fire_cron":   {"queue": "scheduled"},
        "tasks.handle_human_callback": {"queue": "critical"},
    }
    task_soft_time_limit: int = 600         # 10-min soft limit
    task_time_limit: int = 900              # 15-min hard limit (SIGKILL)
    worker_max_tasks_per_child: int = 100   # Recycle workers to prevent memory leaks
```

---

#### 4.2.2 Tasks

##### `tasks/orchestrator.py` — Main workflow run task

```python
@celery_app.task(
    bind=True,
    name="tasks.orchestrate_run",
    max_retries=0,                    # RunOrchestrator handles its own retries
    acks_late=True,
    reject_on_worker_lost=True,       # Requeue if worker dies mid-task
)
def orchestrate_run(self, run_id: str, definition_dict: dict, trace_context: dict):
    """
    Entry point for all workflow executions.
    Creates SDK objects, delegates entirely to RunOrchestrator.
    """
    # 1. Extract OTel trace context from task kwargs
    # 2. Deserialize WorkflowDefinition from definition_dict
    # 3. Build EngineConfig from environment
    # 4. Build all SDK service objects (StateMachine, ContextManager, etc.)
    # 5. Call RunOrchestrator.run(run, definition) — BLOCKS until complete
    # 6. On completion: dispatch cleanup_run.delay()
```

**SDK Objects Built In This Task:**

| SDK Object | Config Source |
|---|---|
| `EngineConfig` | Environment variables |
| `StateMachine` | `EngineConfig.mongodb_url` |
| `ContextManager` | `EngineConfig.redis_url`, `EngineConfig.gcs_bucket` |
| `NodeTypeRegistry` | Static (built-in 7 types) |
| `NodeExecutor` | Registry + SandboxManager |
| `EventBus` | `EngineConfig.redis_url` |
| `RunOrchestrator` | All of the above |

---

##### `tasks/node_runner.py` — Per-node task (for parallel execution)

```python
@celery_app.task(
    bind=True,
    name="tasks.execute_single_node",
    queue="ai-heavy",
    acks_late=True,
)
def execute_single_node(self, run_id: str, node_id: str, definition_dict: dict, trace_context: dict):
    """
    Executes a single node. Used as part of Celery group/chord for parallel branches.
    The chord callback runs the fan-in node after all parallel tasks complete.
    """
    # 1. Build SDK objects
    # 2. context.resolve_inputs(run_id, node_id, definition)
    # 3. node_executor.execute(node_config, inputs, run)
    # 4. context.store_output(run_id, node_id, output)
    # 5. state.transition_node(node_id, SUCCESS)
    # 6. event_bus.publish(NodeCompleted)
```

**Parallel execution pattern (Celery group + chord):**

```python
# In orchestrate_run, when RunOrchestrator signals PARALLEL step:
from celery import group, chord

parallel_tasks = group(
    execute_single_node.s(run_id, nid, definition_dict, trace_ctx)
    for nid in step.node_ids
)

# chord = run parallel, then fan-in callback when ALL complete
fan_in_callback = execute_single_node.s(run_id, fan_in_node_id, definition_dict, trace_ctx)
chord(parallel_tasks)(fan_in_callback)
```

---

##### `tasks/cleanup.py` — Post-run cleanup

```python
@celery_app.task(name="tasks.cleanup_run")
def cleanup_run(run_id: str, tenant_id: str):
    """
    Runs after every execution (success or failure).
    Idempotent — safe to retry.
    """
    # 1. Release tenant semaphore: Redis DECR tenant:{id}:exec_slots
    # 2. Delete execution context keys: Redis DEL ctx:{run_id}:*
    # 3. engine.billing.usage_tracker.record_run_cost(run_id, tenant_id)
    # 4. Log final run summary (node count, duration, token cost)
```

---

##### `tasks/scheduler.py` — Cron trigger dispatcher

```python
@celery_app.task(name="tasks.scheduler_fire_cron")
def scheduler_fire_cron():
    """
    Called by Celery beat every minute.
    Uses engine.scheduler to find and fire due cron workflows.
    """
    # 1. engine.scheduler.trigger_finder.find_due_triggers()
    # 2. For each due trigger: engine.scheduler.dispatcher.dispatch(trigger)
    # 3. Creates ExecutionRun + calls orchestrate_run.delay()
```

**Celery beat schedule (in `celery_app.py`):**

```python
celery_app.conf.beat_schedule = {
    "fire-cron-triggers": {
        "task": "tasks.scheduler_fire_cron",
        "schedule": crontab(minute="*"),  # Every minute
    },
    "cleanup-stale-semaphores": {
        "task": "tasks.cleanup_stale_semaphores",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
}
```

---

##### `tasks/human_callback.py` — Human node resume handler

```python
@celery_app.task(name="tasks.handle_human_callback", queue="critical")
def handle_human_callback(run_id: str, node_id: str, form_data: dict, approved_by: str):
    """
    Called when a human approves/rejects a HumanNode task.
    Resumes the paused workflow execution from the human node.
    """
    # 1. Validate form_data against node's form_schema
    # 2. Store form result in context: context.store_output(run_id, node_id, ...)
    # 3. state.transition_node(node_id, SUCCESS/FAILED)
    # 4. Dispatch orchestrate_run.delay() to continue remaining steps
```

---

#### 4.2.3 Signals (`signals.py`)

```python
from celery.signals import task_failure, task_revoked, worker_shutting_down

@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    """
    Catch unexpected Celery-level failures (not SDK NodeExecutionError — those are handled inside).
    Used for: infrastructure failures, OOM kills, unexpected exceptions.
    """
    run_id = kwargs.get("run_id")
    if run_id:
        # state.transition_run(run_id, FAILED, error=str(exception))
        # event_bus.publish(RunFailed)
        # cleanup_run.delay(run_id, tenant_id)
        # Write to DLQ: dlq:{exec_id}
        pass

@task_revoked.connect
def on_task_revoked(sender, request, terminated, signum, expired, **kw):
    """Handle cancelled tasks (from POST /executions/{id}/cancel)."""
    # state.transition_run(run_id, CANCELLED)

@worker_shutting_down.connect
def on_worker_shutdown(sender, sig, how, exitcode, **kw):
    """Log graceful shutdown; give in-flight tasks 30s to complete."""
    pass
```

---

#### 4.2.4 Worker Configuration (`config.py`)

```python
class WorkerConfig:
    """
    All worker-specific configuration.
    Built from EngineConfig + additional worker settings.
    """
    engine_config: EngineConfig          # Shared SDK config
    worker_concurrency: int              # Number of concurrent Celery processes
    worker_max_memory_mb: int            # Restart worker process if RSS exceeds this
    worker_pool: str = "prefork"         # "prefork" for CPU-bound, "gevent" for I/O-heavy
    task_always_eager: bool = False      # Set True in unit tests (no broker needed)
    dlq_redis_key_prefix: str = "dlq:"  # Dead letter queue key prefix
```

---

#### 4.2.5 Error Handling in Workers

| Error Type | Source | Handling Strategy |
|---|---|---|
| `NodeExecutionError` | SDK executor | Handled inside RunOrchestrator. Retry up to RetryPolicy.max_retries. Final fail → state=FAILED. |
| `ProviderRateLimitError` | SDK providers | Auto-retry with exponential backoff (handled by RetryHandler in SDK). |
| `SandboxTimeoutError` | SDK sandbox | Node fails immediately. No retry. State=FAILED with timeout in error. |
| `asyncio.TimeoutError` | Task-level timeout | `on_task_failure` signal catches. State=FAILED. DLQ entry. |
| `MemoryError` | OOM in worker | Worker process killed by OS. `reject_on_worker_lost=True` requeues. |
| `kombu.exceptions.OperationalError` | Redis connection lost | Celery auto-retries broker reconnection. |

---

#### 4.2.6 Observability

| Signal | Implementation |
|---|---|
| **Traces** | Extract OTel context from `trace_context` task kwarg. Create child span `celery.task.{task_name}`. Add run_id, node_id, tenant_id as span attributes. |
| **Metrics** | `celery_task_duration_seconds` histogram per task_name. `celery_task_failures_total` counter per task_name + error_type. |
| **Logging** | Structured JSON log per task start/end. Include trace_id, run_id, worker_pid. PII-masked via SDK. |
| **Queue depth** | Custom Prometheus exporter scrapes Redis `LLEN` for each queue. Used as HPA custom metric. |

---

#### 4.2.7 Scaling Strategy

| Queue | Worker Pool | Min Replicas | Max Replicas | Scale Trigger |
|---|---|---|---|---|
| `default` | prefork (4 proc/pod) | 2 | 20 | Queue depth > 50 |
| `ai-heavy` | gevent (coroutines) | 2 | 15 | Queue depth > 10 |
| `critical` | prefork (2 proc/pod) | 2 | 4 | Always-on (never scale to 0) |
| `scheduled` | prefork (1 proc/pod) | 1 | 1 | Single Celery beat instance |

**Memory management:** `worker_max_tasks_per_child=100` — recycle worker processes to prevent LLM SDK memory accumulation over time.

---

## 5. workflow-cli — Click Interface

### 5.1 Architecture Principles

- **Local-first.** Operations that don't need the API (validate, diff) work without network access.
- **SDK-direct for offline ops.** `validate` and `diff` import the SDK directly — no HTTP call.
- **API client for online ops.** A thin `api_client.py` wraps httpx for all API calls.
- **Rich output.** All terminal output uses the `Rich` library: tables, progress bars, coloured status indicators.
- **Config file.** User's API URL, API key, and active profile stored in `~/.workflow/config.toml`.
- **Error exit codes.** All commands exit with non-zero codes on failure — safe for CI/CD use.

---

### 5.2 CLI Commands

| Command | Subcommands | Network Required | SDK Direct |
|---|---|---|---|
| `wf validate` | — | No | Yes (`ValidationPipeline`) |
| `wf deploy` | — | Yes (after local validate) | Yes (validate only) |
| `wf run` | — | Yes | No |
| `wf logs` | — | Yes (WebSocket) | No |
| `wf executions` | `list`, `get`, `cancel` | Yes | No |
| `wf versions` | `list`, `get`, `diff`, `rollback` | Yes (list/rollback); No (diff) | Yes (diff only) |
| `wf nodes` | `list`, `schema` | Yes | No |
| `wf config` | `set`, `get`, `list-profiles` | No | No |
| `wf init` | — | No | Yes (`WorkflowDefinition` template) |

---

### 5.3 Module Breakdown

#### 5.3.1 Entry Point (`main.py`)

```python
@click.group()
@click.option("--profile", default="default", envvar="WF_PROFILE")
@click.option("--api-url", envvar="WF_API_URL")
@click.option("--api-key", envvar="WF_API_KEY")
@click.option("--output", type=click.Choice(["table", "json", "yaml"]), default="table")
@click.pass_context
def cli(ctx, profile, api_url, api_key, output):
    """AI Workflow Builder CLI"""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_cli_config(profile)
    ctx.obj["api_client"] = APIClient(api_url or ctx.obj["config"].api_url, api_key or ctx.obj["config"].api_key)
    ctx.obj["output_format"] = output
```

---

#### 5.3.2 `commands/validate.py`

**Uses SDK directly — no API call.**

```
wf validate <file> [--strict] [--format json|table]

Options:
  --strict     Treat warnings as errors
  --format     Output format (default: table)

Exit codes:
  0   Valid
  1   Validation errors found
  2   File parse error
  3   Internal SDK error
```

**Output (Rich table):**

```
✓ Workflow: send-welcome-email (4 nodes, 3 steps)

  Steps:
  ┌─────┬──────────────┬────────────────────────────┬─────────┐
  │ #   │ Type         │ Nodes                      │ Status  │
  ├─────┼──────────────┼────────────────────────────┼─────────┤
  │ 1   │ SEQUENTIAL   │ trigger-webhook             │ ✓       │
  │ 2   │ PARALLEL     │ ai-draft, api-fetch-user    │ ✓       │
  │ 3   │ FAN_IN       │ api-send-email              │ ✓       │
  └─────┴──────────────┴────────────────────────────┴─────────┘
```

**On errors (exit code 1):**

```
✗ 3 validation errors in ./send-welcome.yaml

  Error 1: Port mismatch — ai-draft.output(JSON) → api-fetch.input(TEXT)
  Error 2: Missing required config: model in node 'ai-draft'
  Error 3: Cycle detected: fetch-user → ai-draft → fetch-user
```

---

#### 5.3.3 `commands/deploy.py`

```
wf deploy <file> [--workflow-id <id>] [--dry-run] [--wait]

Options:
  --workflow-id   Override workflow ID from file
  --dry-run       Validate only; do not deploy
  --wait          Wait for version to be confirmed active
```

**Flow:**

```
1. Parse YAML → WorkflowDefinition
2. engine.validation.validate() [LOCAL, no API]
   → If errors: print + exit 1
3. If --dry-run: print "Valid. Dry run complete." exit 0
4. api_client.put("/api/v2/workflows/{id}", definition)
5. Print: "✓ Deployed send-welcome-email (version 7)"
```

---

#### 5.3.4 `commands/run.py`

```
wf run <workflow-id> [--input <json>] [--input-file <path>] [--watch] [--timeout <seconds>]

Options:
  --input         JSON string of trigger inputs
  --input-file    Path to JSON file of trigger inputs
  --watch         Stream execution logs after triggering
  --timeout       Max seconds to wait (with --watch)
```

**Flow:**

```
1. api_client.post("/api/v2/executions", {workflow_id, input})
2. Print: "✓ Execution started — run_id: abc-123 (QUEUED)"
3. If --watch: hand off to logs command for streaming
```

---

#### 5.3.5 `commands/logs.py`

**Connects to WebSocket — streams real-time events.**

```
wf logs <run-id> [--follow] [--node <node-id>] [--level debug|info|warn|error]
```

**Output (Rich live display):**

```
Execution: abc-123 (workflow: send-welcome-email)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ● trigger-webhook    [SUCCESS]  0.1s
  ◉ ai-draft-email     [RUNNING]  3.2s  ██████████░░░░░░░░░░
  ● api-fetch-user     [SUCCESS]  0.8s
  ○ api-send-email     [PENDING]

  Events:
  10:32:01.123  [trigger-webhook]  Node started
  10:32:01.234  [trigger-webhook]  Node completed  output_bytes=128
  10:32:01.456  [ai-draft-email]   Node started
```

**Implementation:** `websockets` library + Rich `Live` context for in-place terminal update.

---

#### 5.3.6 `commands/versions.py`

```
wf versions list <workflow-id>
wf versions get <workflow-id> --version <num>
wf versions diff <workflow-id> --from <v1> --to <v2>     # SDK direct, no API
wf versions rollback <workflow-id> --to <version>
```

**`diff` uses SDK directly:**

```python
# wf versions diff send-welcome.yaml --from 3 --to 5
v1 = versioning_manager.get_version(workflow_id, 3)
v2 = versioning_manager.get_version(workflow_id, 5)
diff = versioning_manager.compute_diff(v1, v2)
# render Rich table: added/removed/changed nodes and edges
```

---

#### 5.3.7 `commands/executions.py`

```
wf executions list [--workflow-id <id>] [--status pending|running|success|failed] [--limit 20]
wf executions get <run-id>
wf executions cancel <run-id>
```

---

#### 5.3.8 `commands/nodes.py`

```
wf nodes list [--category ai|integration|logic|data|human]
wf nodes schema <node-type>
```

---

#### 5.3.9 `commands/config.py` (CLI Configuration)

```
wf config set api-url https://api.workflow.example.com
wf config set api-key <key>
wf config list-profiles
wf config use-profile production
```

**Config file `~/.workflow/config.toml`:**

```toml
[default]
api_url = "http://localhost:8000"
api_key = "wf_dev_abc123"

[production]
api_url = "https://api.workflow.example.com"
api_key = ""   # read from WF_API_KEY env var
```

---

#### 5.3.10 `commands/init.py` — Workflow scaffolding

```
wf init <name> [--template webhook|cron|manual] [--output <path>]
```

Generates a starter YAML workflow file using a template. Does not call the API.

---

#### 5.3.11 `api_client.py` — HTTP Client Wrapper

```python
class APIClient:
    """
    Thin httpx wrapper. All CLI-to-API communication goes through here.
    Handles: auth headers, base URL, timeout, error mapping, retry on 429.
    """

    def __init__(self, base_url: str, api_key: str):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def get(self, path: str, **params) -> dict: ...
    async def post(self, path: str, body: dict) -> dict: ...
    async def put(self, path: str, body: dict) -> dict: ...
    async def delete(self, path: str) -> dict: ...
    async def stream_websocket(self, path: str) -> AsyncIterator[dict]: ...

    def _handle_error_response(self, response: httpx.Response):
        # Map HTTP status to friendly CLI error messages
        if response.status_code == 401: raise CLIAuthError(...)
        if response.status_code == 422: raise CLIValidationError(response.json()["validation_errors"])
        if response.status_code == 404: raise CLINotFoundError(...)
        if response.status_code >= 500: raise CLIServerError(...)
```

---

#### 5.3.12 Error Handling in CLI

| Error | Source | User Output |
|---|---|---|
| `CLIAuthError` | 401 from API | `✗ Authentication failed. Check your API key (wf config set api-key <key>)` |
| `CLIValidationError` | 422 from API | Formatted validation error table |
| `CLINotFoundError` | 404 from API | `✗ Workflow 'abc' not found.` |
| `CLIServerError` | 5xx from API | `✗ API server error. Check the server logs.` |
| `httpx.ConnectError` | API unreachable | `✗ Cannot connect to API at <url>. Is the server running?` |
| `FileNotFoundError` | Missing YAML | `✗ File not found: ./flow.yaml` |
| `yaml.YAMLError` | Bad YAML syntax | `✗ YAML parse error at line 12: <detail>` |
| SDK `ValidationError` | Local validate | Formatted error table (exit code 1) |

---

#### 5.3.13 Observability

| Concern | Implementation |
|---|---|
| `--verbose` flag | Debug-level output: HTTP request/response details, SDK call timing |
| `--output json` | All commands support JSON output for CI/CD pipeline consumption |
| Exit codes | Consistent: 0=success, 1=user error, 2=validation error, 3=network error, 4=server error |
| `~/.workflow/cli.log` | Rolling log of all commands with timestamps (not shown to user unless `--verbose`) |

---

## 6. Cross-Component Integration Patterns

### 6.1 Trace Propagation (API → Worker)

```python
# In API (routes/executions.py):
from opentelemetry.propagate import inject

trace_context = {}
inject(trace_context)  # inject current span context as dict
orchestrate_run.delay(run_id, definition_dict, trace_context=trace_context)

# In Worker (tasks/orchestrator.py):
from opentelemetry.propagate import extract
from opentelemetry import trace

context = extract(trace_context)  # reconstruct span context
with trace.get_tracer(__name__).start_as_current_span("celery.orchestrate_run", context=context):
    orchestrator.run(run, definition)
```

### 6.2 Semaphore Lifecycle (API → Worker)

```
API (trigger_execution):
  Redis INCR tenant:{id}:exec_slots
  If value > max_slots: DECR + raise 429

Worker (cleanup_run):
  Redis DECR tenant:{id}:exec_slots  ← MUST always execute, even on failure
```

**Safety net:** `cleanup_stale_semaphores` Celery beat task runs every 5 minutes:
```python
# If exec_slots > 0 but no RUNNING executions for tenant → reset to 0
```

### 6.3 CLI → API Authentication

```
CLI config: api_key stored in ~/.workflow/config.toml
API client: sends X-API-Key header on every request
API middleware: APIKeyValidator hashes it → queries PostgreSQL api_keys table
```

### 6.4 SDK Version Consistency

All three consumers (API, worker, CLI) **must** pin the same SDK version:

```toml
# Each component's pyproject.toml
dependencies = ["workflow-engine==1.2.3"]  # Always exact pin
```

CI/CD pipeline runs `pip-compile --check` to verify version consistency across all packages before deploy.

---

## 7. Project Structures

### 7.1 SDK (Updated)

```
packages/workflow-engine/
├── pyproject.toml
└── src/workflow_engine/
    ├── __init__.py
    ├── config.py
    ├── models/
    │   ├── workflow.py, node.py, execution.py, version.py
    │   ├── trigger.py, context.py, events.py, tenant.py
    │   ├── provider.py, errors.py
    │   ├── responses.py          ← NEW: API response schemas
    │   └── requests.py           ← NEW: API request schemas
    ├── dag/           (parser, topo_sort, parallel, plan)
    ├── nodes/         (registry, base, 7 node types, custom)
    ├── validation/    (pipeline, 7 checkers)
    ├── executor/      (orchestrator, node_executor, dispatcher, retry, timeout)
    ├── state/         (machine, transitions, persistence)
    ├── context/
    │   ├── manager.py, redis_store.py, gcs_store.py, resolver.py
    │   └── trace.py              ← NEW: OTel context propagation
    ├── sandbox/       (manager, restricted, container, limits)
    ├── providers/     (base, registry, router, 3 providers, tool_calling, rate_limiter, token_counter)
    ├── integrations/  (mcp_client, tool_executor, rest_adapter, webhook_handler, oauth_manager, adapter_registry)
    ├── cache/         (semantic, mcp_cache, key_schema)
    ├── versioning/    (manager, snapshot, diff, pinning)
    ├── privacy/       (detector, masker, gdpr)
    ├── events/        (bus, handlers, audit)
    ├── health/                   ← NEW MODULE
    │   ├── __init__.py
    │   ├── checker.py            (HealthChecker — probe all dependencies)
    │   ├── models.py             (HealthStatus, DependencyStatus, HealthReport)
    │   └── reporter.py           (aggregate and format health report)
    ├── scheduler/                ← NEW MODULE
    │   ├── __init__.py
    │   ├── cron_evaluator.py     (CronEvaluator — parse + compute next fire)
    │   ├── trigger_finder.py     (TriggerFinder — query MongoDB for due triggers)
    │   └── dispatcher.py        (SchedulerDispatcher — create run + fire task)
    └── billing/                  ← NEW MODULE
        ├── __init__.py
        ├── usage_tracker.py      (UsageTracker — record token costs)
        ├── quota_checker.py      (QuotaChecker — pre-execution quota gate)
        ├── cost_calculator.py    (CostCalculator — token × model price)
        └── report.py             (BillingReport — monthly tenant summary)
```

---

### 7.2 workflow-api

```
packages/workflow-api/
├── pyproject.toml                    # depends on workflow-engine==<version>
├── Dockerfile
├── .env.example
└── src/workflow_api/
    ├── main.py                       # FastAPI app + lifespan + exception handler
    ├── dependencies.py               # FastAPI DI providers for all SDK objects
    ├── config.py                     # APIConfig (extends EngineConfig with API-specific settings)
    ├── routes/
    │   ├── __init__.py
    │   ├── workflows.py              # CRUD + duplicate
    │   ├── executions.py             # trigger + status + cancel + retry + nodes
    │   ├── versions.py               # list + get + diff + rollback
    │   ├── nodes.py                  # list types + get type + schema + validate-config
    │   ├── webhooks.py               # inbound webhook receiver
    │   ├── health.py                 # /health + /readyz + /livez
    │   └── admin.py                  # tenant management + GDPR (internal)
    ├── websocket/
    │   ├── hub.py                    # WebSocketHub — Redis → WS fan-out
    │   └── events.py                 # Typed WS event Pydantic schemas
    ├── auth/
    │   ├── jwt.py                    # JWTValidator
    │   ├── api_key.py                # APIKeyValidator
    │   ├── oauth.py                  # OAuthFlow for third-party integrations
    │   └── permissions.py            # PermissionChecker dependency
    ├── middleware/
    │   ├── tenant.py                 # TenantContextMiddleware
    │   ├── rate_limit.py             # APIRateLimitMiddleware
    │   ├── semaphore.py              # TenantSemaphore
    │   ├── cors.py                   # CORS configuration
    │   ├── logging.py                # StructuredLoggingMiddleware
    │   └── tracing.py                # OTelTracingMiddleware
    └── tests/
        ├── conftest.py               # TestClient fixtures, mock SDK objects
        ├── test_routes/
        │   ├── test_workflows.py
        │   ├── test_executions.py
        │   ├── test_versions.py
        │   ├── test_nodes.py
        │   ├── test_webhooks.py
        │   └── test_health.py
        ├── test_auth/
        │   ├── test_jwt.py
        │   └── test_api_key.py
        ├── test_middleware/
        │   ├── test_rate_limit.py
        │   └── test_semaphore.py
        ├── test_websocket/
        │   └── test_hub.py
        └── test_integration/
            └── test_full_flow.py     # API → Celery → Redis → WS — end-to-end
```

---

### 7.3 workflow-worker

```
packages/workflow-worker/
├── pyproject.toml                    # depends on workflow-engine==<version>
├── Dockerfile
├── .env.example
└── src/workflow_worker/
    ├── celery_app.py                 # Celery instance + config + beat schedule
    ├── config.py                     # WorkerConfig (extends EngineConfig)
    ├── tasks/
    │   ├── __init__.py
    │   ├── orchestrator.py           # orchestrate_run — main workflow task
    │   ├── node_runner.py            # execute_single_node — for parallel branches
    │   ├── cleanup.py                # cleanup_run — post-run resource release
    │   ├── scheduler.py              # scheduler_fire_cron — Celery beat task
    │   └── human_callback.py         # handle_human_callback — resume HumanNode
    ├── signals.py                    # task_failure, task_revoked, worker_shutdown handlers
    ├── context_builder.py            # SDK object factory — builds all SDK objects from config
    └── tests/
        ├── conftest.py               # always_eager=True fixtures, testcontainers
        ├── test_tasks/
        │   ├── test_orchestrator.py  # Full run via always_eager mode
        │   ├── test_node_runner.py
        │   ├── test_cleanup.py
        │   ├── test_scheduler.py
        │   └── test_human_callback.py
        ├── test_signals.py
        └── test_integration/
            └── test_parallel_execution.py  # group/chord with real Redis broker
```

---

### 7.4 workflow-cli

```
packages/workflow-cli/
├── pyproject.toml                    # depends on workflow-engine==<version>; entry_points cli=workflow_cli.main:cli
└── src/workflow_cli/
    ├── main.py                       # Click group entry point + global options
    ├── api_client.py                 # httpx wrapper for all API calls
    ├── config.py                     # CLIConfig — ~/.workflow/config.toml loader
    ├── output.py                     # Rich output helpers: tables, progress bars, status icons
    ├── commands/
    │   ├── __init__.py
    │   ├── validate.py               # wf validate — SDK direct
    │   ├── deploy.py                 # wf deploy — SDK validate + API PUT
    │   ├── run.py                    # wf run — API POST
    │   ├── logs.py                   # wf logs — WebSocket stream
    │   ├── executions.py             # wf executions list/get/cancel
    │   ├── versions.py               # wf versions list/get/diff/rollback
    │   ├── nodes.py                  # wf nodes list/schema
    │   ├── config_cmd.py             # wf config set/get/list-profiles
    │   └── init.py                   # wf init — scaffold workflow YAML
    └── tests/
        ├── conftest.py               # CliRunner fixtures, mock API client
        ├── test_commands/
        │   ├── test_validate.py      # Local SDK calls only
        │   ├── test_deploy.py        # Mock API + SDK
        │   ├── test_run.py           # Mock API
        │   ├── test_logs.py          # Mock WebSocket
        │   ├── test_versions.py
        │   └── test_executions.py
        ├── test_api_client.py        # Mock httpx responses
        └── test_output.py            # Rich output formatting
```

---

## 8. Development Phases

### Phase 1 — Core Foundation & SDK Alignment (Weeks 1–4)

**Goal:** SDK gaps filled. All 3 component scaffolds ready. CI pipeline green.

**Deliverables:**
- `engine.health` module implemented and tested
- `engine.scheduler` module implemented and tested
- `engine.billing` module implemented and tested
- `engine.models.responses` and `engine.models.requests` added
- `engine.context.trace` added
- `engine.models.errors` updated with new error types and `http_status_code`
- `engine.versioning` updated with `get_version()` and `get_latest()`
- All 3 consumer packages scaffolded with `pyproject.toml`, `Dockerfile`, CI jobs
- Shared `context_builder.py` in worker (SDK object factory)
- `api_client.py` in CLI fully implemented and tested

---

### Phase 2 — API + Worker Integration (Weeks 5–8)

**Goal:** API fully operational. Worker processes real workflows end-to-end.

**Deliverables:**
- All API routes implemented and tested (workflows, executions, versions, nodes, webhooks, health, admin)
- Auth middleware (JWT + API key) fully functional
- Rate limiting and tenant semaphore middleware tested
- WebSocket hub broadcasting execution events from Redis pub/sub
- All 5 Celery task types implemented (orchestrator, node_runner, cleanup, scheduler, human_callback)
- Signal handlers for failure and revocation
- Parallel execution via Celery group/chord working end-to-end
- OTel trace propagation from API through worker verified in staging

---

### Phase 3 — CLI Integration (Weeks 9–10)

**Goal:** CLI fully operational. Developer experience complete.

**Deliverables:**
- All CLI commands implemented with Rich output
- `wf validate` working offline with SDK
- `wf deploy` doing local-first validation before API call
- `wf logs` streaming real-time WebSocket events
- `wf versions diff` using SDK directly (no API)
- Config file management working across profiles
- `wf init` template scaffolding
- CI/CD usage: all commands return proper exit codes

---

### Phase 4 — Advanced Orchestration Features (Weeks 11–12)

**Goal:** Enterprise features operational — billing, GDPR, human nodes, scheduler.

**Deliverables:**
- Cron scheduler working via Celery beat (`scheduler_fire_cron`)
- Human node pause/resume via `handle_human_callback` task
- Billing quota enforcement at API trigger time via `QuotaChecker`
- Monthly billing report endpoint in API admin routes
- GDPR deletion endpoint functional across all stores
- Multi-provider fallback tested under rate limit conditions

---

### Phase 5 — Testing, Monitoring & Production Readiness (Weeks 13–16)

**Goal:** Full-stack tested. Production hardened. Runbooks complete.

**Deliverables:**
- Contract tests (Pact) for API ↔ CLI interaction
- Load test: 1000 concurrent workflow executions via Locust
- Security scan: OWASP ZAP on API, Snyk on all packages
- Kubernetes manifests: Deployments, Services, HPA configs for all 3 services
- Terraform IaC for GKE, CloudSQL, Memorystore, GCS
- Grafana dashboards: API latency p50/p99, worker queue depth, token costs, cache hit rate
- Runbooks: worker pod killed mid-run, Redis failover, provider outage, DB failover
- `CHANGELOG.md` and API documentation (`/docs` OpenAPI)

---

> **AI Workflow Builder — Unified Development Roadmap**
> workflow-api (FastAPI) · workflow-worker (Celery) · workflow-cli (Click)
> All components are thin consumers of `workflow-engine` (SDK)
> 3 new SDK modules · 3 updated SDK modules · 5 development phases
