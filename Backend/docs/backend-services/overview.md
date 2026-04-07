# Backend Services — Overview
## workflow-api · workflow-worker · workflow-scheduler · workflow-cli

---

## 1. Shared Principle

All four backend services are **thin consumers of the workflow-engine SDK**. They contain:
- Transport logic (HTTP routes, Celery task definitions, CLI commands)
- Auth middleware
- Framework-specific setup

They contain **zero** workflow logic. Any business rule that could be needed by more than one service lives in the SDK.

---

## 2. workflow-api (FastAPI Gateway)

### Responsibility
HTTP/WebSocket gateway. Authenticates requests, delegates all logic to SDK, dispatches executions to Celery.

### As-Built Project Structure

> **Note:** The current implementation uses a lean monolithic structure. All platform services (`PlatformAuthService`, `PlatformWorkflowService`, `PlatformExecutionService`, `PlatformScheduleService`, `PlatformAuditService`, etc.) are defined in `main.py` alongside the FastAPI lifespan. Routes are split into separate files under `routes/`.

```
packages/workflow-api/
├── pyproject.toml          # depends on: workflow-engine, fastapi, uvicorn, celery, slowapi
└── src/workflow_api/
    ├── main.py             # FastAPI app + lifespan + ALL platform service classes
    │                       # PlatformAuthService, PlatformWorkflowService,
    │                       # PlatformExecutionService, PlatformScheduleService,
    │                       # PlatformAuditService (write() + list()), PlatformWebhookService,
    │                       # PlatformBillingService, PlatformUserService
    ├── app.py              # Rate limiter setup (SlowAPI, storage_uri=REDIS_URL)
    ├── dependencies.py     # CurrentUser, TenantId, RequireWrite Depends() providers
    │
    └── routes/
        ├── health.py       # GET /health · /readyz · /livez
        ├── auth.py         # POST /auth/register · /login · /logout · /token/refresh
        │                   # + email verify, password reset, MFA, OAuth
        ├── users.py        # GET/PATCH /users/me · /users
        ├── workflows.py    # CRUD + activate/deactivate + versions + schedules
        │                   # Audit writes: workflow.created, workflow.deleted, schedule.created
        ├── executions.py   # trigger + list + get + cancel + retry + nodes + logs
        │                   # Audit write: execution.triggered
        ├── chat.py         # POST /chat · WS /chat/ws (Redis PubSub streaming)
        ├── webhooks.py     # GET/POST/DELETE /webhooks + inbound receiver + GET /audit
        └── __pycache__/
```

### Middleware Stack (request order)
```
Request
  → RequestIDMiddleware         inject X-Request-ID + success/error response wrapper
  → CORSMiddleware              configured origins
  → SlowAPI RateLimitMiddleware Redis per-tenant RPM counter (storage_uri=REDIS_URL)
  → JWT/API key auth            CurrentUser + TenantId Depends() resolved per route
  → Route Handler
Response
  → Structured JSON: {success, request_id, data} or {success, request_id, error, message}
```

### Key Routes (as-built)

| Route | Method | Notes |
|---|---|---|
| `POST /api/v1/auth/register` | POST | Creates user + tenant; returns `user_id`, `email`; writes `auth.register` audit event |
| `POST /api/v1/auth/login` | POST | Returns `access_token`, `refresh_token`, `user_id`, `tenant_id`; writes `auth.login` audit event |
| `POST /api/v1/workflows` | POST | Creates workflow; writes `workflow.created` audit event |
| `DELETE /api/v1/workflows/{id}` | DELETE | Writes `workflow.deleted` audit event |
| `POST /api/v1/workflows/{id}/trigger` | POST | Creates `ExecutionRun`, dispatches `execute_workflow` to Celery; writes `execution.triggered` audit event |
| `WS /ws/chat` | WS | Redis PubSub streaming chat |
| `GET /api/v1/audit` | GET | Returns tenant-scoped audit events from MongoDB `audit_log` collection |
| `GET /health` | GET | Returns `{status: ok, service: workflow-api}` |

