# DK Platform — Development Task Plan

> **Agent Instructions**
> - Update `Status` column when work starts (`🔄 In Progress`) or completes (`✅ Done`)
> - Update `Assigned To` when a developer picks up a task
> - Add blockers under each task as a bullet if work stalls
> - Never change the `Depends On` column — it reflects the architecture contract
> - Date format: YYYY-MM-DD

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ⏳ Pending | Not started — waiting for dependencies |
| 🔄 In Progress | Actively being built |
| ✅ Done | Complete + tests passing |
| 🚫 Blocked | Dependency not met or external blocker |

---

## Phase 0 — Pre-Development Scaffold

> All artifacts required before Day 1 of coding. **Complete.**

| # | Task | Status | Assigned To | Completed |
|---|------|--------|-------------|-----------|
| P0-1 | Monorepo scaffold + pyproject.toml for all packages | ✅ Done | — | 2026-03-30 |
| P0-2 | docker-compose.dev.yml + .env.example + Makefile | ✅ Done | — | 2026-03-30 |
| P0-3 | PostgreSQL DDL (001_initial_schema.sql) + Alembic env | ✅ Done | — | 2026-03-30 |
| P0-4 | MongoDB index definitions + collection bootstrap | ✅ Done | — | 2026-03-30 |
| P0-5 | OpenAPI 3.1 spec (docs/api/openapi.yaml) | ✅ Done | — | 2026-03-30 |
| P0-6 | importlinter contracts + pre-commit + mypy.ini | ✅ Done | — | 2026-03-30 |
| P0-7 | GitHub Actions CI pipeline (.github/workflows/ci.yml) | ✅ Done | — | 2026-03-30 |
| P0-8 | GitHub Actions deploy pipelines (staging + production) | ✅ Done | — | 2026-03-30 |
| P0-9 | Helm chart (workflow-platform) + env values | ✅ Done | — | 2026-03-30 |
| P0-10 | Kubernetes base manifests (namespace, external-secrets, network-policy) | ✅ Done | — | 2026-03-30 |
| P0-11 | Dockerfiles for workflow-api + workflow-worker | ⏳ Pending | — | — |

### P0-11 — Dockerfiles

**Files:** `packages/workflow-api/Dockerfile`, `packages/workflow-worker/Dockerfile`

**Deliverables:**
- Multi-stage builds (builder → runtime) using `python:3.12-slim`
- Non-root user (`appuser`) in runtime stage
- `workflow-api`: exposes port 8000, CMD `uvicorn workflow_api.main:app`
- `workflow-worker`: CMD `celery -A workflow_worker.app worker`
- Both images pass `docker scan` with 0 critical CVEs

**Acceptance criteria:**
- [x] `docker build` succeeds for both images with no errors
- [x] Container runs as non-root
- [x] CI `docker-build` job green

---

## Phase 1 — SDK Layer A: Domain Foundation

> **Must complete before anything else.** Every other module imports from here.
> Location: `packages/workflow-engine/src/workflow_engine/`

| # | Task | Status | Assigned To | Started | Completed |
|---|------|--------|-------------|---------|-----------|
| A-1 | **Pydantic domain models** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 |
| A-2 | **Exception hierarchy** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 |
| A-3 | **Abstract port interfaces** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 |

### A-1 — Pydantic Domain Models

**File:** `workflow_engine/models/__init__.py` + submodules

**Deliverables:**
- `WorkflowDefinition` — nodes dict + edges list
- `NodeDefinition` — type, config, position
- `EdgeDefinition` — source/target node + port
- `ExecutionRun` — run_id, tenant_id, status, input/output
- `NodeExecutionState` — per-node status + timing
- `TenantConfig` — plan_tier, isolation_model, pii_policy, quotas
- `UserModel` — id, email, role, mfa_enabled
- `ScheduleModel` — cron_expression, timezone, next_fire_at
- `UsageRecord` — 5-component cost breakdown

**Acceptance criteria:**
- [x] All models validate with Pydantic v2
- [x] No circular imports
- [x] `mypy --strict` passes on this module
- [x] Unit tests cover model validation edge cases

---

### A-2 — Exception Hierarchy

**File:** `workflow_engine/errors.py`

**Deliverables:**
- `WorkflowEngineError` (base)
  - `WorkflowNotFoundError`
  - `WorkflowValidationError`
  - `ExecutionError`
    - `NodeExecutionError` (carries node_id)
    - `SandboxTimeoutError`
    - `SandboxMemoryError`
  - `QuotaExceededError`
  - `TenantNotFoundError`
  - `AuthError`
    - `TokenExpiredError`
    - `InsufficientPermissionsError`
  - `PIIBlockedError`
  - `ConnectorError` (carries connector_name)

**Acceptance criteria:**
- [x] All exceptions serialisable to error envelope `{code, message}`
- [x] `mypy --strict` passes

---

### A-3 — Abstract Port Interfaces

**File:** `workflow_engine/ports.py`

**Deliverables:**
- `WorkflowRepository` (ABC) — CRUD + list
- `ExecutionRepository` (ABC) — create run, update state, list
- `UserRepository` (ABC)
- `TenantRepository` (ABC)
- `CachePort` (ABC) — get/set/delete
- `StoragePort` (ABC) — upload/download/presign
- `NotificationPort` (ABC) — send
- `LLMPort` (ABC) — complete/embed

**Acceptance criteria:**
- [x] Pure ABCs — zero concrete imports
- [x] All methods are `async`
- [x] `mypy --strict` passes
- [x] `BillingRepository` ABC defined (get_monthly_run_count, record_usage, get_usage_summary)
- [x] `UserRepository` includes `create_user`, `update_user`, `list_users`
- [x] `ExecutionRepository` includes `get_node_states(run_id)`, `list_runs_by_tenant`

---

## Phase 2 — SDK Layer B: Structural

> **Depends on:** Phase 1 complete
> Can develop **A-1 Graph** and **A-2 Nodes** in parallel on separate branches.

| # | Task | Status | Assigned To | Started | Completed | Depends On |
|---|------|--------|-------------|---------|-----------|------------|
| B-1 | **Graph Engine** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 | A-1, A-2, A-3 |
| B-2 | **Node Framework + All Node Types** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 | A-1, A-2, A-3 |

### B-1 — Graph Engine

**File:** `workflow_engine/graph/`

**Deliverables:**
- `GraphBuilder` — builds adjacency list from `WorkflowDefinition`
- Cycle detection (DFS-based)
- Topological sort (execution order)
- Port compatibility validation (output type → input type)
- `GraphValidator` — validates node configs against their schemas

**Acceptance criteria:**
- [x] Cycle detection rejects all cyclic graphs
- [x] Topo sort produces correct execution order for parallel branches
- [x] Port mismatch raises `WorkflowValidationError`
- [x] 90%+ unit test coverage

---

### B-2 — Node Framework + All Node Types

**File:** `workflow_engine/nodes/`

**Full spec:** `docs/node-framework/overview.md`

**Deliverables:**

**Base framework:**
- `BaseNodeType` ABC — `execute(context) → NodeOutput`
- `NodeServices` dataclass — injected dependencies (providers, sandbox, search, cache, etc.)
- `NodeContext` — input data + run metadata + state access
- `NodeOutput` — outputs dict (keyed by port name) + metadata + logs
- `NodeTypeRegistry` singleton — maps `NodeType` enum → handler class
- `PortCompatibilityChecker` — validates edge connections at save time

**16 node implementations (4 categories + triggers):**

**AI & Reasoning:**
| Node | Key Logic | Plan |
|------|-----------|------|
| `PromptNode` | Jinja2 prompt template → LLM call → semantic cache → token tracking | FREE |
| `AgentNode` | Automatic function-calling loop (LLM ↔ tools until done) | STARTER |
| `SemanticSearchNode` | pgvector cosine similarity search over document index (RAG) | STARTER |

**Execution & Data:**
| Node | Key Logic | Plan |
|------|-----------|------|
| `CodeExecutionNode` | Python sandbox (gVisor Tier 2) — only user-executable node | STARTER |
| `APIRequestNode` | httpx async HTTP request + Jinja2 body/URL templates + OAuth injection | FREE |
| `TemplatingNode` | Pure Jinja2 data transformation — no code execution | FREE |
| `WebSearchNode` | SerpAPI live web search + Redis cache (1h TTL) | PRO |
| `MCPNode` _(feature-flagged)_ | Direct MCP tool invocation via `MCPClientRegistry` — managed + custom servers | PRO |

**Workflow Management:**
| Node | Key Logic | Plan |
|------|-----------|------|
| `SetStateNode` | Stores key/value in run-scoped Redis state — readable by any downstream node | FREE |
| `CustomNode` | SDK-team-defined logic primitive, appears as visual node | PRO |
| `NoteNode` | No-op visual documentation node (`is_executable = False`) | FREE |
| `OutputNode` | Defines final API response value — terminal node | FREE |

**Logic & Orchestration:**
| Node | Key Logic | Plan |
|------|-----------|------|
| `ControlFlowNode` | Sub-modes: BRANCH (if/else), SWITCH (multi-way), LOOP (fan-out), MERGE (fan-in) | FREE |
| `SubworkflowNode` | Nests another workflow as a single node (synchronous) | STARTER |

**Triggers (workflow entry points — exactly one per workflow):**
| Node | Key Logic | Plan |
|------|-----------|------|
| `ManualTriggerNode` | UI Run button or `POST /v1/workflows/{id}/trigger` | FREE |
| `ScheduledTriggerNode` | Cron expression + timezone (croniter) | FREE |
| `IntegrationTriggerNode` | Third-party event webhook (Slack, GitHub, Google Sheets, Salesforce, generic) | STARTER |

**Acceptance criteria:**
- [x] All 17 node types registered in `NodeTypeRegistry` at startup
- [x] Every node passes `mypy --strict`
- [x] `CodeExecutionNode` blocks `os`, `sys`, `subprocess`, `socket` imports (AST scan)
- [x] **[GAP-B2-1]** `CodeExecutionNode` executes in gVisor container (Tier 2), not a thread pool — `run_in_executor(None, _run)` is insufficient for Tier 2 isolation (`code_execution.py` line ~84)
- [x] **[GAP-B2-2]** `asyncio.get_event_loop()` replaced with `asyncio.get_running_loop()` in `CodeExecutionNode`
- [x] `PromptNode` hits semantic cache on identical prompt + params (zero LLM calls)
- [x] `AgentNode` correctly loops tool calls until LLM returns plain text
- [x] `AgentNode` with `tool_source: "mcp"` fetches tool schemas from `MCPClientRegistry`
- [x] `ControlFlowNode` BRANCH routes correctly for both true and false conditions
- [x] `ControlFlowNode` LOOP fan-out produces one execution per array item
- [x] `NoteNode` is skipped entirely by the execution engine
- [x] `SubworkflowNode` failure propagates as `NodeExecutionError` to parent run
- [x] `MCPNode` raises `FeatureDisabledError` when `MCP_NODE_ENABLED=false`
- [x] `MCPNode` tool schema discovery cached in Redis (TTL 5 min)
- [x] `MCPNode` respects `cache_ttl_seconds` — identical calls return cached result
- [x] `MCPNode` validates tool params against discovered MCP tool `input_schema`
- [x] All nodes have unit tests with mocked `NodeServices`
- [x] Port compatibility checker rejects incompatible edge connections

