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
| F-1 | **Auth pages + shell layout** | 🔄 In Progress | Frontend team | 2026-04-02 | — | E-1 (auth routes) ✅ |
| F-2 | **Workflow canvas (React Flow)** | ⏳ Pending | — | — | — | F-1 |
| F-3 | **DynamicConfigForm + node panels** | ⏳ Pending | — | — | — | F-2 |
| F-4 | **Execution monitor + live updates** | ⏳ Pending | — | — | — | F-2, E-2 ✅ |
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
| FIX-39 | GAP-B23 | Audit log writes used `tenant_id="system"` — invisible to tenant queries. Root cause: `register()` returned no `tenant_id`; `login()` returned no `user_id`/`tenant_id`. Fixed both service methods; all audit routes now use real tenant-scoped values | ✅ Done (2026-04-02) | — |
| FIX-40 | GAP-B24 | `schedule.input_data` field missing from `ScheduleModel` — `fire_schedule` task always created runs with `input_data={}`. Added `input_data: dict` to `ScheduleModel`; `PlatformScheduleService.create()` and `fire_schedule` task updated | ✅ Done (2026-04-02) | — |
| FIX-41 | GAP-B22 | `result.get("workflow_id")` returned `None` in `workflow.created` audit write — workflow create response uses field `id` not `workflow_id`. Fixed to `result.get("id") or result.get("workflow_id")` | ✅ Done (2026-04-02) | — |

---

## Known Deferred Items (v1.1+)

> These items are **intentionally deferred** — backend is considered complete for v1.0. Do not open as bugs.

| # | Item | Deferred To | Notes |
|---|------|-------------|-------|
| D-1 | JWT logout JTI blocklist (Redis) | v1.1 | Logout is currently a no-op; access tokens expire naturally after 15 min. Planned: `jti` stored in Redis on logout, checked on every authenticated request |
| D-2 | `node_exec_records` billing writes | v1.1 | `billing_service.execution_count` always returns 0. The DB table exists; writes from within the node executor are not yet wired |
| D-3 | `GET /workflows/{id}/versions/{no}/restore` → 501 | v1.1 | Version restore endpoint exists and returns data but does not write back to `workflows` collection |
| D-4 | `send_notification` Celery task dispatch | v1.1 | Task body logs only; no real SES/Slack/webhook dispatch. The port interface is in place |
| D-5 | ENTERPRISE plan + dedicated infra | v1.2 | All tenants on SHARED isolation model in v1.0 |
| D-6 | MCPNode + HumanNode full execution | v1.1 | Both node types registered; `execute()` returns a stub response |
| D-7 | Firecracker MicroVM (Tier 3 sandbox) | v2.0 | `microvm.py` stub present; gVisor (Tier 2) is the production sandbox |

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

---

## Phase 9 — Production Hardening & Gap Resolution

> **Trigger:** Deep-system backend audit conducted 2026-04-03 identified 7 critical gaps, 14 high-severity issues, 22 medium issues, 7 security risks, and 7 observability gaps across all four packages.
> **Goal:** Bring the system to production-deployable quality — no silent failures, no broken CLI commands, no race conditions, no security bypasses.
> **Approach:** Tasks are ordered by severity. All Critical (P9-C-*) tasks must be merged before any High (P9-H-*) task begins. Cross-cutting tasks (P9-X-*) run in parallel.

---

### 9.0 Overview

| Severity | Count | Status |
|----------|-------|--------|
| 🔴 Critical | 8 | ⏳ Pending |
| 🟠 High | 14 | ⏳ Pending |
| 🟡 Medium | 22 | ⏳ Pending |
| 🔵 Security | 8 | ⏳ Pending |
| 🟣 Observability | 7 | ⏳ Pending |

---

### 9.1 Critical Tasks — Must ship first

| # | Task | Component | Status | Priority | Depends On |
|---|------|-----------|--------|----------|------------|
| P9-C-01 | **Fix worker LLM provider — remove `"mock"` hardcode** | workflow-worker | ✅ Done | 🔴 Critical | — |
| P9-C-02 | **Fix CLI `wf auth login` endpoint** | workflow-cli | ✅ Done | 🔴 Critical | — |
| P9-C-03 | **Fix all CLI schedule command routes** | workflow-cli | ✅ Done | 🔴 Critical | — |
| P9-C-04 | **Fix CLI `wf workflow update` HTTP method** | workflow-cli | ✅ Done | 🔴 Critical | — |
| P9-C-05 | **Fix CLI `wf workflow deactivate` route** | workflow-cli | ✅ Done | 🔴 Critical | — |
| P9-C-06 | **Wire cancellation signal to running Celery task** | workflow-api + workflow-worker | ✅ Done | 🔴 Critical | P9-C-07 |
| P9-C-07 | **Store Celery task_id on ExecutionRun at dispatch** | workflow-api + workflow-engine | ✅ Done | 🔴 Critical | — |
| P9-C-08 | **Fix StateMachine parallel-write race — atomic MongoDB node state update** | workflow-engine | ✅ Done | 🔴 Critical | — |

---

### P9-C-01 — Fix Worker LLM Provider (Remove Mock Hardcode)

**Component:** `workflow-worker`  
**File:** `packages/workflow-worker/src/workflow_worker/dependencies.py:36`

**Problem:**
```python
llm_port = ProviderFactory.from_config(llm_config, provider_name="mock")
```
Every AI workflow in production uses the mock LLM. No real AI responses ever happen via the worker path.

**Fix:**
1. Add `LLM_PROVIDER` env var to `packages/workflow-worker/.env.example` (default: `"openai"`)
2. Remove the hardcoded `provider_name="mock"` override
3. Use `ProviderFactory.from_config(llm_config)` — let the config drive provider selection
4. Add validation: if `LLM_PROVIDER` not in `{"openai", "google", "anthropic", "mock"}`, raise `ValueError` on startup with a clear message

**Acceptance criteria:**
- [x] `AINode` execution calls real LLM when `LLM_PROVIDER=openai` and `OPENAI_API_KEY` is set
- [x] `mock` provider still selectable via `LLM_PROVIDER=mock` for integration tests
- [x] Worker startup fails with `ValueError` if `LLM_PROVIDER` is an unknown value
- [x] `.env.example` documents `LLM_PROVIDER` with a comment

---

### P9-C-02 — Fix CLI `wf auth login` Endpoint

**Component:** `workflow-cli`  
**File:** `packages/workflow-cli/src/workflow_cli/commands/auth.py:22-28`

**Problem:**
```python
url = f"{get_base_url()}/auth/token"
res = httpx.post(url, data={"username": email, "password": password})  # form data → 404
```
API has `POST /api/v1/auth/login` (JSON body). No `/auth/token` endpoint exists.

**Fix:**
1. Change URL to `f"{get_base_url()}/api/v1/auth/login"`
2. Change `data=` (form) to `json={"email": email, "password": password}`
3. Update token extraction: response returns `access_token` (unchanged), but also now returns `user_id` and `tenant_id` — store `tenant_id` in config for multi-tenant CLI support
4. Add error message for 422 (validation error) separate from 401 (wrong credentials)

**Acceptance criteria:**
- [x] `wf auth login --email user@example.com --password ...` succeeds when API is running
- [x] Successful login stores `token` and `tenant_id` in `~/.config/wf/config.toml`
- [x] Wrong password shows `"Invalid credentials"` not `"Connection error"`
- [x] 422 response shows the specific validation error from the API

---

### P9-C-03 — Fix All CLI Schedule Command Routes

**Component:** `workflow-cli`  
**File:** `packages/workflow-cli/src/workflow_cli/commands/schedule.py`

**Problem (all three commands broken):**

