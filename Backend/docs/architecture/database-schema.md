# Database Schema Reference
## DK Platform — PostgreSQL + MongoDB

**Generated:** 2026-04-07 (updated: 2026-04-07)  
**Sources:** `infra/database/postgres/migrations/`, `packages/workflow-engine/src/workflow_engine/storage/`, `packages/workflow-engine/src/workflow_engine/models/`

---

## Overview

| Database | Purpose | Collections / Tables |
|---|---|---|
| **PostgreSQL** | Auth, billing, tenants, semantic cache | 11 tables |
| **MongoDB** | Workflows, executions, schedules, chat sessions, audit log | 5 collections |
| **Redis** | PubSub events, tenant config cache, workflow state, rate limiting | 5 key patterns |

---

## Part 1 — PostgreSQL

> Applied via Alembic: `make migrate`  
> Migrations: `001_initial_schema.sql`, `002_webhooks.sql`, `003_performance_indexes.sql`, `004_pii_disabled.sql`  
> Alembic wrappers: `0001` → `0002` → `0003` → `0004` (all tracked in `alembic_version`)  
> Extensions required: `uuid-ossp`, `pgcrypto`, `vector` (pgvector)

### ENUM types

| Type | Values |
|---|---|
| `plan_tier` | `FREE`, `STARTER`, `PRO`, `ENTERPRISE`, `DEDICATED` |
| `isolation_model` | `SHARED`, `DEDICATED` |
| `user_role` | `OWNER`, `EDITOR`, `VIEWER` |
| `pii_policy` | `DISABLED`, `SCAN_WARN`, `SCAN_MASK`, `SCAN_BLOCK` |

> `DISABLED` was added by migration `004_pii_disabled.sql` — now matches `PIIPolicy` in `models/tenant.py`.

---

### Table: `tenants`

Central registry for every tenant on the platform. One row per organisation.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Primary key |
| `name` | `TEXT` | NO | — | Human-readable tenant name |
| `slug` | `TEXT` | NO | — | URL-safe unique identifier (e.g. `acme-corp`) |
| `plan_tier` | `plan_tier` | NO | `'FREE'` | Subscription tier controlling quotas and features |
| `isolation_model` | `isolation_model` | NO | `'SHARED'` | `SHARED` = shared infra; `DEDICATED` = own cluster |
| `home_region` | `TEXT` | NO | `'us-east-1'` | Primary region for data residency (`us-east-1`, `eu-west-1`, `ap-southeast-1`) |
| `monthly_exec_quota` | `INTEGER` | YES | `NULL` | Max workflow executions per month (NULL = unlimited for ENTERPRISE) |
| `max_concurrent_runs` | `INTEGER` | NO | `2` | Max simultaneous runs for this tenant |
| `max_nodes_per_workflow` | `INTEGER` | NO | `10` | Node count ceiling per workflow definition |
| `pii_policy` | `pii_policy` | NO | `'SCAN_MASK'` | Default PII enforcement policy for all runs |
| `retention_days` | `INTEGER` | NO | `30` | How long execution data is retained before purge |
| `gdpr_dpa_accepted_at` | `TIMESTAMPTZ` | YES | `NULL` | When the GDPR Data Processing Agreement was accepted |
| `gdpr_dpa_accepted_ip` | `INET` | YES | `NULL` | IP address from which DPA was accepted |
| `dedicated_mongodb_secret_arn` | `TEXT` | YES | `NULL` | AWS Secrets Manager ARN for dedicated MongoDB URL (ENTERPRISE only) |
| `dedicated_redis_secret_arn` | `TEXT` | YES | `NULL` | AWS Secrets Manager ARN for dedicated Redis URL (ENTERPRISE only) |
| `dedicated_s3_bucket` | `TEXT` | YES | `NULL` | Dedicated S3 bucket name (ENTERPRISE only) |
| `dedicated_k8s_namespace` | `TEXT` | YES | `NULL` | Dedicated K8s namespace (ENTERPRISE only) |
| `billing_email` | `TEXT` | YES | `NULL` | Email address for invoices |
| `stripe_customer_id` | `TEXT` | YES | `NULL` | Stripe customer ID for billing integration |
| `is_active` | `BOOLEAN` | NO | `TRUE` | Soft-disable a tenant without deleting data |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Auto-updated on every `UPDATE` via trigger |

