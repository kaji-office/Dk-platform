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

### Project Structure
```
packages/workflow-api/
├── pyproject.toml          # depends on: workflow-engine, fastapi, uvicorn, celery
└── src/workflow_api/
    ├── main.py             # FastAPI app + lifespan + exception handler
    ├── dependencies.py     # All FastAPI Depends() providers
    ├── settings.py         # API-level settings (port, CORS origins, etc.)
    │
    ├── auth/
    │   ├── jwt.py          # RS256 JWT validation + claims extraction
    │   ├── api_key.py      # SHA-256 hash lookup in PostgreSQL
    │   ├── oauth.py        # Google / GitHub / Microsoft OAuth2 flows
    │   ├── sso.py          # SAML/OIDC enterprise SSO
    │   └── middleware.py   # Auth middleware (runs before route handlers)
    │
    ├── middleware/
    │   ├── request_id.py   # Inject X-Request-ID header
    │   ├── tracing.py      # AWS X-Ray root span creation
    │   ├── logging.py      # Structured JSON log per request (PII-masked)
    │   ├── cors.py         # CORS configuration
    │   ├── tenant.py       # JWT/API key → Tenant → EngineConfig injection
    │   ├── rate_limit.py   # Redis per-tenant RPM enforcement
    │   └── semaphore.py    # Concurrent execution limit per tenant
    │
    ├── routes/
    │   ├── health.py       # GET /health · /readyz · /livez
    │   ├── auth.py         # POST /auth/login · /signup · /refresh · /logout
    │   ├── oauth.py        # GET /auth/oauth/{provider} · /callback
    │   ├── workflows.py    # CRUD + duplicate
    │   ├── executions.py   # trigger + status + cancel + retry + nodes
    │   ├── versions.py     # list + get + diff + rollback
    │   ├── nodes.py        # list types + schema
    │   ├── schedules.py    # CRUD schedules
    │   ├── webhooks.py     # inbound webhook receiver
    │   ├── logs.py         # paginated logs + SSE stream
    │   ├── templates.py    # workflow template gallery
    │   ├── settings.py     # profile · team · integrations · billing
    │   ├── api_keys.py     # list + create + revoke
    │   └── admin.py        # tenant management (platform admin only)
    │
    └── websocket/
        ├── hub.py          # Redis Pub/Sub → WebSocket fan-out
        └── events.py       # WsEvent serializer → JSON
```

### Middleware Stack (request order)
```
Request
  → RequestIDMiddleware        inject X-Request-ID
  → XRayTracingMiddleware      create root AWS X-Ray segment
  → StructuredLoggingMiddleware JSON log (PII fields masked)
  → CORSMiddleware             configured origins
  → TenantContextMiddleware    JWT/API key → Tenant → EngineConfig
  → RateLimitMiddleware        Redis per-tenant RPM counter
  → Route Handler
Response
  → GZipMiddleware
```

### Key Routes

| Route | Method | SDK Calls | Notes |
|---|---|---|---|
| `POST /auth/login` | POST | `engine.auth.token` | Returns access + refresh tokens |
| `POST /auth/signup` | POST | `engine.auth.password` | Email verification required |
| `POST /api/v2/workflows` | POST | `validation.validate()` · `versioning.create_version()` | 422 if invalid |
| `POST /api/v2/executions` | POST | `billing.quota_checker` · `versioning.pin_for_execution()` | Dispatches to Celery |
| `DELETE /api/v2/executions/{id}/cancel` | POST | `state.transition_run(CANCELLED)` | Sends Celery revoke |
| `WS /api/v2/ws/runs/{id}` | WS | Redis Pub/Sub subscriber | Real-time node status |
| `GET /api/v2/logs/stream` | GET (SSE) | MongoDB tail cursor | Streaming log output |
| `GET /health` | GET | `engine.health.checker.check_all()` | K8s liveness probe |

### Lifespan Management
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    app.state.mongo = AsyncIOMotorClient(settings.MONGODB_URL)
    app.state.pg_pool = await asyncpg.create_pool(settings.POSTGRES_URL, min_size=5, max_size=20)
    app.state.redis = await aioredis.from_url(settings.REDIS_URL, max_connections=10)
    app.state.node_registry = NodeTypeRegistry.get_instance()
    asyncio.create_task(websocket_hub.start_subscriber())
    yield
    # SHUTDOWN
    app.state.mongo.close()
    await app.state.pg_pool.close()
    await app.state.redis.close()
    websocket_hub.stop()