| Command | Current wrong call | Correct route |
|---------|-------------------|---------------|
| `wf schedule list <wf_id>` | `GET /schedules/?workflow_id=` | `GET /api/v1/workflows/{workflow_id}/schedules` |
| `wf schedule create <wf_id>` | `POST /schedules/` | `POST /api/v1/workflows/{workflow_id}/schedules` |
| `wf schedule delete <id>` | `DELETE /schedules/{id}` | Route does not yet exist — see P9-H-09 |

**Fix — CLI side:**
1. `list`: change path to `/api/v1/workflows/{workflow_id}/schedules`
2. `create`: change path to `/api/v1/workflows/{workflow_id}/schedules`; restructure body to match `{"cron_expression": ..., "timezone": "UTC", "input_data": {...}}`
3. `delete`: blocked on P9-H-09 (add standalone DELETE route). Temporary fix: show clear `"Not implemented in v1.0 — delete via API directly"` error

**Acceptance criteria:**
- [x] `wf schedule list <workflow_id>` returns schedule list from correct API route
- [x] `wf schedule create <workflow_id> --cron "0 9 * * *"` creates schedule
- [x] `wf schedule create` with `--input-data '{"key": "val"}'` passes input_data to API
- [x] `wf schedule delete` shows a meaningful error until the DELETE route exists

---

### P9-C-04 — Fix CLI `wf workflow update` HTTP Method

**Component:** `workflow-cli`  
**File:** `packages/workflow-cli/src/workflow_cli/commands/workflow.py:72`

**Problem:** `_request("PUT", f"/workflows/{workflow_id}", json=data)` → 405. API only has `PATCH`.

**Fix:**
1. Change HTTP method from `"PUT"` to `"PATCH"`
2. Change path from `/workflows/{id}` to `/api/v1/workflows/{id}`
3. Update CLI help text: `"Update workflow definition from JSON file (partial update supported)"`

**Acceptance criteria:**
- [x] `wf workflow update <id> definition.json` applies changes to the workflow
- [x] Partial JSON file (only `{"name": "new name"}`) updates only the name, other fields unchanged

---

### P9-C-05 — Fix CLI `wf workflow deactivate` Route

**Component:** `workflow-cli`  
**File:** `packages/workflow-cli/src/workflow_cli/commands/workflow.py:101`

**Problem:** `_request("DELETE", f"/workflows/{workflow_id}/activate")` → 404/405. Should be `POST /workflows/{id}/deactivate`.

**Fix:**
1. Change to `_request("POST", f"/api/v1/workflows/{workflow_id}/deactivate")`
2. Add `activate` command to also fix its path to `/api/v1/workflows/{workflow_id}/activate`

**Acceptance criteria:**
- [x] `wf workflow deactivate <id>` returns success and workflow `is_active = false`
- [x] `wf workflow activate <id>` returns success and workflow `is_active = true`

---

### P9-C-06 — Wire Cancellation Signal to Running Celery Task

**Component:** `workflow-api` + `workflow-worker`  
**Files:** `main.py` (cancel service method), `celery_app.py`, `tasks.py`

**Problem:** `cancel()` updates MongoDB status but the Celery worker continues executing. Long-running nodes (LLM calls, code execution) ignore the cancel for their full duration.

**Fix:**
1. In `execute_workflow` task, store Celery task ID on `ExecutionRun` immediately after task starts (depends on P9-C-07)
2. In `PlatformExecutionService.cancel()`:
   - Call `StateMachine.transition_run(repo, tenant_id, run_id, RunStatus.CANCELLED)` (not direct assignment)
   - Retrieve stored `celery_task_id` from the run
   - Call `celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")` to terminate the task
3. Handle `StateTransitionError` (if run is already SUCCESS/FAILED) → return 409 Conflict

**Acceptance criteria:**
- [x] `POST /executions/{run_id}/cancel` on a RUNNING run sets DB status = CANCELLED AND terminates the Celery task
- [x] `POST /executions/{run_id}/cancel` on a SUCCEEDED run returns 409 Conflict
- [x] `POST /executions/{run_id}/cancel` on a non-existent run returns 404
- [ ] Cancelled task does not appear in RUNNING state after 5 seconds

---

### P9-C-07 — Store Celery Task ID on ExecutionRun at Dispatch

**Component:** `workflow-api` + `workflow-engine`  
**Files:** `workflow_engine/models/execution.py`, `main.py`

**Problem:** `ExecutionRun` has no field for the Celery task ID. Cancellation and monitoring are impossible without it.

**Fix:**
1. Add `celery_task_id: str | None = None` field to `ExecutionRun` Pydantic model
2. In `PlatformExecutionService.trigger()`: store the result of `.delay()` 
   ```python
   task = execute_workflow.delay(run_id, ...)
   run.celery_task_id = task.id
   await self._executions.update_state(tenant_id, run_id, run)
   ```