**Indexes:**
- `idx_tenants_slug` — `(slug)` — unique tenant lookup by slug
- `idx_tenants_plan_tier` — `(plan_tier)` — filter by billing tier
- `idx_tenants_home_region` — `(home_region)` — region-based routing

---

### Table: `users`

User accounts within a tenant. Each user belongs to exactly one tenant.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Primary key |
| `tenant_id` | `UUID` | NO | — | FK → `tenants.id` ON DELETE CASCADE |
| `email` | `TEXT` | NO | — | Email address (unique per tenant) |
| `password_hash` | `TEXT` | YES | `NULL` | bcrypt hash of password; NULL for OAuth-only users |
| `role` | `user_role` | NO | `'EDITOR'` | `OWNER`, `EDITOR`, or `VIEWER` — controls RBAC permissions |
| `is_verified` | `BOOLEAN` | NO | `FALSE` | Whether email has been verified via link |
| `verification_token` | `TEXT` | YES | `NULL` | One-time token sent in verification email |
| `verification_expires_at` | `TIMESTAMPTZ` | YES | `NULL` | Expiry for the verification token |
| `mfa_enabled` | `BOOLEAN` | NO | `FALSE` | Whether TOTP MFA is active for this user |
| `mfa_secret` | `TEXT` | YES | `NULL` | Encrypted TOTP secret (AES-256 via pgcrypto) |
| `mfa_backup_codes` | `TEXT[]` | YES | `NULL` | Array of hashed one-time backup codes |
| `google_id` | `TEXT` | YES | `NULL` | Google OAuth subject ID |
| `github_id` | `TEXT` | YES | `NULL` | GitHub OAuth subject ID |
| `microsoft_id` | `TEXT` | YES | `NULL` | Microsoft OAuth subject ID |
| `sso_provider` | `TEXT` | YES | `NULL` | SAML/OIDC provider name for enterprise SSO |
| `sso_subject` | `TEXT` | YES | `NULL` | Provider's unique user identifier for SSO |
| `last_login_at` | `TIMESTAMPTZ` | YES | `NULL` | Timestamp of most recent successful login |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Account creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Auto-updated on every `UPDATE` via trigger |

**Indexes:**
- `idx_users_email_tenant` — `UNIQUE (email, tenant_id)` — prevents duplicate emails within tenant
- `idx_users_google_id` — `UNIQUE (google_id)` WHERE NOT NULL — fast OAuth lookup
- `idx_users_github_id` — `UNIQUE (github_id)` WHERE NOT NULL
- `idx_users_microsoft_id` — `UNIQUE (microsoft_id)` WHERE NOT NULL
- `idx_users_tenant_id` — `(tenant_id)` — list all users in a tenant
- `idx_users_verification_token` — `(verification_token)` WHERE NOT NULL — email verification flow
- `idx_users_reset_token` — `(reset_token)` WHERE NOT NULL — password reset flow (migration 003)

---

### Table: `api_keys`