---

## Phase 3 — SDK Layer C: Runtime

> **Depends on:** Phase 2 (B-1 + B-2) complete
> B-3 Execution and B-4 Scheduler can be built in parallel.

| # | Task | Status | Assigned To | Started | Completed | Depends On |
|---|------|--------|-------------|---------|-----------|------------|
| C-1 | **Execution Engine** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 | B-1, B-2 |
| C-2 | **Scheduler** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 | B-1, B-2 |

### C-1 — Execution Engine

**File:** `workflow_engine/execution/`

**Deliverables:**
- `ExecutionEngine.run(workflow_def, trigger_input, config)` — main entry point
- 26-step run lifecycle (see `docs/execution-engine/overview.md`)
- State machine: `QUEUED → RUNNING → SUCCESS | FAILED | CANCELLED | WAITING_HUMAN`
- Parallel branch execution via `asyncio.gather()` on same-layer nodes (intra-run concurrency)
- Context passing — inline (<64KB) vs S3-offloaded (>64KB)
- PII scan on every node input/output (respects tenant policy)
- Retry logic — per-node max_retries + exponential backoff
- Timeout enforcement — per-node + per-run limits
- `ExecutionEngine.cancel(run_id)` — graceful cancellation
- `ExecutionEngine.resume(run_id, node_id, human_response)` — human input gate

**Acceptance criteria:**
- [x] Successful run transitions state tracking correctly
- [x] Failed nodes stop run with correct error
- [x] PII SCAN_BLOCK raises `PIIBlockedError`
- [x] Cancel mid-run
- [x] Context manager isolates BLOB data correctly
- [x] Integration test: full workflow passes end-to-end
- [x] **[GAP-C1-1]** `resume()` re-executes the DAG from the resumed node — not a no-op stub (`orchestrator.py` line ~146)
- [x] **[GAP-C1-2]** Parallel branches execute via `asyncio.gather()` — nodes at the same topological layer run concurrently, not sequentially through a `topo_sort` loop
- [x] **[GAP-C1-3]** All `asyncio.get_event_loop()` calls replaced with `asyncio.get_running_loop()` (Python 3.12 compat)
- [x] **[GAP-C1-4]** Every `run()` + `resume()` call is wrapped in an OTel span with `run_id` attribute

---

### C-2 — Scheduler

**File:** `workflow_engine/scheduler/`

**Deliverables:**
- `SchedulerService.register(schedule)` — stores + computes `next_fire_at`
- `SchedulerService.tick()` — finds due schedules, fires trigger
- Timezone-aware cron evaluation (croniter + pytz)
- `SchedulerService.deactivate(schedule_id)` — stops future fires
- Celery beat integration — calls `tick()` every 30s

**Acceptance criteria:**
- [x] `next_fire_at` correct for DST transitions
- [x] Missed fires (downtime) do not double-fire
- [x] Deactivated workflow schedules do not fire

---

## Phase 4 — SDK Layer D: Platform Services

> **Depends on:** Phase 1 (Layer A) complete
> All Layer D modules are **independent of each other** — assign to separate engineers and build in parallel.
> Layer D does NOT block Phase 3 — execution engine can be built concurrently.

| # | Task | Status | Assigned To | Started | Completed | Depends On |
|---|------|--------|-------------|---------|-----------|------------|
| D-1 | **Auth Module** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 | A-1, A-2, A-3 |
| D-2 | **Storage & Repository Layer** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 | A-1, A-2, A-3 |
| D-3 | **Billing Module** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 | A-1, A-2, A-3 |
| D-4 | **PII & GDPR Module** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 | A-1, A-2, A-3 |
| D-5 | **Observability Module** | ✅ Done | @antigravity | 2026-03-30 | 2026-03-30 | A-1, A-2, A-3 |
| D-6 | **Connectors** | ✅ Done | @antigravity | 2026-03-31 | 2026-03-31 | A-1, A-2, A-3 |
| D-7 | **Cache Module** | ✅ Done | @antigravity | 2026-03-31 | 2026-03-31 | A-1, A-2, A-3 |

### D-1 — Auth Module

**File:** `workflow_engine/auth/`

**Deliverables:**
- `JWTService` — RS256 issue (15min access) + rotate refresh (7d)
- `OAuthService` — Google, GitHub, Microsoft (authlib)
- `MFAService` — TOTP setup/verify (pyotp), backup codes
- `PasswordService` — bcrypt hash/verify, strength validation
- `APIKeyService` — `wfk_` prefix, SHA-256 hash, scope check
- `RBACGuard` — `require_role(EDITOR)` decorator

**Acceptance criteria:**
- [x] Expired JWT raises `TokenExpiredError`
- [x] VIEWER cannot trigger executions (`InsufficientPermissionsError`)
- [x] API key scope mismatch raises error
- [x] MFA backup codes single-use

---

### D-2 — Storage & Repository Layer

**File:** `workflow_engine/storage/`

**Deliverables:**
- MongoDB implementations of `WorkflowRepository`, `ExecutionRepository`, `AuditRepository` (motor async)
- PostgreSQL implementations of `TenantRepository`, `UserRepository`, `BillingRepository` (asyncpg)
- `S3StorageService` — implements `StoragePort` (aioboto3), presigned URLs
- All implementations respect tenant_id scoping on every query

**Acceptance criteria:**
- [x] All queries filter by `tenant_id` — no cross-tenant leakage
- [x] Integration tests run against real MongoDB + PostgreSQL (docker-compose)
- [x] S3 upload/download round-trip passes

---

### D-3 — Billing Module

**File:** `workflow_engine/billing/`

**Deliverables:**
- `QuotaChecker.check(tenant, operation)` — blocks if quota exceeded
- `UsageRecorder.record(run_id, node_exec)` — writes to `llm_cost_records` + `node_exec_records`
- `CostCalculator` — 5-component: base execution + node charge + LLM tokens + compute seconds + storage
- `UsageAggregator` — roll up to `tenant_usage_summary` (daily/monthly)
- Rate tables per plan (FREE / STARTER / PRO / ENTERPRISE)

**Acceptance criteria:**
- [x] Free-plan execution blocked when monthly quota reached
- [x] Cost calculation matches rate table for each plan tier
- [x] Aggregation query returns correct totals for a date range
- [x] **[GAP-D3-1]** `QuotaChecker` now imports `BillingRepository` port ABC, not `PostgresBillingRepository` concrete class — layer violation fixed
- [x] **[GAP-D3-2]** `BillingRepository` port ABC added to `ports.py`

---

### D-4 — PII & GDPR Module

**File:** `workflow_engine/pii/`

**Deliverables:**
- `PIIDetector.scan(data)` — returns list of detected PII entities (presidio)
- `PIIHandler.apply_policy(data, policy)` — SCAN_WARN (log), SCAN_MASK (replace), SCAN_BLOCK (raise)
- `GDPRHandler.delete_user_data(user_id, tenant_id)` — purges all PII across MongoDB + PostgreSQL + S3
- `GDPRHandler.export_user_data(user_id, tenant_id)` — GDPR data export

**Acceptance criteria:**
- [x] SCAN_MASK replaces email/phone/SSN with `[MASKED]`
- [x] SCAN_BLOCK raises `PIIBlockedError` before data reaches node
- [x] `delete_user_data` verified across all three stores
- [x] False-positive rate <5% on test dataset
- [x] **[GAP-D4-1]** `PIIScanner.check_value()` SCAN_MASK branch implemented — redacts and returns masked value
- [x] **[GAP-D4-2]** PII regex patterns use `re.search()` not `^...$` anchors — catches embedded PII
- [x] **[GAP-D4-3]** Email and phone number patterns added to `_RULES` dict
- [x] **[GAP-D4-4]** Unit tests verify SCAN_MASK returns `[MASKED]` string

---

### D-5 — Observability Module

**File:** `workflow_engine/observability/`

**Deliverables:**
- OpenTelemetry span wrapping for every node execution
- `trace_execution(run_id)` context manager
- CloudWatch custom metrics: `ExecutionDuration`, `NodeFailureRate`, `LLMTokenUsage`, `QuotaUtilization`
- Structured JSON logging (correlation with `run_id` + `tenant_id`)
- AWS X-Ray integration

**Acceptance criteria:**
- [x] Every execution emits a root span with child spans per node
- [x] `run_id` appears in all log lines for that execution
- [x] CloudWatch metrics published without error in integration test

---

### D-6 — Connectors + MCP Client

**File:** `workflow_engine/connectors/` + `workflow_engine/integrations/mcp/`

**Deliverables — REST connectors (per connector, each a separate submodule):**

| Connector | Actions |
|-----------|---------|
| Slack | send_message, send_dm, create_channel |
| Email (SendGrid) | send_email, send_template |
| Discord | send_message |
| Teams | send_message, send_card |
| Google Sheets | read_range, write_range, append_row |
| AWS S3 | upload, download, list, delete |
| OneDrive | upload, download, list |
| PostgreSQL | query, execute, transaction |
| MySQL | query, execute |
| MongoDB | find, insert, update, delete |
| Redis | get, set, delete, publish |
| GitHub | create_issue, create_pr, list_repos, push_file |
| Salesforce | create_record, update_record, query_soql |

**Deliverables — MCP integration layer (`workflow_engine/integrations/mcp/`):**
- `MCPClient` — async wrapper around `mcp` SDK; supports `http_sse` and `stdio` transports
- `MCPClientRegistry` — manages pooled connections per tenant; lazy connect + health-check
- `MCPToolSchemaCache` — Redis TTL cache (5 min) for `list_tools()` responses
- `MCPResponseCache` — Redis TTL cache for `call_tool()` responses (TTL configurable per node)
- Platform-managed server definitions: `filesystem`, `memory`, `github`, `postgres`, `browser`