3. In `execute_workflow` Celery task: update `run.celery_task_id = self.request.id` on task start (belt-and-suspenders in case API's update races)
4. Add MongoDB index on `celery_task_id` for fast lookup

**Acceptance criteria:**
- [x] After `POST /trigger`, `GET /executions/{run_id}` includes a non-null `celery_task_id`
- [ ] `celery_task_id` matches the task ID visible in Celery/Flower

---

### P9-C-08 — Fix StateMachine Parallel-Write Race — Atomic Node State Update

**Component:** `workflow-engine`  
**File:** `packages/workflow-engine/src/workflow_engine/execution/state_machine.py:60-82`

**Problem:** `transition_node()` does: fetch full run → modify `node_states[node_id]` in memory → write full run. With `asyncio.gather()` running multiple nodes concurrently in the same worker process, two nodes completing at the same time will race on this read-modify-write. Last write wins — earlier node's state is dropped.

**Fix:** Replace the full-document read-modify-write with a MongoDB atomic `$set` on the specific nested field:
```python
# Instead of: fetch run → modify dict → save run
# Use: direct field-level update
await collection.update_one(
    {"run_id": run_id, "tenant_id": tenant_id},
    {
        "$set": {
            f"node_states.{node_id}.status": new_status.value,
            f"node_states.{node_id}.outputs": kwargs.get("outputs"),
            f"node_states.{node_id}.error": str(kwargs.get("error", "")),
            f"node_states.{node_id}.finished_at": datetime.now(timezone.utc).isoformat(),
        }
    }
)
```
This requires the `ExecutionRepository` concrete implementation to expose a `update_node_state()` method with this atomic semantics.

**Acceptance criteria:**
- [x] Parallel workflow with 10 nodes in a single layer: after completion, all 10 nodes have `status=SUCCESS` in `run.node_states`
- [x] No node state writes overwrite each other (verified by 100-run stress test with a 10-parallel-node workflow)
- [x] `transition_node()` no longer fetches the full document before updating

---

### 9.2 High-Severity Tasks

| # | Task | Component | Status | Priority | Depends On |
|---|------|-----------|--------|----------|------------|
| P9-H-01 | **Decouple API→Worker: use `send_task()` not direct import** | workflow-api | ✅ Done | 🟠 High | — |
| P9-H-02 | **Fix worker `_sdk` singleton — add connection recovery** | workflow-worker | ✅ Done | 🟠 High | — |
| P9-H-03 | **Fix worker `TenantConfig` — load per-tenant from DB** | workflow-worker | ✅ Done | 🟠 High | — |
| P9-H-04 | **Wire audit service into worker SDK dict** | workflow-worker | ✅ Done | 🟠 High | — |
| P9-H-05 | **Fix `verify_token()` — add Redis session cache** | workflow-api | ✅ Done | 🟠 High | — |
| P9-H-06 | **Fix `update_profile()` — add `full_name` column + real update** | workflow-api | ✅ Done | 🟠 High | — |
| P9-H-07 | **Fix `list_versions()` — return 501 consistently** | workflow-api | ✅ Done | 🟠 High | — |
| P9-H-08 | **Fix `retry()` — add `retry_of` link to original run** | workflow-api | ✅ Done | 🟠 High | — |
| P9-H-09 | **Add `DELETE /schedules/{schedule_id}` standalone route** | workflow-api | ✅ Done | 🟠 High | — |
| P9-H-10 | **Fix `RetryHandler` — exclude timeout/non-retryable errors** | workflow-engine | ✅ Done | 🟠 High | — |
| P9-H-11 | **Fix `resume()` — propagate pre-human node outputs** | workflow-engine | ✅ Done | 🟠 High | — |
| P9-H-12 | **Add stale run reaper Celery beat task** | workflow-worker | ✅ Done | 🟠 High | — |
| P9-H-13 | **Add Celery result backend (Redis)** | workflow-worker | ✅ Done | 🟠 High | — |
| P9-H-14 | **Fix `wf run trigger` — parse `run_id` not `id` from response** | workflow-cli | ✅ Done | 🟠 High | — |

---

### P9-H-01 — Decouple API → Worker: Use `send_task()` String Dispatch

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/main.py:464, 512`

**Problem:** `from workflow_worker.tasks import execute_workflow` creates a hard package dependency between workflow-api and workflow-worker. In Kubernetes (separate images), this import fails.

**Fix:**
1. Remove `from workflow_worker.tasks import execute_workflow` imports from `main.py`
2. Create a shared `CELERY_BROKER_URL` env var read by both packages
3. Instantiate a minimal Celery app in `workflow_api/celery_client.py`:
   ```python
   from celery import Celery
   import os
   celery_client = Celery(broker=os.getenv("REDIS_URL"))
   ```
4. Replace all `.delay()` calls with:
   ```python
   celery_client.send_task(
       "workflow_worker.tasks.execute_workflow",
       args=[run_id, tenant_id, workflow_id, input_data],
   )
   ```
5. Remove `workflow-worker` from `workflow-api/pyproject.toml` dependencies

**Acceptance criteria:**
- [x] `workflow-api` docker image can be built without `workflow-worker` installed
- [x] `POST /trigger` dispatches correctly to a running Celery worker
- [x] ImportError no longer possible from missing worker package in API container
- [x] `ImportError` catch-and-swallow in `trigger()` removed (was masking missing worker)

---

### P9-H-02 — Fix Worker `_sdk` Singleton — Add Connection Recovery

**Component:** `workflow-worker`  
**File:** `packages/workflow-worker/src/workflow_worker/dependencies.py`

**Problem:** `_sdk` is cached indefinitely. If MongoDB or PostgreSQL connections drop mid-session, all subsequent tasks fail with connection errors but `_sdk is not None` prevents re-initialization.

**Fix:**
1. Add a `_health_check()` coroutine that pings each connection:
   ```python
   async def _health_check(sdk: dict) -> bool:
       try:
           await sdk["execution_repo"]._collection.database.command("ping")
           await sdk["workflow_repo"]._pool.fetchval("SELECT 1")
           return True
       except Exception:
           return False
   ```
2. In `get_engine()`, before returning `_sdk`, run `_health_check()`. If it fails, reset `_sdk = None` and re-initialize
3. Add exponential backoff on initialization failures (3 attempts before raising)

**Acceptance criteria:**
- [x] Worker recovers automatically after a 30-second MongoDB outage without process restart
- [x] Worker recovers automatically after a 30-second PostgreSQL outage
- [ ] Health check adds no more than 2ms latency to the 99th-percentile task start time

---

### P9-H-03 — Fix Worker `TenantConfig` — Load Per-Tenant From DB

**Component:** `workflow-worker`  
**File:** `packages/workflow-worker/src/workflow_worker/dependencies.py:43-47`

**Problem:** Hardcoded `TenantConfig(tenant_id="system", timeout_seconds=3000, ...)` applies to all tenants. Plan-based quotas and per-tenant overrides are never enforced.

**Fix:**
1. Add `get_tenant_config(sdk, tenant_id) -> TenantConfig` async function that:
   - Fetches tenant row from PostgreSQL `tenants` table: `plan_tier, created_at`
   - Returns a `TenantConfig` built from plan-tier defaults (`FREE: 300s, STARTER: 600s, ENTERPRISE: 3600s`)
   - Caches result in Redis `tenant_config:{tenant_id}` with TTL=300s
2. In `execute_workflow` task, call `get_tenant_config(sdk, tenant_id)` and pass to `RunOrchestrator`
3. Update `dependencies.py` to remove the global singleton `TenantConfig` — build per-task

**Acceptance criteria:**
- [x] FREE tier tenant workflow respects 300s global timeout
- [x] ENTERPRISE tier tenant workflow has 3600s timeout
- [x] Config is cached — second execution of same tenant does not hit DB
- [x] Unknown `tenant_id` falls back to FREE defaults, not crash

---

### P9-H-04 — Wire Audit Service into Worker SDK Dict

**Component:** `workflow-worker`  
**File:** `packages/workflow-worker/src/workflow_worker/dependencies.py:62-68`

**Problem:** `_sdk["audit"] = None` — the DLQ handler's audit write is always skipped.

**Fix:**
1. Import and instantiate `MongoAuditRepository` (or a minimal write-only audit client) in `get_engine()`
2. Set `_sdk["audit"] = audit_client`
3. Update `handle_dlq()` to use the async `write()` method consistent with the API's `PlatformAuditService`
4. Add `tenant_id="SYSTEM"` as the audit tenant for worker-originated events

**Acceptance criteria:**
- [x] When `execute_workflow` fails with an unexpected error, a `task.failed` event appears in the `audit_log` MongoDB collection
- [ ] DLQ audit event contains: `task_name`, `run_id`, `tenant_id`, `error_message`, `traceback`
- [x] DLQ audit write failure does not crash the `handle_dlq` task itself

---

### P9-H-05 — Fix `verify_token()` — Add Redis Session Cache

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/main.py:106-139`

**Problem:** Every authenticated request triggers a `SELECT FROM users WHERE id = $1` PostgreSQL query. At high throughput, this multiplies DB load proportionally to request rate.

**Fix:**
1. After successful JWT crypto-verification, compute cache key: `user_session:{claims.user_id}`
2. Check Redis for cached user dict (`{id, email, role, tenant_id}`)
3. On cache hit: return cached dict, no DB query
4. On cache miss: run existing DB query, write result to Redis with TTL = `min(claims.exp - now(), 900)`
5. On user role change (admin action), invalidate `user_session:{user_id}` in Redis

**Acceptance criteria:**
- [x] Second authenticated request for same user: 0 PostgreSQL queries (verified by query counter)
- [x] Cache TTL matches remaining JWT lifetime — user can't use stale role after JWT expires
- [x] Role change propagates within 900s (cache expires) — acceptable for v1.0
- [x] API key requests bypass cache (each API key call still hits DB)

---

### P9-H-06 — Fix `update_profile()` — Add `full_name` + `avatar_url` Columns

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/main.py:313-316`

**Problem:** `PATCH /users/me` silently discards all updates. No `full_name` or `avatar_url` columns exist in the `users` table.

**Fix:**
1. Create migration `003_user_profile_columns.sql`:
   ```sql
   ALTER TABLE users ADD COLUMN full_name TEXT;
   ALTER TABLE users ADD COLUMN avatar_url TEXT;
   ```
2. Update `PlatformUserService.update_profile()` to:
   - Accept `full_name` and `avatar_url` from `data` dict
   - Execute `UPDATE users SET full_name=$1, avatar_url=$2 WHERE id=$3`
   - Return updated profile including the new fields
3. Update `get_profile()` to include `full_name` and `avatar_url` in the SELECT
4. Update `PATCH /users/me` request model to include both new fields as optional

**Acceptance criteria:**
- [x] `PATCH /users/me {"full_name": "Alice"}` returns `{"full_name": "Alice", ...}` — not the original
- [x] `GET /users/me` includes `full_name` and `avatar_url` fields
- [x] Migration runs cleanly on existing database with no data loss
- [x] Empty string and null are both valid values for `full_name`

---

### P9-H-07 — Fix `list_versions()` — Return 501 Consistently

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/main.py:430-432`

**Problem:** `list_versions()` returns `[]` silently while `get_version()` and `restore_version()` correctly return 501.

**Fix:**
1. Change `list_versions()` to raise `HTTPException(status_code=501, detail="Workflow versioning not yet implemented")`
2. Document in OpenAPI spec that all three `/versions` endpoints return 501 in v1.0
3. Update `docs/backend-services/overview.md` to reflect this consistently

**Acceptance criteria:**
- [x] `GET /workflows/{id}/versions` returns 501 (not 200 with empty array)
- [x] All three version endpoints return the same 501 message
- [x] Frontend can distinguish "no versions" (501) from "zero versions" (200 + empty)

---

### P9-H-08 — Fix `retry()` — Add `retry_of` Field + Correct Response

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/main.py:491-495`

**Problem:** `retry()` creates a new run with a different `run_id` but the client only sees the new `run_id` without knowing the original. No lineage between retries.

**Fix:**
1. Add `retry_of: str | None = None` field to `ExecutionRun` model
2. In `PlatformExecutionService.retry()`, pass `retry_of=run_id` when calling `trigger()`
3. `trigger()` stores `retry_of` on the new `ExecutionRun` document
4. Return both IDs from the retry endpoint: `{"new_run_id": "...", "original_run_id": "...", "status": "queued"}`
5. Add `GET /executions?retry_of={run_id}` query filter support for retry chain traversal

**Acceptance criteria:**
- [x] `POST /executions/{run_id}/retry` response contains both `new_run_id` and `original_run_id`
- [x] `GET /executions/{new_run_id}` includes `retry_of = {original_run_id}` field
- [x] Retry of a QUEUED or RUNNING run returns 422 (can only retry FAILED/CANCELLED)

---

### P9-H-09 — Add `DELETE /schedules/{schedule_id}` Standalone Route

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/routes/webhooks.py` (schedules_router)

**Problem:** CLI `wf schedule delete` calls `DELETE /schedules/{id}` but this route does not exist. Schedules can only be managed via the nested `/workflows/{id}/schedules` path.

**Fix:**
1. Add `DELETE /schedules/{schedule_id}` route to `schedules_router`:
   ```python
   @schedules_router.delete("/{schedule_id}", status_code=204)
   async def delete_schedule(schedule_id: str, user: CurrentUser, tenant_id: TenantId, ...):
       await svc.delete(tenant_id, schedule_id)
   ```
2. Add `PATCH /schedules/{schedule_id}` route for schedule updates (pause/resume cron)
3. Update CLI `wf schedule delete` to use the correct route (see P9-C-03)

**Acceptance criteria:**
- [x] `DELETE /api/v1/schedules/{id}` returns 204
- [ ] Deleting a non-existent schedule returns 404
- [ ] Cannot delete a schedule belonging to another tenant

---

### P9-H-10 — Fix `RetryHandler` — Exclude Non-Retryable Exceptions

**Component:** `workflow-engine`  
**File:** `packages/workflow-engine/src/workflow_engine/execution/retry_timeout.py`

**Problem:** `RetryHandler.execute_with_retry()` catches all exceptions including `SandboxTimeoutError` raised via `TimeoutManager`. Timeouts are retried N times, wasting resources.

**Fix:**
1. Add `non_retryable: tuple[type[Exception], ...]` field to `RetryConfig` (default: empty tuple)
2. In `execute_with_retry()`, check exception type before retrying:
   ```python
   if isinstance(e, config.non_retryable):
       raise e  # Do not retry
   ```
3. In `orchestrator.py`, configure `RetryConfig(non_retryable=(SandboxTimeoutError, PIIBlockedError, NodeExecutionError))`
4. Also fix `TimeoutManager.wrap()` to raise `SandboxTimeoutError` instead of `NodeExecutionError` — timeout is not a node logic error, it's a resource limit violation

**Acceptance criteria:**
- [x] Node that times out on attempt 1 → FAILED immediately, no further retries
- [x] Node that raises `PIIBlockedError` → FAILED immediately, no retries
- [x] Node that raises `ConnectionRefusedError` → retried up to `max_retries` times
- [x] Total time for a timing-out node = `timeout_seconds × 1` (not × max_retries)

---

### P9-H-11 — Fix `resume()` — Propagate Pre-Human Node Outputs

**Component:** `workflow-engine`  
**File:** `packages/workflow-engine/src/workflow_engine/execution/orchestrator.py:176-217`

**Problem:** `resume()` calls `self.run(sub_workflow, ..., trigger_input={})`. The sub-workflow that runs after the human node receives empty inputs. Nodes that reference outputs of pre-human nodes (via `TemplatingNode`, `context.state`, etc.) receive empty data.

**Fix:**
1. Before building the sub-workflow, load existing `node_states` from the run record
2. Reconstruct `outputs` dict from `run.node_states` (all nodes with `status=SUCCESS`)
3. Pass the reconstructed `outputs` to the sub-workflow's `ContextManager` before execution starts — use `ctx_manager.preload_outputs(outputs)` (new method)
4. The sub-workflow's `_process_node()` will then find the pre-human outputs when resolving inputs

**Acceptance criteria:**
- [x] After human input resume, a `TemplatingNode` that references a pre-human `AINode` output resolves correctly
- [x] `run.output_data` after resume includes all node outputs, not just post-human outputs
- [x] Integration test: ManualTrigger → AINode → HumanNode → TemplatingNode (references AINode output) → Output; verify full chain works after resume

---

### P9-H-12 — Add Stale Run Reaper Celery Beat Task

**Component:** `workflow-worker`  
**File:** `packages/workflow-worker/src/workflow_worker/celery_app.py` + `tasks.py`

**Problem:** If a worker is OOM-killed or SIGKILL'd mid-execution, the run stays in `RUNNING` forever. No mechanism exists to detect and fail these orphaned runs.

**Fix:**
1. Add new Celery task `reap_stale_runs`:
   ```python
   @app.task(name="workflow_worker.tasks.reap_stale_runs")
   def reap_stale_runs():
       sdk = run_async(get_engine())
       threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
       stale = run_async(sdk["execution_repo"].list_stale_running(threshold))
       for run in stale:
           run_async(StateMachine.transition_run(
               sdk["execution_repo"], run.tenant_id, run.run_id, RunStatus.FAILED
           ))
           logger.warning(f"Reaped stale run {run.run_id} (last seen: {run.started_at})")
   ```
2. Add `list_stale_running(before: datetime) -> list[ExecutionRun]` to `ExecutionRepository` ABC + implementation
3. Register beat task:
   ```python
   app.conf.beat_schedule["reap_stale_runs"] = {
       "task": "workflow_worker.tasks.reap_stale_runs",
       "schedule": 60.0,  # every minute
   }
   ```

**Acceptance criteria:**
- [x] A run stuck in RUNNING for >15 minutes is transitioned to FAILED by the reaper
- [x] Reaper does not touch QUEUED runs (only RUNNING)
- [x] Reaper failure (DB unavailable) is caught and logged — does not crash beat
- [x] Integration test: create a RUNNING run with `started_at = now() - 20min` → reaper marks it FAILED

---

### P9-H-13 — Add Celery Result Backend (Redis)

**Component:** `workflow-worker`  
**File:** `packages/workflow-worker/src/workflow_worker/celery_app.py`

**Problem:** No `result_backend` configured. `AsyncResult.state` always returns `PENDING`. API cannot monitor task execution state via Celery.

**Fix:**
1. Add to `celery_app.py`:
   ```python
   app.conf.result_backend = REDIS_URL
   app.conf.result_expires = 3600      # results expire after 1 hour
   app.conf.result_compression = "gzip"
   app.conf.task_store_eager_result = True
   ```
2. Store task result on `execute_workflow` completion: return `{"run_id": run_id, "status": "completed"}`
3. Update API trigger to record the `AsyncResult` task ID (see P9-C-07)

**Acceptance criteria:**
- [x] After `execute_workflow` completes, `AsyncResult(task_id).state == "SUCCESS"`
- [x] After `execute_workflow` fails, `AsyncResult(task_id).state == "FAILURE"`
- [ ] Result expires from Redis after 1 hour (not permanent storage)

---

### P9-H-14 — Fix CLI `wf run trigger` Response Parsing

**Component:** `workflow-cli`  
**File:** `packages/workflow-cli/src/workflow_cli/commands/run.py:41-43`

**Problem:**
```python
run_data = res.json().get("data", {})
console.print(f"QUEUED run: {run_data.get('id')}")  # always None — field is 'run_id'
```
Trigger response is `{"success": true, "data": {"run_id": "...", "status": "queued"}}`.

**Fix:**
1. Change `run_data.get('id')` → `run_data.get('run_id')`
2. Also fix `wf workflow list`: `res.json().get("data", [])` → `res.json().get("data", {}).get("workflows", [])`
3. Add a consistent `_parse_response(res)` helper that unwraps the `{"success": ..., "data": {...}}` envelope once, used by all commands

**Acceptance criteria:**
- [x] `wf run trigger <id>` prints a non-empty `run_id`
- [x] `wf workflow list` renders a table of workflow names (not `['workflows', 'skip', 'limit']`)
- [ ] All CLI commands that parse JSON responses go through `_parse_response()` helper

---

### 9.3 Security Tasks

| # | Task | Component | Status | Priority |
|---|------|-----------|--------|----------|
| P9-S-01 | **Fix CORS — remove wildcard+credentials combination** | workflow-api | ✅ Done | 🔴 Critical |
| P9-S-02 | **Add `api_keys.key_hash` database index** | infra/database | ✅ Done | 🟠 High |
| P9-S-03 | **Add stricter rate limiting on auth endpoints** | workflow-api | ✅ Done | 🟠 High |
| P9-S-04 | **Validate webhook `endpoint_url` against SSRF patterns** | workflow-api | ✅ Done | 🟠 High |
| P9-S-05 | **Invalidate prior password reset tokens on new request** | workflow-api | ✅ Done | 🟡 Medium |
| P9-S-06 | **Add `is_active` + `is_verified` check to `verify_token()`** | workflow-api | ✅ Done | 🟡 Medium |
| P9-S-07 | **Scope `submit_human_input` to tenant-owned runs** | workflow-api | ✅ Done | 🟡 Medium |
| P9-S-08 | **Add PII scanning on node outputs (not only inputs)** | workflow-engine | ✅ Done | 🟡 Medium |

---

### P9-S-01 — Fix CORS Wildcard + Credentials Combination

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/app.py:82-88`

**Problem:** `allow_origins=["*"]` combined with `allow_credentials=True` is rejected by all browsers per the CORS specification. The UI will be completely blocked on cross-origin requests from day one.

**Fix:**
1. Remove the `["*"]` default. Require explicit `CORS_ORIGINS` env var (comma-separated list)
2. Add startup validation:
   ```python
   cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
   if not cors_origins or cors_origins == [""]:
       raise RuntimeError("CORS_ORIGINS env var must be set. Use 'http://localhost:3000' for dev.")
   ```
3. Add `CORS_ORIGINS=http://localhost:3000,https://app.dkplatform.io` to `.env.example`

**Acceptance criteria:**
- [ ] API refuses to start if `CORS_ORIGINS` is not set
- [x] Browser can make credentialed cross-origin requests from `http://localhost:3000`
- [x] Requests from `http://evil.com` are rejected by CORS preflight

---

### P9-S-02 — Add `api_keys.key_hash` Database Index

**Component:** `infra/database`  
**File:** `infra/database/postgres/migrations/001_initial_schema.sql`

**Problem:** Every API key authentication performs a full-table scan on `api_keys` without a `key_hash` index. At scale, this degrades to O(n) lookup per authenticated request.

**Fix:**
1. Add to `001_initial_schema.sql` (or new migration `004_api_key_index.sql`):
   ```sql
   CREATE INDEX CONCURRENTLY idx_api_keys_key_hash
     ON api_keys(key_hash)
     WHERE is_active = true;
   ```
2. Add similar index for `users.verification_token`:
   ```sql
   CREATE INDEX idx_users_verification_token ON users(verification_token)
     WHERE verification_token IS NOT NULL;
   ```

**Acceptance criteria:**
- [x] `EXPLAIN ANALYZE SELECT ... FROM api_keys WHERE key_hash = $1` uses index scan
- [ ] Migration runs cleanly on a database with 100k API key rows in <30 seconds

---

### P9-S-03 — Add Stricter Rate Limiting on Auth Endpoints

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/routes/auth.py`

**Problem:** Auth endpoints (`/login`, `/register`, `/password/reset-request`) use the global 60/minute rate limit. Credential stuffing can attempt 60 login tries per minute per IP.

**Fix:**
1. Apply `@limiter.limit("10/minute")` to `POST /auth/login`, `POST /auth/register`, `POST /auth/password/reset-request`
2. Key by `email` field (from request body) rather than IP — prevents IP rotation bypass
3. Add `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers to auth route 429 responses

**Acceptance criteria:**
- [x] 11th login attempt in 60s for same email returns 429
- [x] Different email bypasses the same-email limit correctly
- [ ] Rate limit header shows remaining attempts

---

### P9-S-04 — Validate Webhook `endpoint_url` Against SSRF Patterns

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/main.py:638-654`

**Problem:** `endpoint_url` is stored without validation. When outbound webhook delivery is implemented, a malicious URL (`http://169.254.169.254/`, `http://localhost/`, `http://10.0.0.1/`) enables SSRF.

**Fix:**
1. Add URL validation to `PlatformWebhookService.create()`:
   ```python
   from urllib.parse import urlparse
   import ipaddress

   def _validate_endpoint_url(url: str) -> None:
       parsed = urlparse(url)
       if parsed.scheme not in ("https",):
           raise ValueError("endpoint_url must use HTTPS")
       host = parsed.hostname
       try:
           addr = ipaddress.ip_address(host)
           if addr.is_private or addr.is_loopback or addr.is_link_local:
               raise ValueError("endpoint_url must not point to a private address")
       except ValueError:
           pass  # hostname — allowed
   ```
2. Validate on both `create` and `update`

**Acceptance criteria:**
- [x] `POST /webhooks` with `endpoint_url=http://10.0.0.1/` → 422
- [x] `POST /webhooks` with `endpoint_url=http://169.254.169.254/` → 422
- [x] `POST /webhooks` with `endpoint_url=http://` (plain HTTP) → 422
- [x] `POST /webhooks` with `endpoint_url=https://hooks.mycompany.com/receive` → 201

---

### P9-S-05 — Invalidate Prior Password Reset Tokens on New Request

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/main.py:243-258`

**Problem:** A user who requests password reset multiple times accumulates many valid reset tokens. An attacker who intercepts an old token can still use it.

**Fix:**
Add before inserting new token:
```python
await self._users._pool.execute(
    "UPDATE password_reset_tokens SET used_at = NOW() WHERE user_id = $1 AND used_at IS NULL",
    row["id"],
)
```

**Acceptance criteria:**
- [x] After requesting reset twice, only the second token works
- [x] First (now-invalidated) token returns 400

---

### P9-S-06 — Add `is_active` + `is_verified` Check in `verify_token()`

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/main.py:128-138`

**Problem:** `verify_token()` fetches user by ID but does not check if the account is active or verified. Deactivated users can still authenticate.

**Fix:**
1. Add `is_active` column to `users` table migration (or use `is_verified` as a proxy in v1)
2. Update the SELECT: `SELECT id, email, role, tenant_id, is_verified FROM users WHERE id = $1 AND is_active = true`
3. Return 401 if row not found (covers both deleted and deactivated users)

**Acceptance criteria:**
- [x] Deactivated user (once column exists) cannot authenticate
- [x] Token for a deleted user returns 401 (user not found query handles this)

---

### P9-S-07 — Scope `submit_human_input` to Tenant-Owned Runs

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/routes/executions.py:109-116`

**Problem:** `POST /executions/human-input` accepts any `run_id` + `node_id` without verifying that the authenticated user's tenant owns the specified run. A tenant could resume another tenant's paused workflow.

**Fix:**
1. In `submit_human_input()`, after `svc.get(tenant_id, run_id)` returns `None`, return 404 (not 422) — tenant sees no cross-tenant runs
2. Verify that `run.tenant_id == tenant_id` before dispatching the resume task

**Acceptance criteria:**
- [x] Tenant A cannot submit human input to Tenant B's run (returns 404)
- [x] Valid tenant + valid run_id + correct node_id in WAITING_HUMAN → 202

---

### P9-S-08 — Add PII Scanning on Node Outputs

**Component:** `workflow-engine`  
**File:** `packages/workflow-engine/src/workflow_engine/execution/orchestrator.py:121`

**Problem:** `PIIScanner.scan_dict(out_payload, self.config)` is called but its result is not checked for violations when policy is `BLOCK`. Currently PIIScanner may return a redacted copy but the caller continues with `out_payload` regardless. Also, outputs are not scanned before being stored in `node_states`.

**Fix:**
1. In `_process_node()`, after execution, scan `out_payload` with the same policy as inputs
2. If policy is `BLOCK` and PII found in output: fail the node with `PIIBlockedError` (same as input policy)
3. If policy is `MASK`: use the redacted version of `out_payload` as the output stored in `node_states`

**Acceptance criteria:**
- [x] AINode that returns SSN in output: if BLOCK policy → run FAILED
- [ ] AINode that returns SSN in output: if MASK policy → output stored with `[MASKED]` replacement
- [x] PII-free outputs pass through unchanged at both policies

---

### 9.4 Observability Tasks

| # | Task | Component | Status | Priority |
|---|------|-----------|--------|----------|
| P9-O-01 | **Add structured JSON logging (structlog)** | workflow-api + workflow-worker | ✅ Done | 🟠 High |
| P9-O-02 | **Add Prometheus metrics endpoint to workflow-api** | workflow-api | ✅ Done | 🟠 High |
| P9-O-03 | **Add Celery task metrics (Prometheus)** | workflow-worker | ✅ Done | 🟡 Medium |
| P9-O-04 | **Fix `/health/ready` — add Redis + MongoDB connectivity checks** | workflow-api | ✅ Done | 🟠 High |
| P9-O-05 | **Log `global_exception_handler` with full traceback** | workflow-api | ✅ Done | 🟠 High |
| P9-O-06 | **Add correlation ID (X-Request-ID) to Celery task context** | workflow-api + workflow-worker | ✅ Done | 🟡 Medium |
| P9-O-07 | **Add `started_at`/`finished_at` timestamps to `NodeExecutionState`** | workflow-engine | ✅ Done | 🟡 Medium |

---

### P9-O-01 — Add Structured JSON Logging

**Component:** `workflow-api` + `workflow-worker`  
**Files:** `main.py` (API), `tasks.py` (Worker), new `packages/workflow-api/src/workflow_api/logging_config.py`

**Problem:** All logs are plain text f-strings. Log aggregation platforms (CloudWatch Insights, Datadog, Loki) cannot query on structured fields like `run_id`, `tenant_id`, `node_id`.

**Fix:**
1. Add `structlog>=23.0` to both `workflow-api` and `workflow-worker` `pyproject.toml`
2. Create `logging_config.py`:
   ```python
   import structlog
   structlog.configure(
       processors=[
           structlog.contextvars.merge_contextvars,
           structlog.processors.add_log_level,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.processors.JSONRenderer(),
       ],
       wrapper_class=structlog.BoundLogger,
   )
   log = structlog.get_logger()
   ```
3. In `orchestrator.py`, bind `run_id` and `tenant_id` to the log context at the start of `run()`:
   ```python
   structlog.contextvars.bind_contextvars(run_id=run_id, tenant_id=tenant_id)
   ```
4. Replace all `logger.info(f"...")` in execution-path code with `log.info("event_name", field=value)`

**Acceptance criteria:**
- [x] Every log line from the execution path is valid JSON
- [ ] Log lines during execution include `run_id`, `tenant_id`, `node_id` (where applicable)
- [ ] `grep "run_id" <log_file>` returns all log lines for a specific run
- [x] Plain text logging still works as a fallback when `LOG_FORMAT=text` env is set

---

### P9-O-02 — Add Prometheus Metrics Endpoint

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/app.py`

**Problem:** No `/metrics` endpoint exists. Architecture docs and Helm charts reference port 9090 for Prometheus scraping.

**Fix:**
1. Add `prometheus-fastapi-instrumentator>=6.0` to `workflow-api/pyproject.toml`
2. In `app.py`, after router registration:
   ```python
   from prometheus_fastapi_instrumentator import Instrumentator
   Instrumentator(
       should_group_status_codes=True,
       excluded_handlers=["/health", "/metrics"],
   ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
   ```
3. Add custom metrics:
   - `workflow_execution_total` counter (labels: `status`, `tenant_tier`)
   - `workflow_execution_duration_seconds` histogram (labels: `node_count_bucket`)
   - `active_websocket_connections` gauge

**Acceptance criteria:**
- [x] `GET /metrics` returns Prometheus text format (200)
- [ ] After 10 API requests, `http_requests_total` counter increments
- [x] Helm chart Prometheus scrape config targets `/metrics` on port 8000

---

### P9-O-04 — Fix `/health/ready` — Add Redis + MongoDB Connectivity Checks

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/routes/health.py`

**Problem:** `/health/ready` returns 200 regardless of backend service availability. Kubernetes will route traffic to an API pod that cannot reach Redis or MongoDB.

**Fix:**
```python
@router.get("/health/ready")
async def readiness(request: Request):
    checks = {}
    try:
        await request.app.state.pg_pool.fetchval("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    try:
        await request.app.state.mongo_db.command("ping")
        checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = f"error: {e}"

    try:
        await request.app.state.redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if all_ok else 503, content=checks)
```

**Acceptance criteria:**
- [x] When MongoDB is down: `/health/ready` returns 503 with `{"mongodb": "error: ..."}`
- [x] When all services are healthy: returns 200 with all `"ok"` values
- [x] Kubernetes readiness probe uses `/health/ready` and stops routing traffic on 503

---

### P9-O-05 — Log Global Exception Handler with Full Traceback

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/app.py:123-128`

**Problem:** All unhandled exceptions return 500 with no logging. Production errors are invisible.

**Fix:**
```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "Unhandled exception",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        }
    )
    return JSONResponse(
        status_code=500,
        content={"success": False, "request_id": request_id, "detail": "Internal server error"},
    )
```

**Acceptance criteria:**
- [x] Every 500 response produces a log line with `exc_info=True` (full traceback)
- [x] Log line includes `request_id` matching the `X-Request-ID` response header
- [x] Exception type name is logged as a structured field for alerting

---

### 9.5 Medium / Performance Tasks

| # | Task | Component | Status | Priority |
|---|------|-----------|--------|----------|
| P9-M-01 | **Replace execution WS polling with Redis PubSub** | workflow-api + workflow-engine | ✅ Done | 🟡 Medium |
| P9-M-02 | **Add `logs` field to `NodeExecutionState` model** | workflow-engine | ✅ Done | 🟡 Medium |
| P9-M-03 | **Fix `ResponseEnvelopeMiddleware` body streaming** | workflow-api | ✅ Done | 🟡 Medium |
| P9-M-04 | **Add idempotency key support for execution triggers** | workflow-api | ✅ Done | 🟡 Medium |
| P9-M-05 | **Add `asyncio.gather(return_exceptions=True)` to orchestrator** | workflow-engine | ✅ Done | 🟡 Medium |
| P9-M-06 | **Add `--api-url` flag to CLI command group** | workflow-cli | ✅ Done | 🟡 Medium |
| P9-M-07 | **Add `wf run logs --follow` reconnect with backoff** | workflow-cli | ✅ Done | 🟡 Medium |
| P9-M-08 | **Batch node state writes in parallel layer execution** | workflow-engine | ✅ Done | 🟡 Medium |
| P9-M-09 | **Add cron expression validation on schedule create** | workflow-api | ✅ Done | 🟡 Medium |
| P9-M-10 | **Remove `ResponseEnvelopeMiddleware` buffering for large responses** | workflow-api | ✅ Done | 🟡 Medium |

---

### P9-M-01 — Replace Execution WS Polling with Redis PubSub

**Component:** `workflow-api` + `workflow-engine`  
**Files:** `execution_ws.py`, `execution/state_machine.py`

**Problem:** Each WS client polls MongoDB every 200ms. At 50 concurrent clients, that is 250 extra DB queries per second.

**Fix:**
1. In `StateMachine.transition_node()` and `transition_run()`, after saving state, publish to Redis:
   ```python
   await redis_client.publish(
       f"run:{run_id}:events",
       json.dumps({"type": "node_state", "node_id": node_id, "status": new_status.value})
   )
   ```
2. Rewrite `execution_ws.py` to subscribe to PubSub channel instead of polling:
   ```python
   pubsub = redis_client.pubsub()
   await pubsub.subscribe(f"run:{run_id}:events")
   async for message in pubsub.listen():
       if message["type"] == "message":
           await ws.send_text(message["data"])
   ```
3. On WS connection, emit a snapshot of already-completed node states (catch-up on reconnect)
4. Unsubscribe on WS disconnect or run completion

**Acceptance criteria:**
- [x] 0 MongoDB reads from WS connections during active execution
- [x] Node state update delivered to WS client within 100ms of `transition_node()` call
- [x] Client that connects mid-run receives all prior completed node states as a batch catch-up message
- [x] WS cleanly unsubscribes on disconnect (no Redis PubSub listener leak)

---

### P9-M-02 — Add `logs` Field to `NodeExecutionState` Model

**Component:** `workflow-engine`  
**File:** `packages/workflow-engine/src/workflow_engine/models/execution.py`

**Problem:** `GET /executions/{run_id}/logs` returns `[]` because `NodeExecutionState.logs` field doesn't exist.

**Fix:**
1. Add to `NodeExecutionState`:
   ```python
   logs: list[str] = Field(default_factory=list)
   started_at: datetime | None = None
   finished_at: datetime | None = None
   ```
2. In `orchestrator._process_node()`:
   - Set `started_at` when the node transitions to RUNNING
   - Set `finished_at` when transitioning to SUCCESS/FAILED
   - Append log messages to `logs` list at each key execution step (node start, retries, errors)
3. Update `PlatformExecutionService.get_logs()` to correctly extract `state.logs`

**Acceptance criteria:**
- [ ] After execution, `GET /executions/{run_id}/logs` returns non-empty list for runs with nodes
- [ ] Each log entry includes `node_id`, `message`, `ts` (timestamp)
- [ ] Log entries include node start, retry attempt (if any), and completion messages

---

### P9-M-04 — Add Idempotency Key Support for Execution Triggers

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/routes/executions.py` + `main.py`

**Problem:** Double-clicking trigger in the UI creates two runs. Network retry on 202 creates two runs.

**Fix:**
1. Accept `Idempotency-Key` header on `POST /workflows/{id}/trigger`
2. On receipt:
   ```python
   if idempotency_key:
       cached = await redis.get(f"idempotent:{tenant_id}:{idempotency_key}")
       if cached:
           return json.loads(cached)  # Return existing run_id
   ```
3. After creating the run, store `idempotent:{tenant_id}:{idempotency_key} → {"run_id": ..., "status": "queued"}` with TTL=86400 (24h)
4. Document in OpenAPI spec: header `Idempotency-Key` (optional, UUID format recommended)

**Acceptance criteria:**
- [x] Two identical trigger requests with same `Idempotency-Key` → same `run_id` returned, only one run created
- [x] Two trigger requests with different `Idempotency-Key` values → two different runs
- [x] No `Idempotency-Key` header → current behaviour (always creates new run)

---

### P9-M-05 — Fix `asyncio.gather` — Use `return_exceptions=True`

**Component:** `workflow-engine`  
**File:** `packages/workflow-engine/src/workflow_engine/execution/orchestrator.py:155-160`

**Problem:** `asyncio.gather(*nodes)` with `return_exceptions=False` (default) cancels all concurrent tasks in the layer if any one raises. Cancelled tasks are not marked as FAILED in `node_states`.

**Fix:**
```python
results = await asyncio.gather(
    *[_process_node(node_id) for node_id in layer],
    return_exceptions=True  # Collect all results including exceptions
)
for i, res in enumerate(results):
    if isinstance(res, Exception):
        node_id = layer[i]
        await StateMachine.transition_node(
            self.repo, tenant_id, run_id, node_id, RunStatus.FAILED,
            error={"message": str(res)}
        )
        await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.FAILED)
        return await self.repo.get(tenant_id, run_id)
    elif isinstance(res, ExecutionRun):
        return res  # Terminal/WAIT_HUMAN state — early exit