Long-lived API keys for programmatic access (format: `wfk_...`).

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Primary key |
| `tenant_id` | `UUID` | NO | — | FK → `tenants.id` ON DELETE CASCADE |
| `user_id` | `UUID` | NO | — | FK → `users.id` ON DELETE CASCADE |
| `name` | `TEXT` | NO | — | Human-readable label for the key |
| `key_prefix` | `TEXT` | NO | — | First 8 characters for display (e.g. `wfk_abc1`) — never the full key |
| `key_hash` | `TEXT` | NO | — | SHA-256 hash of the full key — used for lookup |
| `scopes` | `TEXT[]` | NO | `'{}'` | Permission scopes (e.g. `['workflows:read', 'executions:write']`) |
| `expires_at` | `TIMESTAMPTZ` | YES | `NULL` | Optional expiry; NULL = never expires |
| `last_used_at` | `TIMESTAMPTZ` | YES | `NULL` | Updated on each successful authentication |
| `is_active` | `BOOLEAN` | NO | `TRUE` | Revoke a key without deleting it |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Creation timestamp |

**Indexes:**
- `idx_api_keys_hash` — `UNIQUE (key_hash)` WHERE active — fast O(1) auth lookup
- `idx_api_keys_user_id` — `(user_id)`
- `idx_api_keys_tenant_id` — `(tenant_id)`
- `idx_api_keys_key_hash` (migration 003) — `CONCURRENTLY (key_hash)` WHERE active

---

### Table: `refresh_tokens`

Short-lived rotation-based refresh tokens. Each login issues one; rotating issues a new one and revokes the old.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Primary key |
| `user_id` | `UUID` | NO | — | FK → `users.id` ON DELETE CASCADE |
| `tenant_id` | `UUID` | NO | — | FK → `tenants.id` ON DELETE CASCADE |
| `token_hash` | `TEXT` | NO | — | SHA-256 of the opaque token string sent to the client |
| `expires_at` | `TIMESTAMPTZ` | NO | — | Hard expiry (default 7 days from issue) |
| `is_revoked` | `BOOLEAN` | NO | `FALSE` | Set TRUE after rotation or logout |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Issue timestamp |

**Indexes:**
- `idx_refresh_tokens_hash` — `UNIQUE (token_hash)` WHERE NOT revoked — fast token exchange
- `idx_refresh_tokens_user_id` — `(user_id)` — revoke all tokens for a user

---

### Table: `oauth_tokens`

OAuth 2.0 access/refresh tokens for third-party connectors (Slack, GitHub, Salesforce, etc.). Tokens are encrypted at rest via pgcrypto.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Primary key |
| `tenant_id` | `UUID` | NO | — | FK → `tenants.id` ON DELETE CASCADE |
| `user_id` | `UUID` | NO | — | FK → `users.id` ON DELETE CASCADE |
| `connector_id` | `TEXT` | NO | — | Connector identifier: `slack`, `github`, `salesforce`, etc. |
| `provider_user_id` | `TEXT` | YES | `NULL` | The user's ID in the external system |
| `access_token` | `TEXT` | NO | — | Encrypted access token (AES-256 via pgcrypto) |
| `refresh_token` | `TEXT` | YES | `NULL` | Encrypted refresh token (nullable for connectors without refresh) |
| `token_type` | `TEXT` | NO | `'Bearer'` | Token type (always `Bearer` in current connectors) |
| `scopes` | `TEXT[]` | YES | `NULL` | Granted OAuth scopes |
| `expires_at` | `TIMESTAMPTZ` | YES | `NULL` | Access token expiry; NULL = long-lived token |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Issue timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Auto-updated on token refresh via trigger |

**Indexes:**
- `idx_oauth_tokens_tenant_connector` — `UNIQUE (tenant_id, connector_id, user_id)` — one token set per user per connector per tenant
- `idx_oauth_tokens_expires` — `(expires_at)` WHERE refresh_token IS NOT NULL — background refresh job

---

### Table: `llm_cost_records` _(range-partitioned by quarter)_