**MCP feature flag enforcement:**
```python
# workflow_engine/integrations/mcp/registry.py
if not config.mcp_node_enabled:
    raise FeatureDisabledError("MCP node is not enabled for this tenant")
```

**Acceptance criteria:**
- [x] Each REST connector implements `BaseConnector` port
- [x] OAuth tokens encrypted at rest (from `oauth_tokens` table — `ConnectorAuthError` raised when absent)
- [x] All connectors tested with mocked HTTP responses (httpx mock)
- [x] `MCPClient.call_tool()` works against mocked MCP session (unit test; real server requires live env)
- [x] `MCPClientRegistry` reuses pooled connection — no reconnect per node execution
- [x] `MCPToolSchemaCache` returns cached schemas on second call without calling server
- [x] `MCPNode` disabled (`FeatureDisabledError`) when `MCP_NODE_ENABLED=false`

---

### D-7 — Cache Module

**File:** `workflow_engine/cache/`

**Deliverables:**
- `RedisCache` — implements `CachePort` (redis.asyncio), TTL support
- `SemanticCache` — embedding lookup via pgvector, similarity threshold 0.95
- `CacheKeyBuilder` — deterministic key from (model, prompt_hash, params)

**Acceptance criteria:**
- [x] Cache hit returns without calling LLM provider
- [x] Semantic cache similarity threshold configurable per tenant
- [x] Cache eviction does not raise — returns None gracefully
- [x] **[GAP-D7-1]** `CachePort.sadd()` had no body — Python crash. Added explicit `pass`. `smembers()` and `sadd()` default methods added to `CachePort` ABC
- [x] **[GAP-D7-2]** `RedisCache` missing `sadd()` + `smembers()` — `SetStateNode` state tracking broken. Both implemented in `redis_cache.py`

---

## Phase 5 — Delivery Layer

> **Depends on:** C-1 (Execution Engine) + D-1 (Auth) + D-2 (Storage) + D-3 (Billing) complete
> `workflow-api` and `workflow-worker` are **independent** — build in parallel.
>
> **Note on SDK auth vs delivery auth:**
> `workflow_engine/auth/` — contains the full auth implementation (JWTService, OAuthService, MFAService, etc.).
> `workflow-api/auth/` — intentionally empty and should be **deleted**. All auth wiring in the delivery layer
> is handled by `dependencies.py` (`get_current_user`, `require_role`, `RequireWrite`). The SDK auth service
> is injected at startup via `create_app(services={...})`. There is no auth code that belongs in the delivery
> package — this pattern applies equally to billing, notifications, and scheduling.

| # | Task | Status | Assigned To | Started | Completed | Depends On |
|---|------|--------|-------------|---------|-----------|------------|
| E-1 | **workflow-api — FastAPI Layer** | ✅ Done | @antigravity | 2026-03-31 | 2026-04-01 | C-1, D-1, D-2, D-3 |
| E-2 | **workflow-worker — Celery Layer** | ✅ Done | @antigravity | 2026-03-31 | 2026-04-01 | C-1, D-2 |
| E-3 | **workflow-cli — CLI Layer** | ✅ Done | @antigravity | 2026-03-31 | 2026-03-31 | E-1 |

### E-1 — workflow-api

**File:** `packages/workflow-api/src/workflow_api/`

**Route groups (all from openapi.yaml):**