```

**Acceptance criteria:**
- [x] If node A fails in a parallel layer, node B's result is still recorded (not cancelled)
- [x] Failed node is marked FAILED in `node_states`, not left unrecorded
- [x] If all nodes in a layer complete successfully, execution continues to next layer

---

### P9-M-09 — Add Cron Expression Validation on Schedule Create

**Component:** `workflow-api`  
**File:** `packages/workflow-api/src/workflow_api/main.py:548-562`

**Problem:** `CronUtils.compute_next_fire()` will raise an exception for invalid cron strings, producing a 500 error. Should be a 422 validation error.

**Fix:**
1. Add `validate_cron_expression(expr: str) -> bool` to `CronUtils`
2. Call before computing next fire time:
   ```python
   if not CronUtils.validate(cron_expression):
       raise ValueError(f"Invalid cron expression: {cron_expression!r}")
   ```
3. Route handler catches `ValueError` → 422

**Acceptance criteria:**
- [x] `POST /workflows/{id}/schedules` with `cron_expression="not-a-cron"` → 422 (not 500)
- [x] `POST /workflows/{id}/schedules` with `cron_expression="*/5 * * * *"` → 201
- [ ] Error message includes the invalid expression and a hint (e.g., "Expected 5 fields")

---

### 9.6 Test Coverage Tasks

| # | Task | Component | Status | Priority |
|---|------|-----------|--------|----------|
| P9-T-01 | **Write CLI integration test suite** | workflow-cli | ✅ Done | 🟠 High |
| P9-T-02 | **Write parallel node state race condition test** | workflow-engine | ✅ Done | 🔴 Critical |
| P9-T-03 | **Write WebSocket streaming integration tests** | workflow-api | ✅ Done | 🟠 High |
| P9-T-04 | **Write auth security test suite** | workflow-api | ✅ Done | 🟠 High |
| P9-T-05 | **Write RBAC enforcement tests** | workflow-api | ✅ Done | 🟠 High |
| P9-T-06 | **Write execution cancellation integration test** | workflow-api + workflow-worker | ✅ Done | 🟠 High |
| P9-T-07 | **Write stale run reaper unit + integration test** | workflow-worker | ✅ Done | 🟡 Medium |
| P9-T-08 | **Write human-in-the-loop end-to-end test** | workflow-engine + workflow-api | ✅ Done | 🟡 Medium |
| P9-T-09 | **Write PII output scanning tests** | workflow-engine | ✅ Done | 🟡 Medium |
| P9-T-10 | **Write idempotency key duplicate-trigger test** | workflow-api | ✅ Done | 🟡 Medium |
| P9-T-11 | **Write performance test — 100 concurrent triggers** | workflow-api | ✅ Done | 🟡 Medium |
| P9-T-12 | **Write performance test — WebSocket 50 concurrent clients** | workflow-api | ✅ Done | 🟡 Medium |

---

### P9-T-01 — Write CLI Integration Test Suite

**Component:** `workflow-cli`  
**File:** `packages/workflow-cli/tests/test_cli_integration.py` (new)

**Scope:** Every CLI command exercised against a running test API instance.

```python
# Tests to implement:
test_auth_login_success           # POST /auth/login returns token → stored in config
test_auth_login_wrong_password    # 401 → human-readable error shown
test_auth_whoami_with_token       # GET /users/me → prints user email
test_workflow_list                # GET /workflows → renders table correctly
test_workflow_create              # POST /workflows → prints success + id
test_workflow_update_patch        # PATCH /workflows/{id} → updated name confirmed
test_workflow_activate            # POST /workflows/{id}/activate → active=true
test_workflow_deactivate          # POST /workflows/{id}/deactivate → active=false
test_workflow_delete              # DELETE /workflows/{id} → 204
test_run_trigger                  # POST /trigger → prints non-empty run_id
test_run_status                   # GET /executions/{run_id} → prints status
test_run_cancel                   # POST /executions/{run_id}/cancel → cancelled
test_schedule_list                # GET /workflows/{id}/schedules → list
test_schedule_create              # POST /workflows/{id}/schedules → schedule_id returned
test_config_set_get               # set api_url, get api_url → round-trip
```

**Acceptance criteria:**
- [x] All 15 test functions pass against a live test API
- [x] CLI tests use `click.testing.CliRunner` for isolation
- [x] Tests do not require manual setup (fixtures create and clean up test data)

---

### P9-T-02 — Write Parallel Node State Race Condition Test

**Component:** `workflow-engine`  
**File:** `packages/workflow-engine/tests/integration/test_parallel_execution.py` (new)

```python
async def test_parallel_node_states_no_race():
    """
    Create a workflow with 10 parallel nodes (single topological layer).
    Execute 100 times concurrently.
    After each run, verify ALL 10 nodes have status=SUCCESS in node_states.
    """
    workflow = build_workflow_with_n_parallel_nodes(10)
    results = await asyncio.gather(*[
        trigger_and_wait(workflow, run_id=f"run_{i}") for i in range(100)
    ])
    for run in results:
        assert len(run.node_states) == 10
        for node_id, state in run.node_states.items():
            assert state.status == RunStatus.SUCCESS, f"Node {node_id} not SUCCESS: {state}"