Per-LLM-call billing records. Each AI node execution inserts one row. Partitioned by `created_at` into quarterly child tables to keep query performance fast as data grows.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Partition key (composite PK with `created_at`) |
| `tenant_id` | `UUID` | NO | — | FK → `tenants.id` |
| `run_id` | `TEXT` | NO | — | Execution run ID that triggered this LLM call |
| `node_id` | `TEXT` | NO | — | Node ID within the workflow |
| `model` | `TEXT` | NO | — | Model identifier (e.g. `gemini-1.5-flash`, `claude-haiku-3-5`) |
| `input_tokens` | `INTEGER` | NO | `0` | Number of prompt tokens consumed |
| `output_tokens` | `INTEGER` | NO | `0` | Number of completion tokens generated |
| `cost_usd` | `NUMERIC(12,8)` | NO | `0` | Computed cost in USD |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Partition key — timestamp of the LLM call |

**Partitions:** Quarterly from 2024-Q1 → 2026-Q4 (12 partitions). Add new partitions before each quarter starts.

**Indexes:**
- `idx_llm_costs_tenant_date` — `(tenant_id, created_at DESC)` — billing dashboard queries
- `idx_llm_costs_run_id` — `(run_id)` — per-run cost breakdown

---

### Table: `node_exec_records` _(range-partitioned by quarter)_

Per-node execution records for compute billing and audit. Each node execution inserts one row.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Partition key (composite PK with `created_at`) |
| `tenant_id` | `UUID` | NO | — | FK → `tenants.id` |
| `run_id` | `TEXT` | NO | — | Execution run ID |
| `node_id` | `TEXT` | NO | — | Node ID within the workflow |
| `node_type` | `TEXT` | NO | — | Node type string (e.g. `PromptNode`, `CodeExecutionNode`) |
| `isolation_tier` | `SMALLINT` | NO | `0` | Sandbox tier: 0=in-process, 1=RestrictedPython, 2=gVisor, 3=Firecracker |
| `compute_seconds` | `NUMERIC(8,3)` | NO | `0` | Wall-clock execution time in seconds |
| `output_bytes` | `INTEGER` | NO | `0` | Size of node output payload in bytes |
| `s3_spilled` | `BOOLEAN` | NO | `FALSE` | Whether output was spilled to S3 (exceeded inline threshold) |
| `status` | `TEXT` | NO | — | Final node status: `SUCCESS`, `FAILED`, `CANCELLED` |
| `node_cost_usd` | `NUMERIC(12,8)` | NO | `0` | Per-node execution charge |
| `compute_cost_usd` | `NUMERIC(12,8)` | NO | `0` | Compute time charge |
| `storage_cost_usd` | `NUMERIC(12,8)` | NO | `0` | S3 storage charge for spilled outputs |
| `started_at` | `TIMESTAMPTZ` | NO | — | Node execution start time |
| `ended_at` | `TIMESTAMPTZ` | YES | `NULL` | Node execution end time (NULL if still running) |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Partition key |

**Partitions:** Quarterly from 2025-Q1 → 2026-Q4 (8 partitions).

**Indexes:**
- `idx_node_exec_tenant_date` — `(tenant_id, created_at DESC)`
- `idx_node_exec_run_id` — `(run_id)`

---

### Table: `tenant_usage_summary`

Hourly pre-aggregated billing totals per tenant. Written by a background aggregation job. Used for fast dashboard queries and quota enforcement.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `tenant_id` | `UUID` | NO | — | FK → `tenants.id` ON DELETE CASCADE. Composite PK with `period_start` |
| `period_start` | `TIMESTAMPTZ` | NO | — | Hour boundary (truncated to hour, e.g. `2026-04-07 14:00:00`) |
| `period_end` | `TIMESTAMPTZ` | NO | — | End of the hour |
| `execution_count` | `INTEGER` | NO | `0` | Number of workflow runs started in this period |
| `node_exec_count` | `INTEGER` | NO | `0` | Total nodes executed across all runs |
| `total_input_tokens` | `BIGINT` | NO | `0` | Sum of LLM input tokens |
| `total_output_tokens` | `BIGINT` | NO | `0` | Sum of LLM output tokens |
| `total_compute_secs` | `NUMERIC(12,3)` | NO | `0` | Total CPU/compute seconds across all nodes |
| `total_cost_usd` | `NUMERIC(14,6)` | NO | `0` | Total billed amount for the period |