### Lifespan Management (as-built)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP — reads env vars directly (no settings object)
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    pg_pool = await asyncpg.create_pool(POSTGRES_URL_ASYNCPG)
    redis_client = redis.from_url(REDIS_URL)  # redis[asyncio]
    # Injects services into app.state:
    # auth_service, workflow_service, execution_service, schedule_service,
    # audit_service, webhook_service, billing_service, user_service
    yield
    # SHUTDOWN — closes all connections
```

### Auth implementation (as-built)
- Access token: RS256 JWT, 15 min TTL, stored in React memory
- Refresh token: HMAC-HS256 JWT, 7 day TTL — stored in DB (not opaque SHA-256)
- **Logout is a no-op** in v1 — token still valid until expiry; JTI blocklist deferred
- Rate limit: SlowAPI 60 req/min per tenant, Redis-backed (`LIMITS:LIMITER/*` keyspace)

---

## 3. workflow-worker (Celery)

### Responsibility
Consumes tasks from Redis queues. Calls `RunOrchestrator.run()` from the SDK. Zero workflow logic of its own.

### As-Built Project Structure

> **Note:** All tasks are in a single `tasks.py` file, not a `tasks/` directory.

```
packages/workflow-worker/
├── pyproject.toml          # depends on: workflow-engine, celery, redis
└── src/workflow_worker/
    ├── celery_app.py       # Celery app config + queue definitions + beat schedule
    ├── dependencies.py     # get_engine() — builds SDK repository bundle
    └── tasks.py            # All Celery tasks in one file:
                            #   execute_workflow — main execution entry point
                            #   execute_node     — single node retry/offload
                            #   fire_schedule    — beat task (every 30s)
                            #                      dispatches execute_workflow per due schedule
                            #   send_notification
                            #   handle_dlq       — dead-letter handler
```

### Queue Configuration (as-built)
```python
# celery_app.py

app = Celery("workflow_worker")
app.conf.update(
    broker_url=CELERY_BROKER_URL,          # Redis DB0
    result_backend=CELERY_RESULT_BACKEND,  # Redis DB1, ~8h TTL
    task_routes={
        "workflow_worker.tasks.execute_workflow": {"queue": "default"},
        "workflow_worker.tasks.execute_node":     {"queue": "ai-heavy"},
        "workflow_worker.tasks.fire_schedule":    {"queue": "scheduled"},
        "workflow_worker.tasks.send_notification":{"queue": "default"},
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "fire-schedules": {
            "task": "workflow_worker.tasks.fire_schedule",
            "schedule": 30.0,          # every 30 seconds (not every minute)
            "options": {"queue": "scheduled"},
        },
    },
)
```

### Core Task: execute_workflow (as-built)
```python
@app.task(bind=True, autoretry_for=TRANSIENT_ERRORS, retry_kwargs={"max_retries": 3},
          name="workflow_worker.tasks.execute_workflow")
def execute_workflow(self, run_id: str, tenant_id: str, workflow_id: str | None = None, ...):
    """Loads run from DB, loads workflow def, calls RunOrchestrator.run()."""
    sdk = run_async(get_engine())
    run = run_async(sdk["execution_repo"].get(tenant_id, run_id))
    workflow = run_async(sdk["workflow_repo"].get(tenant_id, run.workflow_id))
    run_async(sdk["orchestrator"].run(
        workflow_def=workflow, run_id=run_id, tenant_id=tenant_id,
        trigger_input=run.input_data,   # input_data from DB — authoritative
    ))
```

### Beat Task: fire_schedule (as-built)
```python
@app.task(bind=True, name="workflow_worker.tasks.fire_schedule")
def fire_schedule(self):
    """Runs every 30s. Finds due schedules, dispatches execute_workflow per schedule."""
    service = SchedulerService(sdk["scheduler"])
    fired = run_async(service.tick())
    for schedule in fired:
        run = ExecutionRun(..., input_data=schedule.input_data)  # uses schedule.input_data
        run_async(sdk["execution_repo"].create(tenant_id, run))
        execute_workflow.delay(run_id, tenant_id, workflow_id)
```

---

## 4. workflow-scheduler (Celery Beat)

### Responsibility
Exactly-one beat process. Fires cron-based workflow executions and periodic maintenance tasks.

### Deployment
Single replica deployment — beat must never run as multiple instances (would double-fire cron triggers).

```yaml
# K8s deployment for scheduler
spec:
  replicas: 1          # CRITICAL: always exactly 1
  strategy:
    type: Recreate     # Never RollingUpdate — would briefly have 2 instances
```

### Beat Schedule (as-built)

> **As-built:** Beat fires a single `fire_schedule` task every **30 seconds** (not every minute). Cleanup tasks (semaphore purge, retention) are deferred to a future sprint.

```python
# celery_app.py — beat_schedule
{
    "fire-schedules": {
        "task": "workflow_worker.tasks.fire_schedule",
        "schedule": 30.0,          # every 30s via PersistentScheduler
        "options": {"queue": "scheduled"},
    },
}
```

`fire_schedule` calls `SchedulerService.tick()` which queries MongoDB for documents where `is_active=True AND next_fire_at <= now`. For each due schedule it:
1. Creates an `ExecutionRun` with `input_data=schedule.input_data`
2. Dispatches `execute_workflow.delay(run_id, tenant_id, workflow_id)`
3. Advances `next_fire_at` to the next cron occurrence

---

## 5. workflow-cli (Click)

### Responsibility
Developer tool for local workflow validation, deployment to API, and log tailing. The CLI uses the SDK locally for validation (no network), and HTTP for all other operations.

### Project Structure
```
packages/workflow-cli/
├── pyproject.toml          # depends on: workflow-engine, click, httpx, rich
└── src/workflow_cli/
    ├── cli.py              # Click group + global options (--api-url, --api-key)
    ├── config.py           # ~/.workflow/config.toml — stored credentials
    │
    └── commands/
        ├── auth.py         # wf login · wf logout · wf whoami
        ├── validate.py     # wf validate ./workflow.json (SDK-only, no network)
        ├── deploy.py       # wf deploy ./workflow.json → PUT /api/v2/workflows
        ├── run.py          # wf run {workflow_id} → POST /api/v2/executions
        ├── logs.py         # wf logs {run_id} → WS /ws/runs/{id} (streams to terminal)
        ├── versions.py     # wf versions {workflow_id} → list + diff + rollback
        └── nodes.py        # wf nodes list → GET /api/v2/nodes/types
```

### Key Commands
```bash
# Validate a workflow file locally (no API call — pure SDK)
wf validate ./my-workflow.json

# Deploy to the platform
wf deploy ./my-workflow.json --name "My Workflow"

# Trigger a run with input
wf run wf_abc123 --input '{"customer_id": "c1"}'

# Stream execution logs in real-time
wf logs run_xyz789

# Compare workflow versions
wf versions diff wf_abc123 --from 2 --to 3

# Rollback to a previous version
wf versions rollback wf_abc123 --to 2
```

---

## 6. Service-to-Service Communication

```
workflow-api  ──(Celery task)──►  workflow-worker
     │                                 │
     │                                 │ publishes events
     │                           Redis Pub/Sub
     │                                 │
     ◄────────────────────────── WebSocket hub subscribes
     │
     ►──(HTTP redirect)──► None (API is the only HTTP gateway)

workflow-scheduler ──(Celery task)──► workflow-worker
workflow-cli       ──(HTTP)──────────► workflow-api
```

### Trace Context Propagation
AWS X-Ray trace context is injected into every Celery task to maintain end-to-end distributed traces:

```python
# In API before dispatching:
from aws_xray_sdk.core import xray_recorder
trace_header = xray_recorder.current_segment().serialize_segment_header()
orchestrate_run.delay(run_id, definition_dict, trace_ctx={"x-ray-header": trace_header})

# In Worker when receiving:
from aws_xray_sdk.core import patch_all
xray_recorder.begin_subsegment("orchestrate_run")
```