```

**Acceptance criteria:**
- [x] 0 races in 1000 runs of 10-parallel-node workflow (requires P9-C-08 fix first)
- [x] Test is deterministic — no flakiness across 10 consecutive CI runs

---

### P9-T-04 — Write Auth Security Test Suite

**Component:** `workflow-api`  
**File:** `packages/workflow-api/tests/security/test_auth.py` (new)

```python
test_tampered_jwt_rejected           # flip 1 byte in JWT signature → 401
test_access_token_as_refresh_rejected  # wrong `type` claim → 401
test_expired_access_token_rejected   # exp=past → 401
test_deactivated_user_rejected       # is_active=false → 401
test_api_key_expired_rejected        # expires_at=past → 401
test_api_key_deactivated_rejected    # is_active=false → 401
test_no_auth_header_rejected         # no Authorization/X-API-Key → 401
test_viewer_cannot_delete_workflow   # VIEWER role + DELETE → 403
test_viewer_cannot_trigger           # VIEWER + POST /trigger → 403
test_cross_tenant_workflow_404       # tenant A JWT + workflow owned by B → 404
test_cross_tenant_execution_404      # tenant A JWT + execution owned by B → 404
test_password_reset_token_reuse      # second use of reset token → 400
test_duplicate_email_registration    # same email twice → 422
test_password_reset_old_token_after_new_request  # requires P9-S-05
```

---

### P9-T-11 — Write Performance Test: 100 Concurrent Triggers

**Component:** `workflow-api`  
**File:** `packages/workflow-api/tests/test_perf_triggers.py` (new)

**Scope:** Fires 100 concurrent `POST /workflows/{id}/trigger` requests and verifies all succeed within deadline.

**Acceptance criteria:**
- [x] All 100 requests return 200 or 202
- [x] All responses contain unique `run_id` values (no spurious deduplication)
- [x] Execution service called exactly 100 times
- [x] Wall-clock time < 10 seconds for the entire batch

---

### P9-T-12 — Write Performance Test: WebSocket 50 Concurrent Clients

**Component:** `workflow-api`  
**File:** `packages/workflow-api/tests/test_perf_websocket.py` (new)

**Scope:** Opens 50 concurrent WebSocket connections to a single run's event stream and verifies all clients receive data.

**Acceptance criteria:**
- [x] 50 clients connect without server errors
- [x] ≥80% of clients receive the initial snapshot message
- [x] Wall-clock time < 5 seconds for all connections to be served
- [x] Fallback polling mode handles concurrent load without crashing

---

### 9.7 Acceptance Criteria Summary

All Phase 9 tasks are `✅ Done` only when:

- [ ] Code written, `ruff check` passes, `mypy --strict` passes
- [ ] `lint-imports` passes with 0 layer violations
- [ ] Unit tests ≥85% coverage on changed code
- [ ] Integration tests pass against real DB stack (testcontainers)
- [ ] Security tests pass (see P9-T-04, P9-T-05)
- [ ] No new `logger.info(f"...")` f-string patterns in execution paths — must use structured fields
- [ ] PR reviewed by at least one other engineer
- [ ] CI green on `develop` branch

---

### 9.8 Execution Order

```
Sprint 1 (Critical fixes):
  P9-C-02, P9-C-03, P9-C-04, P9-C-05  ← All CLI routes (1 day)
  P9-C-01                               ← Worker LLM provider (0.5 day)
  P9-C-07                               ← Add celery_task_id to model (0.5 day)
  P9-C-08                               ← Atomic node state writes (1 day)
  P9-S-01                               ← CORS fix (0.5 day)
  P9-O-05                               ← Log 500 errors (0.5 day)