```

### Global Exception Handler
```python
@app.exception_handler(EngineError)
async def engine_error_handler(request: Request, exc: EngineError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status_code,
        content=ErrorResponse(
            error=type(exc).__name__,
            message=str(exc),
            request_id=request.headers.get("X-Request-ID"),
            validation_errors=getattr(exc, "errors", None),
        ).model_dump(),
    )
```

---

## 3. workflow-worker (Celery)

### Responsibility
Consumes tasks from Redis queues. Calls `RunOrchestrator.run()` from the SDK. Zero workflow logic of its own.

### Project Structure
```
packages/workflow-worker/
├── pyproject.toml          # depends on: workflow-engine, celery, redis
└── src/workflow_worker/
    ├── celery_app.py       # Celery app config + queue definitions
    ├── signals.py          # Worker startup/shutdown hooks
    │
    └── tasks/
        ├── orchestrator.py   # orchestrate_run — main execution task
        ├── node_runner.py    # execute_single_node — parallel branch execution
        ├── cleanup.py        # cleanup_run — post-execution housekeeping
        ├── scheduler.py      # scheduler_fire_cron — beat task
        ├── human_callback.py # handle_human_callback — resume HumanNode
        ├── notifications.py  # send_notification — post-run alerts
        └── export.py         # export_workflow_bundle — ZIP export to S3
```

### Queue Configuration
```python
# workflow-worker/celery_app.py

app = Celery("workflow_worker")
app.config_from_object({
    "broker_url": settings.REDIS_URL,
    "result_backend": settings.REDIS_URL,
    "task_routes": {
        "tasks.orchestrator.orchestrate_run":       {"queue": "default"},
        "tasks.node_runner.execute_single_node":    {"queue": "ai-heavy"},
        "tasks.cleanup.cleanup_run":                {"queue": "default"},
        "tasks.human_callback.handle_human_callback": {"queue": "critical"},
        "tasks.scheduler.scheduler_fire_cron":      {"queue": "scheduled"},
        "tasks.notifications.send_notification":    {"queue": "default"},
    },
    "task_acks_late": True,
    "task_reject_on_worker_lost": True,
    "worker_prefetch_multiplier": 1,     # one task at a time per worker process
    "task_soft_time_limit": 300,         # SoftTimeLimitExceeded after 5 min
    "task_time_limit": 360,              # SIGKILL after 6 min
})
```

### Core Task: orchestrate_run
```python
@app.task(bind=True, max_retries=0, queue="default")
def orchestrate_run(self, run_id: str, definition_dict: dict, trace_ctx: dict) -> None:
    """Entry point from API into execution engine."""
    config = EngineConfig.from_run_context(run_id)  # loads tenant config
    extract_trace_context(trace_ctx)                # continue API trace

    orchestrator = RunOrchestrator(config)
    definition = WorkflowDefinition.model_validate(definition_dict)

    try:
        asyncio.run(orchestrator.run(run_id, definition))
    except Exception as exc:
        # DLQ — all retries exhausted (max_retries=0 means no retry at task level;
        # retry is handled inside RunOrchestrator per node)
        write_to_dlq(self.request.id, {"run_id": run_id}, exc)
        raise
    finally:
        cleanup_run.delay(run_id)
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

### Beat Schedule
```python
app.conf.beat_schedule = {
    "fire-cron-triggers": {
        "task": "tasks.scheduler.scheduler_fire_cron",
        "schedule": crontab(minute="*"),    # every minute
        "options": {"queue": "scheduled"},
    },
    "cleanup-stale-semaphores": {
        "task": "tasks.cleanup.cleanup_stale_semaphores",
        "schedule": crontab(minute="*/5"),  # every 5 min
    },
    "purge-expired-context-keys": {
        "task": "tasks.cleanup.purge_expired_context",
        "schedule": crontab(hour="*"),      # every hour
    },
    "enforce-retention-policy": {
        "task": "tasks.cleanup.enforce_retention",
        "schedule": crontab(hour=2, minute=0),  # daily at 02:00 UTC
    },
}
```

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