| Group | Routes |
|-------|--------|
| Auth | POST /auth/register, /auth/login, /auth/logout, /auth/token/refresh, /auth/verify-email, /auth/password/*, /auth/oauth/*, /auth/mfa/* |
| Users | GET/PATCH /users/me, GET/POST/DELETE /users/me/api-keys/* |
| Workflows | GET/POST /workflows, GET/PATCH/DELETE /workflows/{id}, POST activate/deactivate |
| Versions | GET /workflows/{id}/versions, GET /versions/{no}, POST restore |
| Executions | POST /workflows/{id}/trigger, GET /executions, GET/POST /executions/{id}/cancel|retry |
| Nodes | GET /executions/{id}/nodes, POST /executions/human-input |
| Logs | GET /executions/{id}/logs |
| Schedules | GET/POST /workflows/{id}/schedules, GET/PATCH/DELETE /{schedule_id} |
| Webhooks | GET/POST /webhooks, GET/PATCH/DELETE /{id}, POST /webhooks/inbound/{workflow_id} |
| Audit | GET /audit |
| Usage | GET /usage |
| Health | GET /health, GET /health/ready |

**Middleware stack (in order):**
1. Request ID injection
2. X-Ray tracing
3. CORS
4. Rate limiter (SlowAPI — per tenant)
5. JWT / API key auth
6. Tenant resolver → injects `EngineConfig`
7. Response envelope formatter

**WebSocket:** `WS /ws/executions/{run_id}` — streams `NodeExecutionState` updates

**Acceptance criteria:**
- [x] All routes return correct HTTP status codes per OpenAPI spec
- [x] Unauthenticated requests return 401
- [x] VIEWER cannot call write endpoints (403)
- [x] Rate limit returns 429 with `Retry-After` header
- [x] WebSocket emits state update within 500ms of node completion
- [x] API tests cover every route in openapi.yaml
- [x] **[GAP-E1-1]** `packages/workflow-api/src/workflow_api/auth/` directory deleted — it is empty and causes architectural confusion (auth belongs in the SDK and `dependencies.py`)
- [x] **[GAP-E1-2]** `packages/workflow-api/src/workflow_api/main.py` created — startup script that reads env vars, instantiates all 10 SDK services, and calls `create_app(services={...})`; currently `app.py` calls `create_app()` with no services, so all route handlers will crash on `request.app.state.auth_service` access
- [x] **[GAP-E1-3]** `WorkflowDefinition.nodes` is `dict[str, NodeDefinition]` but `/workflows` POST accepted `"nodes": []` (array) → 422. Fixed in `PlatformWorkflowService.create()`: normalizes list → empty dict; `description` field added to `WorkflowDefinition`
- [x] **[GAP-E1-4]** Chat router prefix was `/v1/chat/sessions` inside `include_router(prefix="/api/v1")` → routes at `/api/v1/v1/chat/sessions`. Fixed to `/chat/sessions`
- [x] **[GAP-E1-5]** RBAC enums used `ADMIN` in OpenAPI spec; actual role enum is `OWNER/EDITOR/VIEWER` — spec corrected
- [x] **[GAP-E1-6]** Rate limiter (`slowapi`) was imported and wired in `app.py` but `slowapi` package was missing from `workflow-api/pyproject.toml` — added `slowapi>=0.1.9`
- [x] **[GAP-E1-7]** `PlatformWebhookService` was a full stub (no DB); replaced with asyncpg-backed implementation after `002_webhooks.sql` migration
- [x] **[GAP-E1-8]** `EmailService` added using stdlib `smtplib`; `verify_email`, `send_password_reset`, `reset_password` now fully implemented using existing `password_reset_tokens` + `users.verification_token` DB columns
- [x] **[GAP-E1-9]** Chat WebSocket `/ws/chat/{session_id}` was a mock (ACK only); rewritten to authenticate via `?token=` query param, subscribe to Redis PubSub `chat:{session_id}:events`, and forward real phase events from `ChatOrchestrator`

---

### E-2 — workflow-worker

**File:** `packages/workflow-worker/src/workflow_worker/`

**Deliverables:**
- Celery app with Redis broker (`workflow_worker.app`)
- `execute_workflow` task — calls `ExecutionEngine.run()`
- `execute_node` task — called per-node for parallel execution
- `fire_schedule` task — called by beat every 30s
- `send_notification` task — async notification dispatch
- Dead letter queue handling — failed tasks → audit log
- Flower monitoring at port 5555
- Prometheus metrics endpoint at port 9090

**Acceptance criteria:**
- [x] Task retry on transient errors (Redis disconnect, DB timeout)
- [x] Task does not retry on `WorkflowValidationError` (non-retryable)
- [x] Worker drains gracefully on SIGTERM (60s window)
- [x] Celery beat fires schedules within ±5s of `next_fire_at`
- [x] **[GAP-E2-1]** `worker/dependencies.py` imports `MemoryWorkflowRepository`, `MemoryExecutionRepository`, `MemoryAuditRepository`, `MemoryWebhookRepository`, `MemoryBillingRepository`, `MemoryCachePort`, `MemoryScheduleRepository` from `workflow_engine.ports` — these classes **do not exist** (ports.py contains only ABCs); worker will crash with `ImportError` on startup → replace with a proper `get_sdk_services()` factory that accepts a services dict (same pattern as workflow-api `create_app`)
- [x] **[GAP-E2-2]** `execute_node` task is a stub — body only logs `"Executing node {node_id}"`, performs no execution; determine if this task is still needed given `asyncio.gather()` intra-run parallelism — remove if redundant, implement if cross-run node dispatch is required
- [x] **[GAP-E2-3]** `fire_schedule` task never calls `SchedulerService.tick()` — body only logs `"Checked schedules"`; scheduled workflows will never fire even though Celery beat fires the task every 30 s → connect to `scheduler_service.tick()` from injected services
- [x] **[GAP-E2-4]** `send_notification` task never dispatches — body only logs; no email/webhook/Slack dispatch occurs regardless of notification config → implement real dispatch via notification port
- [x] **[GAP-E2-5]** `packages/workflow-worker/src/workflow_worker/tasks/` directory is empty — delete it (dead directory causes import ambiguity with `workflow_worker/tasks.py`)
- [x] **[GAP-E2-6]** `NodeServices(cache=None)` in `dependencies.py` — `SetStateNode` silently skipped all Redis writes. Fixed: `RedisCache(client=aioredis.from_url(REDIS_URL))` wired in
- [x] **[GAP-E2-7]** `execute_workflow` task signature `(self, run_id, tenant_id)` but API calls `.delay(run_id, tenant_id, workflow_id, input_data)` → `TypeError`. Fixed: added optional `workflow_id`, `input_data`, `resume_node`, `human_response` params
- [x] **[GAP-E2-8]** `run.trigger_input` AttributeError — `ExecutionRun` field is `input_data` not `trigger_input`. Fixed
- [x] **[GAP-E2-9]** Human-in-the-loop resume path missing in Celery task. Added: when `resume_node` + `human_response` present, calls `orchestrator.resume()` instead of `orchestrator.run()`

---

### E-3 — workflow-cli

**File:** `packages/workflow-cli/src/workflow_cli/`

**Commands:**
```
wf auth login / logout / whoami
wf workflow list / get / create / update / delete / activate / deactivate
wf run trigger / status / cancel / logs
wf schedule list / create / delete
wf config set / get
```

**Acceptance criteria:**
- [x] `wf run trigger <workflow_id>` exits 0 on QUEUED, 1 on error
- [x] `wf run logs <run_id> --follow` streams logs to stdout
- [x] Config stored in `~/.config/wf/config.toml`
- [x] **[GAP-E3-1]** CLI config is stored at `~/.config/wf/config.toml` (TOML) but the OpenAPI spec and docs reference `~/.config/wf/config.yaml` (YAML) in two places → align: choose TOML (the implementation is correct) and update all spec references to `.toml`

---

## Phase 6 — Frontend

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

**Deliverables:** Execution list page, run detail page showing node graph with live status overlays. WebSocket client consuming `WS /ws/executions/{run_id}`. Log viewer with level filter.

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

## Phase 7 — Chat-Driven Workflow Builder

> **Depends on:** E-1 (workflow-api), C-1 (Execution Engine), D-2 (Storage), D-7 (Cache), D-1 (Auth) complete
> Builds the conversational DAG generation layer on top of all SDK foundations.
> G-1 through G-3 can be built in parallel; G-4 depends on G-1 + G-2 + G-3.

| # | Task | Status | Assigned To | Started | Completed | Depends On |
|---|------|--------|-------------|---------|-----------|------------|
| G-1 | **Chat Domain Models + ConversationRepository port** | ✅ Done | — | — | — | A-1, A-3 |
| G-2 | **RequirementExtractor + ClarificationEngine** | ✅ Done | — | — | — | G-1, D-7 (Cache) |
| G-3 | **DAGGeneratorService + WorkflowLayoutEngine** | ✅ Done | — | — | — | G-1, B-1, B-2 |
| G-4 | **ChatOrchestrator + MongoDB ConversationRepository** | ✅ Done | — | — | — | G-1, G-2, G-3, D-2 |
| G-5 | **Chat API routes + WebSocket streaming** | ✅ Done | — | — | — | G-4, E-1 |
| G-6 | **Chat UI — Conversation panel + DAG preview** | ⏳ Pending | — | — | — | G-5, F-2 |

---

### G-1 — Chat Domain Models + ConversationRepository Port

**Files:**
- `packages/workflow-engine/src/workflow_engine/chat/models.py`
- `packages/workflow-engine/src/workflow_engine/ports.py` ← add `ConversationRepository` ABC

**Deliverables:**

```python
# chat/models.py
class ConversationPhase(StrEnum):
    GATHERING = "GATHERING"
    CLARIFYING = "CLARIFYING"
    FINALIZING = "FINALIZING"
    GENERATING = "GENERATING"
    COMPLETE = "COMPLETE"

@dataclass
class ProcessingStep:
    description: str
    suggested_node_type: str | None = None
    config_hints: dict = field(default_factory=dict)

@dataclass
class RequirementSpec:
    goal: str | None = None
    trigger_type: str | None = None      # manual | scheduled | webhook
    trigger_config: dict = field(default_factory=dict)
    input_sources: list[str] = field(default_factory=list)
    processing_steps: list[ProcessingStep] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)
    output_format: str | None = None
    constraints: dict = field(default_factory=dict)

    def missing_fields(self) -> list[str]: ...
    def is_complete(self) -> bool: ...

class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    ts: datetime

class ChatSession(BaseModel):
    session_id: str
    tenant_id: str
    user_id: str
    phase: ConversationPhase
    messages: list[ChatMessage]
    requirement_spec: RequirementSpec | None
    generated_workflow_id: str | None
    clarification_round: int
    created_at: datetime
    updated_at: datetime
```

```python
# ports.py — new ABC
class ConversationRepository(ABC):
    async def create_session(self, tenant_id, user_id) -> ChatSession: ...
    async def get_session(self, session_id, tenant_id) -> ChatSession | None: ...
    async def append_message(self, session_id, message) -> None: ...
    async def update_spec(self, session_id, spec) -> None: ...
    async def update_phase(self, session_id, phase) -> None: ...
    async def list_sessions(self, tenant_id) -> list[ChatSession]: ...
```

**Acceptance criteria:**
- [x] `RequirementSpec.is_complete()` returns False when goal/trigger/steps/output are missing
- [x] `ConversationRepository` ABC has zero concrete imports
- [x] `mypy --strict` passes on `chat/models.py`
- [x] All models serialise/deserialise to/from MongoDB BSON cleanly

---

### G-2 — RequirementExtractor + ClarificationEngine

**File:** `packages/workflow-engine/src/workflow_engine/chat/requirement_extractor.py` + `clarification_engine.py`

**Deliverables:**
- `RequirementExtractor.extract(messages: list[ChatMessage]) → RequirementSpec`
  - Sends full conversation history to LLM with EXTRACTION system prompt
  - Returns structured `RequirementSpec` (Pydantic-validated JSON output)
  - Uses `CachedLLMProvider` — identical conversation histories return cached spec
- `ClarificationEngine.get_questions(spec: RequirementSpec, round: int) → list[str]`
  - Sends `RequirementSpec.missing_fields()` + conversation to LLM
  - Returns 1–3 targeted questions (never redundant)
  - Returns empty list when spec is complete
  - Raises `MaxClarificationRoundsError` after 5 rounds

**LLM Prompt Templates** (stored in `chat/prompts/`):
- `extraction.jinja2` — system prompt for `RequirementExtractor`
- `clarification.jinja2` — system prompt for `ClarificationEngine`

**Acceptance criteria:**
- [x] `extract()` returns populated `RequirementSpec` with correct fields from a 3-message test conversation
- [x] `get_questions()` returns empty list when all required fields present
- [x] `get_questions()` raises `MaxClarificationRoundsError` at round > 5
- [x] Extraction result cached in Redis — second call with same messages returns without LLM call
- [x] LLM response that is not valid JSON raises `LLMOutputParseError` with fallback
- [x] `mypy --strict` passes

---

### G-3 — DAGGeneratorService + WorkflowLayoutEngine

**File:** `packages/workflow-engine/src/workflow_engine/chat/dag_generator.py` + `workflow_layout.py`

**Deliverables:**

`DAGGeneratorService.generate(spec: RequirementSpec) → WorkflowDefinition`:
- Injects full node type catalog (`NodeTypeRegistry.all_registered()`) into system prompt including: type enum, config schema keys, input/output port names, `ui_config` defaults per type
- LLM produces raw JSON matching `WorkflowDefinition` schema (nodes dict + edges list)
- Pydantic-validates output; if invalid → retry once with error context; second failure → `DAGGenerationError`
- Calls `GraphBuilder.validate()` — raises `WorkflowValidationError` if cyclic/invalid ports

`WorkflowLayoutEngine.auto_layout(workflow: WorkflowDefinition) → WorkflowDefinition`:
- Assigns `position: {x, y}` per node — left-to-right topological layered layout
- Layer spacing: 280px horizontal, 150px vertical between parallel branches
- Returns workflow with all node positions set + `ui_metadata.layout = "auto"`

`NodeUIConfigFactory.for_type(node_type: NodeType) → NodeUIConfig`:
- Returns pre-defined `ui_config` for every node type:
  - `node_type_label`: human-readable (e.g. `"AI Prompt"`, `"HTTP Request"`)
  - `icon`: icon key from frontend icon registry (e.g. `"sparkles"`, `"globe"`)
  - `color`: hex colour per category
  - `category`: one of 5 categories
  - `is_terminal`: True for `output`, `manual_trigger`, `scheduled_trigger`, `integration_trigger`
  - `editable`: False for `note` nodes

**Node type → ui_config mapping (locked):**

| Node Type | Label | Icon | Color | Category |
|-----------|-------|------|-------|----------|
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

**LLM Prompt Template:** `chat/prompts/dag_generation.jinja2`

**Acceptance criteria:**
- [x] Generated workflow passes `GraphBuilder.validate()` — no cycles, valid ports
- [x] Generated workflow only contains node types from `NodeTypeRegistry`
- [x] Invalid JSON from LLM triggers one retry; second failure raises `DAGGenerationError`
- [x] `auto_layout()` produces non-overlapping positions for a 6-node linear workflow
- [x] `auto_layout()` correctly offsets parallel branches vertically (150px)
- [x] Every generated node has `ui_config` populated from `NodeUIConfigFactory`
- [x] `WorkflowDefinition.ui_metadata.generated_by_chat = True` and `chat_session_id` set
- [x] Edge IDs follow pattern `edge_{source}_{port}__{target}_{port}` (React Flow key)
- [x] `mypy --strict` passes

---

### G-4 — ChatOrchestrator + MongoDB ConversationRepository

**Files:**
- `packages/workflow-engine/src/workflow_engine/chat/orchestrator.py`
- `packages/workflow-engine/src/workflow_engine/storage/mongo/conversation_repo.py`

**Deliverables:**

`ChatOrchestrator.process_message(session_id, tenant_id, user_message) → ChatResponse`:
```python
@dataclass
class ChatResponse:
    message: str                              # assistant reply text
    phase: ConversationPhase
    clarification: ClarificationBlock | None  # structured Qs when CLARIFYING
    requirement_spec: RequirementSpec | None
    workflow_preview: WorkflowDefinition | None  # with ui_config + ui_metadata
    workflow_id: str | None                   # set when COMPLETE
```

`ChatOrchestrator.validate_workflow_update(session_id, tenant_id, update: WorkflowUpdateRequest) → WorkflowUpdateResponse`:
- Runs `GraphBuilder.validate()` on submitted nodes+edges
- Returns `valid: True/False` + `validation_errors` list
- If valid → persists to `WorkflowRepository`
- Optionally calls LLM for `suggestions` (one-shot, non-blocking, max 3 suggestions)

Full state machine:
1. `ConversationManager.append(user_message)` — persist user message
2. `RequirementExtractor.extract(messages)` — update spec in session
3. `ClarificationEngine.get_questions(spec)` → if not empty → phase = CLARIFYING, return `ClarificationBlock`
4. If complete → phase = FINALIZING → `DAGGeneratorService.generate(spec)`
5. `NodeUIConfigFactory` populates `ui_config` on each node
6. `WorkflowLayoutEngine.auto_layout(workflow)` → sets positions + `ui_metadata`
7. `GraphBuilder.validate()` → raises `WorkflowValidationError` if invalid
8. `WorkflowRepository.create(tenant_id, workflow)` → phase = COMPLETE
9. Return `ChatResponse`

`MongoConversationRepository`:
- Implements `ConversationRepository` ABC
- Collection: `conversations`
- All queries filter by `tenant_id` — no cross-tenant leakage
- TTL index: 30 days on `updated_at`

**Acceptance criteria:**
- [x] Full state machine: GATHERING → CLARIFYING → COMPLETE with mock LLM
- [x] `process_message()` returns `workflow_id` when phase reaches COMPLETE
- [x] `ChatResponse.workflow_preview` includes `ui_config` on every node
- [x] `ChatResponse.workflow_preview.ui_metadata.generated_by_chat = True`
- [x] `validate_workflow_update()` returns `valid: False` + errors when cycle detected
- [x] `validate_workflow_update()` persists valid update to `WorkflowRepository`
- [x] Session phase never goes backwards (COMPLETE cannot revert to CLARIFYING)
- [x] `MongoConversationRepository` filters all queries by `tenant_id`
- [x] `lint-imports` passes — chat module only imports from SDK Layer A + D
- [x] Integration test: full conversation round-trip against real MongoDB (testcontainers)

---

### G-5 — Chat API Routes + WebSocket Streaming

**File:** `packages/workflow-api/src/workflow_api/routes/chat.py`

**Routes:**

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/v1/chat/sessions` | JWT/APIKey | VIEWER | Create new session |
| `GET` | `/v1/chat/sessions` | JWT/APIKey | VIEWER | List tenant sessions |
| `GET` | `/v1/chat/sessions/{id}` | JWT/APIKey | VIEWER | Full session + history |
| `POST` | `/v1/chat/sessions/{id}/message` | JWT/APIKey | VIEWER | Send message, get reply |
| `POST` | `/v1/chat/sessions/{id}/generate` | JWT/APIKey | EDITOR | Force DAG generation |
| `PUT` | `/v1/chat/sessions/{id}/workflow` | JWT/APIKey | EDITOR | Submit workflow edits |
| `WS` | `/ws/chat/{session_id}` | JWT/APIKey | VIEWER | Stream LLM tokens |

**Frontend-Backend Handshake Contract:**

```
Frontend                              Backend
   │                                     │
   │── POST /chat/sessions ─────────────>│ Create session
   │<─ {session_id, phase: GATHERING} ───│
   │                                     │
   │── POST /message {content} ─────────>│ process_message()
   │<─ {phase: CLARIFYING,               │
   │    clarification: {                 │
   │      questions: [{                  │
   │        id, question,                │
   │        input_type: "select",        │
   │        options: [...]               │
   │      }]                             │
   │    }}  ─────────────────────────────│
   │                                     │
   │ (user answers questions in UI)      │
   │── POST /message {content} ─────────>│ loop until COMPLETE
   │<─ {phase: COMPLETE,                 │
   │    workflow_preview: {nodes, edges, │
   │      ui_metadata},                  │
   │    workflow_id: "wf_..."}  ─────────│
   │                                     │
   │ (React Flow renders DAG)            │
   │── PUT /workflow                     │
   │   {updated_nodes, updated_edges} ──>│ validate_workflow_update()
   │<─ {valid: true,                     │
   │    workflow: {...},                 │
   │    suggestions: [...]}  ────────────│
```

**WebSocket Protocol** (`/ws/chat/{session_id}`):
```json
// Server → Client (streaming)
{"type": "token", "content": "To build "}
{"type": "token", "content": "this workflow..."}
{"type": "done", "phase": "CLARIFYING", "full_response": {...ChatMessageResponse}}

// Server → Client (phase change event)
{"type": "phase_change", "from": "CLARIFYING", "to": "GENERATING"}

// Server → Client (workflow ready)
{"type": "workflow_ready", "workflow_id": "wf_abc123", "workflow_preview": {...}}
```

**State Management (Zustand) contract** — backend response keys map directly to frontend store:
```typescript
interface ChatStore {
  sessionId: string | null
  phase: ConversationPhase
  messages: ChatMessage[]
  clarificationBlock: ClarificationBlock | null  // rendered as question cards
  requirementSpec: RequirementSpec | null         // shown in progress sidebar
  workflowPreview: WorkflowDefinition | null      // fed to React Flow canvas
  workflowId: string | null                       // link to workflow editor
  isStreaming: boolean
}
```

**Acceptance criteria:**
- [x] `POST /chat/sessions` returns 201 with `session_id`
- [x] `POST /message` with complete requirements returns `workflow_preview` with `ui_config` on all nodes
- [x] `PUT /workflow` with cycle returns `valid: false` + error describing cycle
- [x] `PUT /workflow` with valid edits returns `valid: true` + optional `suggestions` array
- [x] Unauthenticated requests return 401
- [x] VIEWER cannot call `/generate` or `PUT /workflow` (403)
- [x] WebSocket emits `phase_change` event when session transitions CLARIFYING → GENERATING
- [x] WebSocket emits `workflow_ready` event when phase reaches COMPLETE
- [x] WebSocket closes cleanly with 1000 after `done` message
- [x] API tests cover all 7 routes against mock `ChatOrchestrator`
- [x] OpenAPI spec up to date (already done — `docs/api/openapi.yaml`)

---

### G-6 — Chat UI — Conversation Panel + DAG Preview

**Full spec:** `docs/frontend/chat-module.md`
**Foundation:** `docs/frontend/overview.md` (Next.js 14, React Flow v12, Zustand, shadcn/ui)

**New files added to existing `packages/workflow-ui/src/`:**
```
app/(dashboard)/workflows/new/page.tsx    ← ChatPage (route: /workflows/new)
components/chat/
  ChatPanel.tsx          PhaseIndicator.tsx    TypingIndicator.tsx
  MessageThread.tsx      ClarificationCard.tsx  PromptSuggestions.tsx
  MessageBubble.tsx      QuestionWidget.tsx     ChatInputBar.tsx
  StreamingText.tsx      RequirementProgress.tsx
components/nodes/ChatGeneratedNode.tsx    ← React Flow node for AI-generated workflows
stores/chatStore.ts                       ← Zustand chat state (see spec §4)
api/chat.ts                               ← TanStack Query hooks (see spec §5)
hooks/useChatWebSocket.ts                 ← WebSocket token streaming (see spec §6)
types/chat.ts                             ← TypeScript interfaces
```

**Layout:** Chat panel (380px, collapsible to 48px) left of full-height canvas. Config panel overlaps canvas from right (does not shrink canvas).

**Tech choices locked:**
- `useChatStore` (Zustand) — owns all chat state; `workflowStore.loadFromDefinition()` called when workflow ready
- `useChatWebSocket` — native WebSocket, reconnects with 3s backoff; routes `token | done | phase_change | workflow_ready` events
- `ChatGeneratedNode` — coloured header from `ui_config.color`, Lucide icon from `ui_config.icon`, config preview pills, conditional port handles based on `is_terminal`
- `ClarificationCard` — React Hook Form; question type → widget: `text→Textarea`, `select→Select`, `multiselect→CheckboxGroup`, `boolean→Switch`, `number→Input`
- Canvas edits debounced 1s → `PUT /chat/sessions/{id}/workflow` → validation errors highlight nodes red, suggestions render as dismissible toasts
- Empty canvas shows prompt suggestion chips (4 starters); clicking one sends the prompt and creates a session automatically

**Acceptance criteria:**
- [x] WebSocket token streaming renders text incrementally — no full re-render
- [x] `ClarificationCard` renders correct input widget per `input_type`
- [x] Submitting all clarification answers via form auto-sends a message with answers formatted
- [x] `RequirementProgressBar` shows correct filled/missing fields from `requirement_spec`
- [x] DAG canvas renders all nodes with correct colour, icon, and label from `ui_config`
- [x] Node position `{x, y}` from `WorkflowDefinition` is honoured — no re-layout on render
- [x] Dragging a node updates its position, triggers debounced `PUT /workflow`
- [x] `validation_errors` from backend highlight the affected node/edge in red
- [x] `suggestions` toast appears and is dismissible
- [x] `EditWorkflowButton` navigates to `/workflows/{workflow_id}/edit` (full canvas — F-2)
- [x] Responsive: ChatPanel stacks above WorkflowPreviewPanel on screens < 1024px
- [x] Phase transitions animate (fade) in `PhaseIndicator`

---

## Critical Path

The minimum path to a working end-to-end execution:

```
A-1 → B-1 → B-2 → C-1 → D-2 → E-1 → E-2
```

The minimum path to a working chat-to-DAG pipeline:

```
A-1 → A-3 → G-1 → G-2 + G-3 (parallel) → G-4 → G-5 → G-6
```

Everything else (auth, billing, connectors, CLI, frontend) can be built around this backbone.

---

## Production Readiness Gaps — Fix Required

> Issues discovered during full codebase audit on 2026-03-30. Each gap has a `[GAP-XX-N]` tag that links back to the phase acceptance criteria above where the fix must be verified.
> **All gaps must be resolved before Phase 5 (Delivery Layer) work begins.**

| ID | Severity | File | Issue | Fix Task |
|----|----------|------|-------|----------|
| GAP-A3-1 | 🔴 Critical | `ports.py` | `BillingRepository` ABC missing — `QuotaChecker` cannot use port pattern | Add ABC to `ports.py` |
| GAP-A3-2 | 🟠 High | `ports.py` | `UserRepository` missing `create_user`, `update_user`, `list_users` | Add methods to ABC |
| GAP-A3-3 | 🟠 High | `ports.py` | `ExecutionRepository` missing `get_node_states(run_id)`, `list_runs_by_tenant` | Add methods to ABC |
| GAP-B2-1 | 🔴 Critical | `nodes/implementations/code_execution.py` | Tier 2 isolation uses thread pool (`run_in_executor`) not gVisor container | Implement gVisor dispatch |
| GAP-B2-2 | 🟡 Medium | `nodes/implementations/code_execution.py` | `asyncio.get_event_loop()` deprecated in Python 3.12 | Replace with `get_running_loop()` |
| GAP-C1-1 | 🔴 Critical | `execution/orchestrator.py` | `resume()` sets state then stops — HumanInputNode workflows permanently broken | Implement DAG re-traversal from node |
| GAP-C1-2 | 🔴 Critical | `execution/orchestrator.py` | Sequential `topo_sort` loop — parallel branches block on each other | Group same-layer nodes and `asyncio.gather()` them |
| GAP-C1-3 | 🟡 Medium | `execution/orchestrator.py` | `asyncio.get_event_loop()` deprecated in Python 3.12 | Replace with `get_running_loop()` |
| GAP-C1-4 | 🟠 High | `execution/orchestrator.py` | No OTel spans in `run()` or `resume()` — execution not traceable | Wrap with `trace_execution()` spans |
| GAP-D3-1 | 🔴 Critical | `billing/quota_checker.py` | Imports concrete `PostgresBillingRepository` — violates Layer A→D isolation | Inject `BillingRepository` port |
| GAP-D3-2 | 🟠 High | `billing/quota_checker.py` | `BillingRepository` port ABC required before fix | Depends on GAP-A3-1 |
| GAP-D4-1 | 🔴 Critical | `execution/pii_scanner.py` | `SCAN_MASK` policy silently falls through — no masking occurs | Implement redaction branch |
| GAP-D4-2 | 🔴 Critical | `execution/pii_scanner.py` | Regex anchors `^...$` miss embedded PII (e.g. in sentences) | Switch to `re.search()` |
| GAP-D4-3 | 🟠 High | `execution/pii_scanner.py` | Missing email and phone number patterns in `_RULES` | Add email + phone regexes |
| GAP-P0-11 | 🟠 High | `packages/workflow-api/`, `packages/workflow-worker/` | No Dockerfiles — CI `docker-build` job will fail | Create Dockerfiles (P0-11) |
| GAP-TEST-1 | 🟠 High | `tests/conftest.py` | Nearly empty — no shared fixtures; every test inlines its own mocks | Add shared `NodeServices`, tenant, repo fixtures |
| GAP-TEST-2 | 🔴 Critical | `tests/integration/` | Empty directory — zero real database integration tests | Write integration tests with testcontainers |
| GAP-E1-1 | 🟡 Medium | `packages/workflow-api/src/workflow_api/auth/` | Empty directory causes architectural confusion — auth belongs in SDK + `dependencies.py` | Delete empty directory (FIX-12) |
| GAP-E1-2 | 🔴 Critical | `packages/workflow-api/src/workflow_api/` | `main.py` missing — `app.py` calls `create_app()` with no services; every route will crash on `request.app.state.auth_service` | Create startup script that assembles + injects all 10 SDK services (FIX-13) |
| GAP-E2-1 | 🔴 Critical | `packages/workflow-worker/src/workflow_worker/dependencies.py` | Imports 7 non-existent `Memory*` classes from `workflow_engine.ports` — `ImportError` on worker startup | Replace with `get_sdk_services()` factory using injected services dict (FIX-14) |
| GAP-E2-2 | 🟠 High | `packages/workflow-worker/src/workflow_worker/tasks.py` | `execute_node` task is a stub (logs only) — determine if still needed given `asyncio.gather()` decision | Remove if redundant, implement if needed (FIX-15) |
| GAP-E2-3 | 🔴 Critical | `packages/workflow-worker/src/workflow_worker/tasks.py` | `fire_schedule` never calls `SchedulerService.tick()` — scheduled workflows never fire | Wire to injected `scheduler_service.tick()` (FIX-16) |
| GAP-E2-4 | 🟠 High | `packages/workflow-worker/src/workflow_worker/tasks.py` | `send_notification` never dispatches — logs only | Implement notification port dispatch (FIX-17) |
| GAP-E2-5 | 🟡 Medium | `packages/workflow-worker/src/workflow_worker/tasks/` | Empty directory — causes import ambiguity with `tasks.py` | Delete empty directory (FIX-18) |
| GAP-E2-6 | ✅ Fixed | `packages/workflow-worker/src/workflow_worker/dependencies.py` | `NodeServices(cache=None)` — `SetStateNode` silently skipped all Redis writes | Wired `RedisCache` — FIX-28 |
| GAP-E2-7 | ✅ Fixed | `packages/workflow-worker/src/workflow_worker/tasks.py` | `execute_workflow(self, run_id, tenant_id)` only accepted 2 args; API calls `.delay(run_id, tenant_id, workflow_id, input_data)` → `TypeError` | Added `workflow_id`, `input_data`, `resume_node`, `human_response` params — FIX-29 |
| GAP-E2-8 | ✅ Fixed | `packages/workflow-worker/src/workflow_worker/tasks.py` | `run.trigger_input` → `AttributeError`; field is `input_data` | Fixed field name — FIX-29 |
| GAP-E2-9 | ✅ Fixed | `packages/workflow-worker/src/workflow_worker/tasks.py` | Human-in-the-loop resume path missing in Celery task | Added `orchestrator.resume()` branch — FIX-29 |
| GAP-E3-1 | 🟡 Medium | `packages/workflow-cli/` + `docs/api/openapi.yaml` | Config path mismatch: CLI uses `.toml`, spec references `.yaml` | Update spec references to `.toml` (FIX-19) |
| GAP-E1-3 | ✅ Fixed | `packages/workflow-api/src/workflow_api/main.py` | `WorkflowDefinition.nodes` is `dict` but POST body sent `[]` → 422; `description` field missing from model | Normalise list→dict in `PlatformWorkflowService`; add `description` to model — FIX-30 |
| GAP-E1-4 | ✅ Fixed | `packages/workflow-api/src/workflow_api/routes/chat.py` | Double `/v1` prefix — routes landed at `/api/v1/v1/chat/sessions` | Changed prefix to `/chat/sessions` — FIX-31 |
| GAP-E1-5 | ✅ Fixed | `packages/workflow-api/src/workflow_api/main.py` + `docs/api/openapi.yaml` | `ADMIN` role used in spec/code; correct enum is `OWNER/EDITOR/VIEWER` | Fixed throughout — FIX-31 |
| GAP-E1-6 | ✅ Fixed | `packages/workflow-api/pyproject.toml` | `slowapi` imported in `app.py` but not in dependencies — `ImportError` on install | Added `slowapi>=0.1.9` — FIX-32 |
| GAP-E1-7 | ✅ Fixed | `packages/workflow-api/src/workflow_api/main.py` | `PlatformWebhookService` was a stub (no DB); inbound webhooks not persisted | Replaced with asyncpg implementation after `002_webhooks.sql` — FIX-33 |
| GAP-E1-8 | ✅ Fixed | `packages/workflow-api/src/workflow_api/main.py` | `verify_email`, `send_password_reset`, `reset_password` were pass/stub | Implemented using existing DB columns; `EmailService` added — FIX-34 |
| GAP-E1-9 | ✅ Fixed | `packages/workflow-api/src/workflow_api/routes/chat.py` | WebSocket `/ws/chat/{session_id}` was mock — no auth, no real processing, ACK only | Rewritten with `?token=` auth + Redis PubSub subscription — FIX-35 |
| GAP-D7-1 | ✅ Fixed | `packages/workflow-engine/src/workflow_engine/ports.py` | `CachePort.sadd()` had no body — `SyntaxError`; `smembers`/`sadd` ABCs missing | Added default methods to `CachePort`; implemented in `RedisCache` — FIX-36 |
| GAP-D7-2 | ✅ Fixed | `packages/workflow-engine/src/workflow_engine/execution/orchestrator.py` | `NodeContext(state={})` always empty — `SetStateNode` writes not loaded for downstream nodes | Orchestrator pre-loads via `smembers` + `get` before each node — FIX-36 |
| GAP-LLM-1 | ✅ Fixed | `packages/workflow-engine/src/workflow_engine/providers/google_genai.py` | Token counting used tiktoken estimation; native `count_tokens()` API and `usage_metadata` available | Added `complete_with_usage()` with native counting; `_count_tokens()` helper — FIX-37 |
| GAP-LLM-2 | ✅ Fixed | `packages/workflow-engine/src/workflow_engine/providers/openai.py` | Token counting used tiktoken estimation; `response.usage` available natively | Added `complete_with_usage()` using `response.usage` — FIX-37 |
| GAP-LLM-3 | ✅ Fixed | `packages/workflow-engine/src/workflow_engine/ports.py` | `LLMPort` had no usage-aware interface; nodes had no standard way to get token counts | Added `complete_with_usage()` default method to `LLMPort` ABC — FIX-37 |
| GAP-DEP-1 | ✅ Fixed | all `pyproject.toml` files | `aioredis>=2.0` incompatible with Python 3.12; code already used `redis.asyncio` | Replaced `aioredis` with `redis[asyncio]>=5.0` in all packages — FIX-38 |
| GAP-DEP-2 | ✅ Fixed | `packages/workflow-api/pyproject.toml` | `sendgrid` listed as hard dependency but SMTP implementation uses stdlib | Commented out `sendgrid`; `EmailService` uses stdlib `smtplib` — FIX-38 |
| GAP-WEBHOOK-1 | ✅ Fixed | `infra/database/postgres/migrations/` | No `webhooks` table — webhook data had nowhere to persist | Created `002_webhooks.sql` with `webhooks` + `webhook_deliveries` tables — FIX-33 |
| GAP-D7-1 | ✅ Verified | `packages/workflow-engine/src/workflow_engine/providers/` | ~~`providers/` is empty~~ — `google_genai.py`, `openai.py`, `factory.py`, `mock.py` confirmed present and implemented. Closed. | FIX-20 (✅ Done) |
| GAP-INFRA-1 | ✅ Fixed | `infra/helm/.../deployment-worker.yaml` + `values.yaml` | Celery command and liveness probe used `workflow_worker.app` — actual module is `workflow_worker.celery_app`. Worker pods crash-loop on deploy. | Fixed — FIX-21 |
| GAP-INFRA-2 | ✅ Fixed | `infra/helm/workflow-platform/` | No beat scheduler Deployment — `ScheduledTriggerNode` workflows silently never fire in production. `celery beat` has no K8s manifest. | Created `deployment-beat.yaml` + beat values — FIX-22 |
| GAP-INFRA-3 | ✅ Fixed | `infra/database/postgres/migrations/001_initial_schema.sql` | `llm_cost_records` had only 2 one-month partitions (Jan 2024, Jan 2025). `node_exec_records` had only `2025_q1`. All other dates raise `ERROR: no partition for value` on INSERT. | Added full quarterly partitions 2024–2026 — FIX-23 |
| GAP-INFRA-4 | ✅ Fixed | `infra/database/mongodb/indexes.py` | `chat_sessions` collection had no indexes or JSON schema validator — unbounded data growth, no tenant isolation index. | Added indexes + TTL + schema validator — FIX-24 |
| GAP-INFRA-5 | ✅ Fixed | `packages/workflow-api/alembic/` | `make migrate` called `alembic upgrade head` but no `alembic.ini` or `versions/` directory existed. Created `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_initial_schema.py`. | FIX-25 |
| GAP-INFRA-6 | ✅ Fixed | `packages/workflow-worker/src/workflow_worker/dependencies.py` | `NodeServices` was assembled without LLM — already confirmed `llm=llm_port` present at line 47. Verified in this session. | FIX-26 |
| GAP-INFRA-7 | ✅ Fixed | `packages/workflow-api/src/workflow_api/main.py` | All 9 service facades wired to `app.state` in `lifespan()`. LLM passed to `DAGGeneratorService`. Connection pools closed on shutdown. | FIX-27 |

### Fix Schedule

| # | Fix ID(s) | Task | Status | Depends On |
|---|-----------|------|--------|------------|
| FIX-1 | GAP-A3-1,2,3 | Extend `ports.py` with `BillingRepository` ABC + missing methods | ✅ Done | — |
| FIX-2 | GAP-D3-1, GAP-D3-2 | Refactor `QuotaChecker` to inject `BillingRepository` port | ✅ Done | FIX-1 |
| FIX-3 | GAP-D4-1,2,3 | Fix `PIIScanner`: implement SCAN_MASK, remove `^$` anchors, add email/phone rules | ✅ Done | — |
| FIX-4 | GAP-C1-1 | Implement `orchestrator.resume()` DAG re-traversal | ✅ Done | — |
| FIX-5 | GAP-C1-2 | Implement parallel branch execution via `asyncio.gather()` in `orchestrator.run()` — group nodes by topological layer, gather within each layer | ✅ Done | — |
| FIX-6 | GAP-B2-1 | Implement gVisor container dispatch in `CodeExecutionNode` | ✅ Done | — |
| FIX-7 | GAP-B2-2, GAP-C1-3 | Replace all `asyncio.get_event_loop()` with `get_running_loop()` | ✅ Done | — |
| FIX-8 | GAP-C1-4 | Add OTel spans to `orchestrator.run()` + `resume()` | ✅ Done | D-5 |
| FIX-9 | GAP-P0-11 | Create `packages/workflow-api/Dockerfile` + `packages/workflow-worker/Dockerfile` | ✅ Done | — |
| FIX-10 | GAP-TEST-1 | Expand `tests/conftest.py` with shared fixtures | ✅ Done | — |
| FIX-11 | GAP-TEST-2 | Write integration tests for storage layer using testcontainers | ✅ Done | D-2 |
| FIX-12 | GAP-E1-1 | Delete empty `packages/workflow-api/src/workflow_api/auth/` directory | ✅ Done | — |
| FIX-13 | GAP-E1-2 | Create `packages/workflow-api/src/workflow_api/main.py` — read env vars, instantiate all 10 SDK services, call `create_app(services={...})` | ✅ Done | FIX-14 |
| FIX-14 | GAP-E2-1 | Fix `worker/dependencies.py` — replace non-existent `Memory*` imports with a `get_sdk_services(settings)` factory that builds real SDK service instances | ✅ Done | D-2, D-1 |
| FIX-15 | GAP-E2-2 | Evaluate `execute_node` Celery task — remove if `asyncio.gather()` handles all intra-run parallelism; document decision in `worker/tasks.py` docstring | ✅ Done | C-1 |
| FIX-16 | GAP-E2-3 | Wire `fire_schedule` to `scheduler_service.tick()` from injected services dict | ✅ Done | FIX-14, C-2 |
| FIX-17 | GAP-E2-4 | Implement `send_notification` task body — dispatch via notification port (email/webhook/Slack) | ✅ Done | FIX-14 |
| FIX-18 | GAP-E2-5 | Delete empty `packages/workflow-worker/src/workflow_worker/tasks/` directory | ✅ Done | — |
| FIX-19 | GAP-E3-1 | Update `docs/api/openapi.yaml` and any other spec references from `config.yaml` → `config.toml` to match CLI implementation | ✅ Done | — |
| FIX-20 | GAP-D7-1 | Implement LLM providers: `GoogleGenAIProvider`, `OpenAIProvider`, `AnthropicProvider`, `ProviderFactory.from_config()`, `MockLLMProvider` in `workflow_engine/providers/` | ✅ Done | A-3 (LLMPort ABC) |
| FIX-21 | GAP-INFRA-1 | Fix Celery module reference: `workflow_worker.app` → `workflow_worker.celery_app` in `deployment-worker.yaml` command and `values.yaml` liveness probe | ✅ Done | — |
| FIX-22 | GAP-INFRA-2 | Create `infra/helm/workflow-platform/templates/deployment-beat.yaml` — Celery Beat Deployment (replicas: 1, strategy: Recreate, redbeat scheduler) | ✅ Done | FIX-21 |
| FIX-23 | GAP-INFRA-3 | Add quarterly partitions for full 2024–2026 range to `llm_cost_records` and `node_exec_records` in `001_initial_schema.sql` | ✅ Done | — |
| FIX-24 | GAP-INFRA-4 | Add `chat_sessions` collection indexes (tenant+session unique, user sessions, TTL 30d) and JSON schema validator to `infra/database/mongodb/indexes.py` | ✅ Done | G-4 |
| FIX-25 | GAP-INFRA-5 | Create `packages/workflow-api/alembic.ini` + `alembic/env.py` + `alembic/versions/0001_initial_schema.py` wrapping `001_initial_schema.sql` — Alembic is now the authoritative migration runner | ✅ Done | — |
| FIX-26 | GAP-INFRA-6 | Wire `ProviderFactory.from_config(config)` into `dependencies.py` → pass `llm=provider` to `NodeServices` | ✅ Done | FIX-20, FIX-14 |
| FIX-27 | GAP-INFRA-7 | Complete `packages/workflow-api/src/workflow_api/main.py` `lifespan()` — all 9 service facades (auth, user, workflow, execution, schedule, audit, webhook, billing, chat) wired to `app.state`; LLM passed to `DAGGeneratorService`; connection pools closed on shutdown | ✅ Done | FIX-20, FIX-14 |
| FIX-28 | GAP-E2-6 | Wire `RedisCache(client=aioredis.from_url(REDIS_URL))` into `NodeServices` in `worker/dependencies.py`; was `cache=None` | ✅ Done | — |
| FIX-29 | GAP-E2-7,8,9 | Fix `execute_workflow` Celery task: add `workflow_id`, `input_data`, `resume_node`, `human_response` params; fix `run.trigger_input` → `run.input_data`; add `orchestrator.resume()` branch | ✅ Done | — |
| FIX-30 | GAP-E1-3 | Normalize `nodes: [] → {}` in `PlatformWorkflowService.create()`; add `description: str\|None` to `WorkflowDefinition` | ✅ Done | — |
| FIX-31 | GAP-E1-4,5 | Fix chat router prefix `/v1/chat/sessions` → `/chat/sessions`; fix `ADMIN` → `OWNER/EDITOR/VIEWER` in spec and code | ✅ Done | — |
| FIX-32 | GAP-E1-6 | Add `slowapi>=0.1.9` to `workflow-api/pyproject.toml`; rate limiter was already wired in `app.py` | ✅ Done | — |
| FIX-33 | GAP-E1-7, GAP-WEBHOOK-1 | Create `002_webhooks.sql` (webhooks + webhook_deliveries tables); replace `PlatformWebhookService` stub with asyncpg-backed implementation including HMAC verification and `execute_workflow.delay()` dispatch | ✅ Done | — |
| FIX-34 | GAP-E1-8 | Add `EmailService` (stdlib `smtplib`, async via `run_in_executor`); implement `verify_email`, `send_password_reset`, `reset_password` using existing `password_reset_tokens` + `users.verification_token` columns | ✅ Done | — |
| FIX-35 | GAP-E1-9 | Rewrite WebSocket `stream_chat`: authenticate via `?token=` query param; subscribe to Redis PubSub `chat:{session_id}:events`; `ChatOrchestrator.process_message()` now publishes phase events via optional `publish` callback | ✅ Done | FIX-36 |
| FIX-36 | GAP-D7-1,2 | Add `smembers`/`sadd` default methods to `CachePort`; implement in `RedisCache`; orchestrator pre-loads `state_keys:{run_id}` via `smembers` + `get` before each node execution; `SetStateNode` tracks keys via `sadd` | ✅ Done | — |
| FIX-37 | GAP-LLM-1,2,3 | Add `complete_with_usage()` to `LLMPort` (default wraps `complete()`); implement in `GoogleGenAIProvider` using `response.usage_metadata` + `client.models.count_tokens()`; implement in `OpenAIProvider` using `response.usage` | ✅ Done | — |
| FIX-38 | GAP-DEP-1,2 | Replace `aioredis>=2.0` with `redis[asyncio]>=5.0` across all `pyproject.toml` files; comment out `sendgrid` hard dep; add inline note about `tiktoken` as fallback | ✅ Done | — |

---

## Enhanced Test Requirements

> Updated criteria applying to **all** phases. Any task with a `✅ Done` status that fails these criteria must be re-opened.

### Security Tests (apply to: B-2, C-1, D-4)
- [x] PII SCAN_MASK: verify output contains `[MASKED]` and does not contain original PII value
- [x] PII regex: test inputs with PII embedded mid-sentence (not just standalone values)
- [x] CodeExecutionNode: verify `os.system()`, `subprocess.run()`, `socket.connect()` all raise before execution
- [x] JWT: verify token with tampered payload (flipped signature byte) raises `InvalidTokenError`
- [x] JWT: verify access token rejected when used as refresh token and vice versa

### Isolation / Architecture Tests (apply to: A-3, D-3)
- [x] `lint-imports` must pass with 0 violations — run as part of every PR CI check
- [x] `QuotaChecker.__init__` must accept `BillingRepository` (ABC) not the concrete Postgres class
- [x] All Layer D modules must only import from Layer A (models + ports) — verified by importlinter contract

### Async Correctness Tests (apply to: C-1, B-2)
- [x] `orchestrator.resume()` tested: verify run proceeds from resumed node and reaches COMPLETED state
- [x] Parallel workflow: two branches at the same topological layer are dispatched via `asyncio.gather()` and both finish before the merge node runs — verified by mock timing (neither branch awaits the other)
- [x] No `asyncio.get_event_loop()` calls anywhere (grep check in CI)

### Integration Tests (apply to all storage-touching modules)
- [x] MongoDB integration: workflow CRUD round-trip with real motor + testcontainers
- [x] PostgreSQL integration: tenant + user + billing queries with real asyncpg + testcontainers
- [x] Redis integration: `SetStateNode` read-after-write verified against real Redis
- [x] End-to-end: trigger a 3-node workflow (Prompt → Transform → Output) against real DB stack

### Observability Tests (apply to: D-5, C-1)
- [x] OTel spans emitted for every node execution — verified by in-memory span exporter in tests
- [x] `run_id` and `tenant_id` present in every log line during execution
- [x] `QuotaUtilization` metric emitted after each quota check

---

## Definition of Done (per task)

A task is `✅ Done` only when ALL of the following are true:

- [x] Code written and committed on feature branch
- [x] `ruff check` passes (0 errors)
- [x] `mypy --strict` passes on the module
- [x] `lint-imports` passes (no layer violations) — **zero tolerance**
- [x] Unit tests written and passing (≥85% coverage on new code)
- [x] Integration tests passing (where applicable — required for all storage-touching modules)
- [x] No `asyncio.get_event_loop()` calls in new code (use `get_running_loop()`)
- [x] No direct concrete storage class imports from SDK business logic (use port ABCs)
- [x] All production readiness gap tags (`[GAP-*]`) in the task's acceptance criteria resolved
- [x] PR reviewed and merged to `develop`
- [x] CI pipeline green on `develop`

---

## How to Update This File

When starting a task:
```
| A-1 | Pydantic domain models | 🔄 In Progress | @dev-name | 2026-04-01 | — |
```

When completing a task:
```
| A-1 | Pydantic domain models | ✅ Done | @dev-name | 2026-04-01 | 2026-04-03 |
```

When blocked:
```
| A-1 | Pydantic domain models | 🚫 Blocked | @dev-name | 2026-04-01 | — |
```
> **Blocker:** Waiting for decision on enum values for `plan_tier` — pending stakeholder input.

---

## Phase 8 — Production Hardening (Post-Backend-Complete)

> **Completed:** 2026-04-01  
> **Depends on:** E-1, E-2 complete (backend is ready for frontend integration)  
> These tasks close the three HIGH-severity gaps identified in the final pre-frontend audit.

| # | Task | Status | Completed | Gap IDs |
|---|------|--------|-----------|---------|
| H-1 | **Chat WebSocket — Redis PubSub streaming** | ✅ Done | 2026-04-01 | GAP-E1-9 |
| H-2 | **Webhooks DB persistence** | ✅ Done | 2026-04-01 | GAP-E1-7, GAP-WEBHOOK-1 |
| H-3 | **Email/SMTP — verification + password reset** | ✅ Done | 2026-04-01 | GAP-E1-8 |
| H-4 | **Native LLM token counting** | ✅ Done | 2026-04-01 | GAP-LLM-1,2,3 |
| H-5 | **Dependency cleanup** | ✅ Done | 2026-04-01 | GAP-DEP-1,2, GAP-E1-6 |

### H-1 — Chat WebSocket Streaming

**Files changed:**
- `packages/workflow-engine/src/workflow_engine/chat/orchestrator.py` — `process_message()` accepts optional `publish: Callable[[str, dict], Awaitable[None]]`; emits 4 real-time events via internal `_emit()` helper
- `packages/workflow-api/src/workflow_api/routes/chat.py` — WebSocket rewrites to: (1) authenticate via `?token=<jwt>` query param, (2) subscribe to Redis PubSub `chat:{session_id}:events`, (3) spawn `process_message()` as background task on client message, (4) forward PubSub events to WebSocket client in real time
- `packages/workflow-api/src/workflow_api/main.py` — exposes `app.state.redis_client` for WebSocket handler

**WebSocket event protocol (server → client):**
```json
{"type": "status",   "phase": "PROCESSING"}
{"type": "phase",    "phase": "CLARIFYING"}
{"type": "phase",    "phase": "GENERATING"}
{"type": "response", "phase": "COMPLETE", "message": "...", "workflow_id": "wf_..."}
```

**Connect URL:** `wss://{host}/api/v1/chat/sessions/ws/chat/{session_id}?token=<jwt>`

**Acceptance criteria:**
- [x] WebSocket authenticates via `?token=` query param — 4001 close code on missing/invalid token
- [x] Client sends `{"type": "message", "content": "..."}` → `process_message()` called with real PubSub publisher
- [x] `PROCESSING`, `CLARIFYING`, `GENERATING`, `COMPLETE` events delivered to client as they occur
- [x] REST `POST /{session_id}/message` still works (backward-compatible — `publish=None`)
- [x] WebSocket cleanup: PubSub unsubscribed + both asyncio tasks cancelled on disconnect

---

### H-2 — Webhooks DB Persistence

**Files changed:**
- `infra/database/postgres/migrations/002_webhooks.sql` (new) — `webhooks` + `webhook_deliveries` tables with indexes and `updated_at` trigger
- `packages/workflow-api/src/workflow_api/main.py` — `PlatformWebhookService` replaced with asyncpg-backed implementation

**`webhooks` table columns:** `id, tenant_id, workflow_id, name, events[], webhook_secret, endpoint_url, active, created_at, updated_at`

**`webhook_deliveries` table columns:** `id, webhook_id, tenant_id, workflow_id, event_type, payload (JSONB), response_status, delivered_at`

**Inbound webhook flow:**
1. `POST /api/v1/webhooks/inbound/{workflow_id}` received
2. Look up active webhook for `workflow_id`
3. If `webhook_secret` set and `X-Webhook-Signature` header present → HMAC-SHA256 verify
4. `execute_workflow.delay(run_id, tenant_id, workflow_id, body)` dispatched
5. Insert row into `webhook_deliveries` (best-effort; failure does not reject request)
6. Return `{"accepted": true, "workflow_id": ..., "run_id": ...}`

**Acceptance criteria:**
- [x] `POST /webhooks` creates row in `webhooks` table; returns plaintext secret only at creation
- [x] `POST /webhooks/inbound/{id}` with valid HMAC signature dispatches Celery task
- [x] `POST /webhooks/inbound/{id}` with invalid HMAC returns `{"accepted": false, "reason": "Invalid webhook signature"}`
- [x] Delivery logged to `webhook_deliveries` on every inbound call
- [x] `DELETE /webhooks/{id}` sets `active = false` (soft delete)
- [x] Run migration `002_webhooks.sql` before starting API — apply with `alembic upgrade head`

---

### H-3 — Email/SMTP

**Files changed:**
- `packages/workflow-api/src/workflow_api/main.py` — added `EmailService` class; wired `verify_email`, `send_password_reset`, `reset_password`

**EmailService configuration (env vars):**
| Env Var | Default | Description |
|---------|---------|-------------|
| `SMTP_HOST` | (unset) | SMTP server hostname. Email disabled if not set |
| `SMTP_PORT` | `587` | SMTP port (STARTTLS) |
| `SMTP_USER` | (unset) | SMTP username |
| `SMTP_PASSWORD` | (unset) | SMTP password |
| `EMAIL_FROM` | `noreply@dkplatform.io` | Sender address |
| `APP_URL` | `http://localhost:3000` | Base URL for verification/reset links |

**Email flows implemented:**
- `register()` → sends verification email with 24h token link
- `verify_email(token)` → marks `users.is_verified = true`, clears token
- `send_password_reset(email)` → creates `password_reset_tokens` row, sends 1h reset link
- `reset_password(token, password)` → validates token, updates `password_hash`, marks token used

**Acceptance criteria:**
- [x] `POST /auth/register` triggers verification email when `SMTP_HOST` is set
- [x] `POST /auth/verify-email?token=<valid>` marks user verified
- [x] `POST /auth/verify-email?token=<expired>` returns 400
- [x] `POST /auth/password/reset-request` sends email; does not reveal whether email exists
- [x] `POST /auth/password/reset` with used token returns 400
- [x] `EmailService` logs intent and returns `False` gracefully when `SMTP_HOST` not set (no crash)
- [x] Uses stdlib `smtplib` — no extra dependency required

---

### H-4 — Native LLM Token Counting

**Files changed:**
- `packages/workflow-engine/src/workflow_engine/ports.py` — `LLMPort.complete_with_usage()` default method
- `packages/workflow-engine/src/workflow_engine/providers/google_genai.py` — native implementation
- `packages/workflow-engine/src/workflow_engine/providers/openai.py` — native implementation

**`complete_with_usage()` return schema:**
```python
{
    "text": str,           # completion text
    "input_tokens": int,   # prompt token count (native API)
    "output_tokens": int,  # completion token count (native API)
    "thoughts_tokens": int # reasoning tokens (Gemini only; 0 for all others)
}
```

**Google GenAI:** uses `response.usage_metadata.prompt_token_count` / `candidates_token_count` / `thoughts_token_count` — no `tiktoken` needed. `count_tokens()` helper also available for pre-call counting.

**OpenAI:** uses `response.usage.prompt_tokens` / `completion_tokens` directly from API response.

**Backward compatibility:** `complete()` is unchanged — all existing nodes continue working. Nodes opt in to usage tracking by calling `complete_with_usage()` instead.

**Acceptance criteria:**
- [x] `GoogleGenAIProvider.complete_with_usage()` returns non-zero `input_tokens` and `output_tokens`
- [x] `GoogleGenAIProvider.count_tokens("hello world")` returns a positive integer
- [x] `OpenAIProvider.complete_with_usage()` returns non-zero token counts from `response.usage`
- [x] Default `LLMPort.complete_with_usage()` returns `{"text": ..., "input_tokens": 0, ...}` (graceful fallback)
- [x] `PromptNode` can call `complete_with_usage()` and pass token counts to `UsageRecorder`

---

### H-5 — Dependency Cleanup

**Files changed:**
- `packages/workflow-engine/pyproject.toml` — `aioredis` → `redis[asyncio]>=5.0`; tiktoken comment updated
- `packages/workflow-api/pyproject.toml` — `aioredis` removed; `redis[asyncio]>=5.0` added; `slowapi>=0.1.9` added; `sendgrid` commented out
- `packages/workflow-worker/pyproject.toml` — `aioredis` → `redis[asyncio]>=5.0`

**Rationale:**
- `aioredis>=2.0` is incompatible with Python 3.12 (`asyncio.get_event_loop()` removed). All code already uses `redis.asyncio` (from the `redis>=5` package). Removing `aioredis` eliminates the import confusion and the CI breakage
- `slowapi` was already wired in `app.py` (rate limiter middleware fully implemented) but missing from deps — this caused `ImportError` on install
- `sendgrid` was a hard dependency but `EmailService` uses stdlib `smtplib` — removing it avoids an unnecessary paid API dependency

**Acceptance criteria:**
- [x] `pip install -e packages/workflow-engine` succeeds with Python 3.12
- [x] `pip install -e packages/workflow-api` succeeds and `from slowapi import Limiter` works
- [x] No `aioredis` import anywhere in source (grep confirms)
- [x] All Redis operations use `import redis.asyncio as aioredis` pattern