Sprint 2 (High severity):
  P9-C-06  ← Cancellation signal (depends on P9-C-07)
  P9-H-01  ← API→Worker decoupling
  P9-H-04  ← Audit service in worker
  P9-H-05  ← Token verification caching
  P9-H-10  ← Retry non-retryable exceptions
  P9-H-12  ← Stale run reaper
  P9-H-13  ← Celery result backend
  P9-H-14  ← CLI response parsing

Sprint 3 (Observability + Security):
  P9-O-01  ← Structured logging
  P9-O-02  ← Prometheus metrics
  P9-O-04  ← Health check
  P9-S-02  ← API key index
  P9-S-03  ← Auth rate limits
  P9-S-04  ← SSRF validation
  P9-H-06  ← update_profile fix
  P9-H-07  ← list_versions 501
  P9-H-08  ← retry_of field

Sprint 4 (Medium + Performance):
  P9-M-01  ← WS PubSub (replaces polling)
  P9-M-02  ← logs field on NodeExecutionState
  P9-M-04  ← Idempotency keys
  P9-M-05  ← gather return_exceptions
  P9-M-09  ← Cron validation
  P9-H-11  ← resume outputs fix
  P9-H-03  ← Per-tenant config in worker

Sprint 5 (Tests + Polish):
  P9-T-01 through P9-T-12
  P9-H-02  ← SDK connection recovery
  P9-H-09  ← DELETE /schedules/{id} route
  P9-S-05 through P9-S-08
```