**Indexes:**
- `idx_usage_summary_tenant_period` — `(tenant_id, period_start DESC)` — billing dashboard

---

### Table: `semantic_cache`

pgvector-backed LLM response deduplication. Stores embeddings of prompts to find semantically equivalent queries and return cached responses, reducing API costs.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Primary key |
| `tenant_id` | `UUID` | NO | — | FK → `tenants.id` ON DELETE CASCADE. Scopes cache per tenant |
| `model` | `TEXT` | NO | — | LLM model identifier used for the original call |
| `prompt_hash` | `TEXT` | NO | — | SHA-256 of the exact prompt — for deterministic exact-match lookup |
| `embedding` | `vector(1536)` | YES | `NULL` | 1536-dim float vector for cosine similarity search |
| `response` | `TEXT` | NO | — | Cached LLM response text |
| `input_tokens` | `INTEGER` | NO | `0` | Token count of the original prompt (for cost attribution) |
| `output_tokens` | `INTEGER` | NO | `0` | Token count of the cached response |
| `hit_count` | `INTEGER` | NO | `0` | Number of times this entry has been served from cache |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | When the entry was first cached |
| `last_hit_at` | `TIMESTAMPTZ` | YES | `NULL` | Most recent cache hit timestamp |

**Indexes:**
- `idx_semantic_cache_hash` — `(tenant_id, model, prompt_hash)` — fast exact-match lookup
- `idx_semantic_cache_embedding` — `IVFFlat (embedding vector_cosine_ops)` with 100 lists — approximate nearest-neighbor similarity search

---

### Table: `password_reset_tokens`

Single-use, time-limited tokens for the forgot-password flow. Always the same response whether or not the email exists (prevents enumeration).

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Primary key |
| `user_id` | `UUID` | NO | — | FK → `users.id` ON DELETE CASCADE |
| `token_hash` | `TEXT` | NO | — | SHA-256 of the token sent in the email link |
| `expires_at` | `TIMESTAMPTZ` | NO | — | 24-hour TTL from issue time |
| `used_at` | `TIMESTAMPTZ` | YES | `NULL` | Set when the token is redeemed; prevents reuse |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Issue timestamp |

**Indexes:**
- `idx_pwd_reset_hash` — `UNIQUE (token_hash)` WHERE used_at IS NULL — fast lookup, ignores used tokens

---

### Table: `webhooks`

Inbound webhook registrations. Each row represents an external system's endpoint that can trigger a workflow.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Primary key |
| `tenant_id` | `UUID` | NO | — | FK → `tenants.id` ON DELETE CASCADE |
| `workflow_id` | `TEXT` | NO | — | MongoDB workflow ID to trigger on inbound event |
| `name` | `TEXT` | NO | — | Human-readable label |
| `events` | `TEXT[]` | NO | `'{"execution.completed"}'` | Event types this webhook listens for |
| `webhook_secret` | `TEXT` | YES | `NULL` | Plaintext HMAC signing secret (shown once to user) |
| `endpoint_url` | `TEXT` | YES | `NULL` | Outbound delivery URL for future push notifications |
| `active` | `BOOLEAN` | NO | `TRUE` | Soft-disable without deleting |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Auto-updated via trigger |

**Indexes:**
- `idx_webhooks_tenant_id` — `(tenant_id)` WHERE active
- `idx_webhooks_workflow_id` — `(workflow_id)` WHERE active

---

### Table: `webhook_deliveries`

Audit log of every inbound event received and every outbound delivery attempt.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid_generate_v4()` | Primary key |
| `webhook_id` | `UUID` | NO | — | FK → `webhooks.id` ON DELETE CASCADE |
| `tenant_id` | `UUID` | NO | — | Denormalised for fast per-tenant queries |
| `workflow_id` | `TEXT` | NO | — | Denormalised for tracing which workflow was triggered |
| `event_type` | `TEXT` | NO | `'inbound'` | `inbound` for received triggers; `execution.completed` etc. for outbound |
| `payload` | `JSONB` | NO | `'{}'` | Full request body of the inbound event or outbound payload |
| `response_status` | `INTEGER` | YES | `NULL` | HTTP status code of outbound delivery attempt; NULL for inbound |
| `delivered_at` | `TIMESTAMPTZ` | NO | `NOW()` | Delivery timestamp |

**Indexes:**
- `idx_webhook_deliveries_webhook_id` — `(webhook_id)`
- `idx_webhook_deliveries_tenant_date` — `(tenant_id, delivered_at DESC)`

---

### Triggers

| Trigger | Table | Event | Action |
|---|---|---|---|
| `update_tenants_updated_at` | `tenants` | BEFORE UPDATE | Sets `updated_at = NOW()` |
| `update_users_updated_at` | `users` | BEFORE UPDATE | Sets `updated_at = NOW()` |
| `update_oauth_tokens_updated_at` | `oauth_tokens` | BEFORE UPDATE | Sets `updated_at = NOW()` |
| `update_webhooks_updated_at` | `webhooks` | BEFORE UPDATE | Sets `updated_at = NOW()` |

---

## Part 2 — MongoDB

> Database name: parsed from `MONGODB_URL` DSN; defaults to `dk_platform`  
> Client: Motor async (`AsyncIOMotorClient`)  
> All collections enforce tenant isolation via `{ "tenant_id": ... }` on every query.

---

### Collection: `workflow_definitions`

Stores `WorkflowDefinition` documents — the full workflow graph including all nodes, edges, and UI metadata.

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Auto-generated MongoDB primary key (stripped before returning to app) |
| `id` | String | Application-level workflow ID (e.g. `wf_abc123`) |
| `tenant_id` | String | Tenant isolation key — injected on every write |
| `name` | String | Human-readable workflow name (default: `"Untitled Workflow"`) |
| `description` | String \| null | Optional description |
| `nodes` | Object | Map of `node_id → NodeDefinition`. Each node has: `id`, `type` (e.g. `PromptNode`), `config` (object), `position` (`{x, y}`) |
| `edges` | Array | List of `EdgeDefinition`. Each edge has: `id`, `source_node`, `target_node`, `source_port` (default `"default"`), `target_port` (default `"default"`) |
| `ui_metadata` | Object | Canvas layout state: `layout`, `version`, `viewport` (`{x, y, zoom}`), `generated_by_chat`, `chat_session_id` |

**Indexes (auto-created by `initialize_indexes()` at startup):**
- `idx_workflow_tenant_id` — `{ tenant_id: 1, id: 1 }` UNIQUE — fast lookup + tenant isolation

---

### Collection: `execution_runs`

Stores `ExecutionRun` documents tracking the full lifecycle of a workflow execution, including per-node states and outputs.

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Auto-generated MongoDB primary key |
| `run_id` | String | Application-level run ID (e.g. `run_abc123`) |
| `tenant_id` | String | Tenant isolation key |
| `workflow_id` | String | ID of the workflow being executed |
| `status` | String | Run-level status: `QUEUED`, `RUNNING`, `SUCCESS`, `FAILED`, `CANCELLED`, `WAITING_HUMAN` |
| `input_data` | Object | Trigger input payload passed to the first node |
| `output_data` | Object | Final output of the last terminal node |
| `node_states` | Object | Map of `node_id → NodeExecutionState`. Each state has: `status`, `started_at`, `ended_at`, `error` (string\|null), `outputs` (object), `logs` (string[]) |
| `error` | String \| null | Run-level error message if status is `FAILED` |
| `started_at` | Date \| null | When the run transitioned to `RUNNING` |
| `ended_at` | Date \| null | When the run reached a terminal state |
| `celery_task_id` | String \| null | Celery `AsyncResult` task ID — used to cancel the Celery task on run cancellation |
| `retry_of` | String \| null | Original `run_id` if this run is a retry |

**Write patterns:**
- `create()` — full document insert on `POST /executions`
- `update_node_state()` — atomic `$set node_states.{node_id}` — safe for parallel node writes
- `bulk_update_node_states()` — batch `$set` of all nodes in a layer — one round-trip per topological layer
- `patch_fields()` — partial `$set` for top-level fields (e.g. `status`, `celery_task_id`)

**Indexes (auto-created by `initialize_indexes()` at startup):**
- `idx_execution_tenant_run` — `{ tenant_id: 1, run_id: 1 }` UNIQUE
- `idx_execution_tenant_workflow_date` — `{ tenant_id: 1, workflow_id: 1, started_at: -1 }` — run history list
- `idx_execution_stale_reaper` — `{ status: 1, started_at: 1 }` — stale run reaper query

---

### Collection: `schedules`

Stores `ScheduleModel` documents for cron-triggered workflows. The scheduler worker polls `get_due_schedules()` on a heartbeat tick.

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Auto-generated MongoDB primary key |
| `schedule_id` | String | Application-level schedule ID |
| `tenant_id` | String | Tenant isolation key |
| `workflow_id` | String | ID of the workflow to trigger on fire |
| `cron_expression` | String | Standard Unix cron expression (e.g. `"0 9 * * MON"`) |
| `timezone` | String | Timezone for cron evaluation (default: `"UTC"`) |
| `next_fire_at` | Date \| null | Next scheduled fire time — updated after each successful fire |
| `is_active` | Boolean | Whether the schedule is actively polling (default: `true`) |
| `input_data` | Object | Static trigger input payload to pass to the workflow (default: `{}`) |

**Write patterns:**
- `get_due_schedules(timestamp)` — global query: `{ is_active: true, next_fire_at: { $lte: now } }` across all tenants

**Indexes (auto-created by `initialize_indexes()` at startup):**
- `idx_schedule_tenant_id` — `{ tenant_id: 1, schedule_id: 1 }` UNIQUE
- `idx_schedule_due` — `{ is_active: 1, next_fire_at: 1 }` — due-schedule polling

---

### Collection: `conversations`

Stores `ChatSession` documents for the AI chat-to-workflow feature. Sessions track the full conversation history, extracted requirements, and the generated workflow ID.

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Auto-generated MongoDB primary key |
| `session_id` | String | Application-level session ID (format: `cs_{hex}`) |
| `tenant_id` | String | Tenant isolation key |
| `user_id` | String | User who owns the session |
| `phase` | String | Conversation phase: `GATHERING`, `CLARIFYING`, `FINALIZING`, `GENERATING`, `COMPLETE` |
| `messages` | Array | List of `ChatMessage`: `{ id, role ("user"\|"assistant"), content, ts }` |
| `requirement_spec` | Object \| null | Extracted intent: `{ goal, trigger_type, trigger_config, input_sources, processing_steps, integrations, output_format, constraints }` |
| `generated_workflow_id` | String \| null | MongoDB workflow ID after successful DAG generation |
| `clarification_round` | Integer | How many clarification rounds have occurred (incremented on each `CLARIFYING` phase transition) |
| `created_at` | Date | Session creation time |
| `updated_at` | Date | Updated on every message append or phase change |

**Indexes (auto-created by `initialize_indexes()`):**
- `{ tenant_id: 1, session_id: 1 }` UNIQUE
- `{ updated_at: 1 }` with `expireAfterSeconds: 2592000` (30-day TTL — sessions auto-deleted)

---

### Collection: `audit_log`

Append-only audit trail written directly by the worker on DLQ hits and system events. No repository class — written via raw Motor client in `workflow_worker/dependencies.py`. TTL index on `created_at` auto-created at worker startup (90-day expiry).

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Auto-generated |
| `tenant_id` | String | Tenant the event belongs to (`"SYSTEM"` for platform-level events) |
| `event_type` | String | Event type string (e.g. `"dlq_hit"`, `"run_failed"`) |
| `user_id` | String | `"SYSTEM"` for worker-generated events |
| `resource_type` | String | `"task"` for Celery task events |
| `resource_id` | String \| null | Resource identifier if applicable |
| `detail` | Object | Arbitrary JSON detail dict (task args, error messages, etc.) |
| `created_at` | Date | Event timestamp — TTL index key |

**Indexes (auto-created by worker at startup):**
- `idx_audit_log_ttl` — `{ created_at: 1 }` with `expireAfterSeconds: 7776000` — documents auto-deleted after 90 days

---

## Part 3 — Redis

Redis is used for three distinct purposes: event streaming, caching, and ephemeral state.

| Key Pattern | Type | TTL | Description |
|---|---|---|---|
| `run:{run_id}:events` | PubSub channel | — | Execution event stream. `RunOrchestrator` publishes JSON events (`node_state`, `run_complete`, `run_waiting_human`). WebSocket hub subscribes and fans out to browser clients. |
| `tenant_config:{tenant_id}` | String (JSON) | 300s (5 min) | Serialised `TenantConfig` (plan_tier, pii_policy, quotas). Read by every Celery task on startup. Cache miss → PostgreSQL fetch. |
| `state:{run_id}:{state_key}` | String (JSON) | 86400s (24h) | Per-run workflow state values written by `SetStateNode`. Loaded into `context.state` by the orchestrator at the start of resume operations. |
| `state_keys:{run_id}` | Set | 86400s (24h) | Tracks which state keys exist for a given run. Used by the orchestrator to bulk-load `context.state` without scanning. |
| `{tenant_id}:{endpoint}` | String | 60s window | Per-tenant rate limit counter managed by `slowapi`. Key format is internal to slowapi's storage backend. `Limiter` configured with `swallow_errors=True` — fails open when Redis is unavailable. |

---

## Fixes Applied (2026-04-07)

All schema gaps have been resolved. The table below documents what was fixed and where.

| # | Gap | Status | Fix Applied |
|---|---|---|---|
| 1 | `PIIPolicy.DISABLED` not in SQL ENUM | ✅ Fixed | Added `004_pii_disabled.sql` (`ALTER TYPE pii_policy ADD VALUE IF NOT EXISTS 'DISABLED' BEFORE 'SCAN_WARN'`) + Alembic wrapper `0004_pii_disabled.py` |
| 2 | MongoDB indexes not auto-created | ✅ Fixed | Added `initialize_indexes()` to `MongoWorkflowRepository`, `MongoExecutionRepository`, `MongoScheduleRepository`; called from `RepositoryFactory.create_all()` at startup |
| 3 | `billing_repo.py` inserted `model_name` but SQL column is `model` | ✅ Fixed | `billing_repo.py` `record_llm_tokens()` — changed INSERT column from `model_name` to `model` |
| 4 | `billing_repo.py` inserted `duration_ms` but SQL defines `compute_seconds` | ✅ Fixed | `billing_repo.py` `record_node_execution()` — converts `duration_ms / 1000` → `compute_seconds (NUMERIC)`; also added required `started_at = NOW()` |
| 5 | Migrations `002`/`003` had no Alembic wrapper | ✅ Fixed | Created `0002_webhooks.py` and `0003_performance_indexes.py` — full chain is now `0001 → 0002 → 0003 → 0004` |

| 6 | `audit_log` has no TTL index — grows unbounded | ✅ Fixed | `workflow_worker/dependencies.py` now calls `await _audit_col.create_index("created_at", expireAfterSeconds=7776000, name="idx_audit_log_ttl")` on every worker startup (idempotent). Documents expire after **90 days**. |
