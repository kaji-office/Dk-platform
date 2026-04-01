# DK Platform — Quickstart Guide

> **Backend status:** Structurally complete. One wiring gap in `main.py`
> (`auth_service` not attached to `app.state`) must be patched before
> protected routes work. Step 6 covers this fix.
>
> **Time to first API call:** ~15 minutes on a clean machine.

---

## Prerequisites

| Tool | Minimum version | Check |
|---|---|---|
| Python | 3.12 | `python --version` |
| Docker + Compose | Docker 24, Compose v2 | `docker compose version` |
| Node.js | 18 LTS | `node --version` (frontend only) |
| npm | 9 | `npm --version` (frontend only) |
| OpenSSL | any | `openssl version` |

---

## 1. Clone and enter the repo

```bash
git clone <repo-url> dk-platform
cd dk-platform
```

---

## 2. Generate JWT key pair

RS256 signed tokens require a private/public key pair. Generate them once:

```bash
make keys
```

This creates `keys/private.pem` and `keys/public.pem`. **Never commit these files.**

---

## 3. Create your `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in the **required** values. Everything else can stay as the default for local development.

### Required — fill these in

```bash
# At least one LLM provider key (Gemini is the default model)
ANTHROPIC_API_KEY=sk-ant-...        # OR
OPENAI_API_KEY=sk-...               # OR
# For Gemini: set GOOGLE_APPLICATION_CREDENTIALS or use vertex:
VERTEX_AI_PROJECT=your-gcp-project
VERTEX_AI_LOCATION=us-central1
```

> **Minimum viable:** Add only `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to get
> the AI nodes working. The platform defaults to `gemini-2.0-flash` — if you
> only have an OpenAI key, set `DEFAULT_LLM_PROVIDER=openai` in `.env`.

### Pre-filled for local Docker (leave as-is)

```bash
MONGODB_URL=mongodb://localhost:27017/workflow_platform
POSTGRES_URL_ASYNCPG=postgresql+asyncpg://workflow:devpassword@localhost:5432/workflow_platform
REDIS_URL=redis://:devpassword@localhost:6379/0
CELERY_BROKER_URL=redis://:devpassword@localhost:6379/0
S3_BUCKET=workflow-platform-dev
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
```

---

## 4. Start infrastructure

```bash
make dev
```

This starts 6 containers in the background:

| Container | Port | What it is |
|---|---|---|
| `wf_postgres` | 5432 | PostgreSQL 16 + pgvector |
| `wf_mongodb` | 27017 | MongoDB 7 |
| `wf_redis` | 6379 | Redis 7 (broker + cache) |
| `wf_localstack` | 4566 | LocalStack S3 emulation |
| `wf_flower` | 5555 | Celery task monitor |
| `wf_mongo_express` | 8081 | MongoDB UI |

Wait until all containers are healthy:

```bash
docker compose -f docker-compose.dev.yml ps
# All rows should show (healthy)
```

---

## 5. Install Python packages

```bash
make install-dev
```

This installs all four packages in editable mode with dev dependencies:
- `workflow-engine` — SDK (all business logic)
- `workflow-api` — FastAPI delivery layer
- `workflow-worker` — Celery delivery layer
- `workflow-cli` — CLI delivery layer

---

## 6. Apply the `auth_service` wiring patch

`main.py` bootstraps the app but does not attach `auth_service` to `app.state`.
Every protected route calls `request.app.state.auth_service.verify_token()` —
without this patch all non-health endpoints return a 500.

Open `packages/workflow-api/src/workflow_api/main.py` and replace the
`lifespan` function body with the version below:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from workflow_engine.config import EngineConfig
    from workflow_engine.storage.factory import RepositoryFactory
    from workflow_engine.auth.jwt_service import JWTService
    from workflow_engine.auth.api_key_service import APIKeyService
    from workflow_engine.chat.orchestrator import ChatOrchestrator
    from workflow_engine.chat.dag_generator import DAGGeneratorService
    from workflow_engine.providers.factory import ProviderFactory

    logger.info("Starting DK Workflow Engine API...")
    config = EngineConfig()

    repos   = await RepositoryFactory.create_all(config)
    llm     = ProviderFactory.from_config(config.llm_providers)

    # ── Auth services (required by dependencies.py) ────────────────────────
    app.state.auth_service    = JWTService(config)
    app.state.api_key_service = APIKeyService(repos.users)

    # ── Domain services ────────────────────────────────────────────────────
    app.state.workflow_repo   = repos.workflows
    app.state.execution_repo  = repos.executions
    app.state.schedule_repo   = repos.schedules
    app.state.audit_repo      = repos.audit

    # ── Chat (Phase 7) ─────────────────────────────────────────────────────
    generator               = DAGGeneratorService(llm)
    app.state.chat_orchestrator = ChatOrchestrator(
        repo=repos.chat_sessions,
        workflow_repo=repos.workflows,
        generator=generator,
    )

    app.state.repos = repos
    logger.info("API startup complete.")
    yield

    logger.info("Shutting down...")
```

> This is tracked as **FIX-13 / GAP-E1-2** in `TASKS.md`. Once merged to
> `develop`, this step disappears.

---

## 7. Run database migrations

```bash
make migrate
```

This runs:
1. Alembic `upgrade head` — creates all PostgreSQL tables (tenants, users, executions, billing, schedules, etc.)
2. MongoDB index bootstrap — creates compound indexes for workflows, executions, chat sessions

---

## 8. Start the API server

In a new terminal:

```bash
make run-api
```

Expected output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO     Starting DK Workflow Engine API...
INFO     Initializing Repository Factory...
INFO     API startup complete.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Verify it's running:

```bash
curl http://localhost:8000/health
# {"status":"healthy","version":"1.0.0","checks":{"postgres":"ok","mongodb":"ok","redis":"ok"}}
```

Interactive API docs: **http://localhost:8000/docs**

---

## 9. Start the Celery worker

In another new terminal:

```bash
make run-worker
```

Expected output:
```
[tasks]
  . workflow_worker.tasks.execute_workflow
  . workflow_worker.tasks.execute_node
  . workflow_worker.tasks.fire_schedule
  . workflow_worker.tasks.send_notification
  . workflow_worker.tasks.handle_dlq

[2026-03-31 ...] celery@hostname ready.
```

---

## 10. Start the Celery beat scheduler

In another terminal (needed for scheduled triggers):

```bash
make run-scheduler
```

---

## 11. Verify end-to-end

### Register your first account

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "password123",
    "name": "Admin User",
    "tenant_name": "My Company"
  }' | python -m json.tool
```

Response includes `access_token` and `refresh_token`.

### Create a workflow

```bash
export TOKEN="<access_token from above>"

curl -s -X POST http://localhost:8000/workflows \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": { "name": "Hello World", "is_active": true },
    "definition": {
      "nodes": {
        "trigger_1": {
          "type": "manual_trigger",
          "config": {},
          "position": { "x": 0, "y": 0 }
        },
        "prompt_1": {
          "type": "prompt",
          "config": {
            "model": "gemini-2.0-flash",
            "prompt_template": "Say hello to {{ input.name }}",
            "max_tokens": 100
          },
          "position": { "x": 300, "y": 0 }
        },
        "output_1": {
          "type": "output",
          "config": { "output_key": "greeting" },
          "position": { "x": 600, "y": 0 }
        }
      },
      "edges": [
        {
          "id": "edge_trigger_prompt",
          "source_node_id": "trigger_1",
          "source_port": "output",
          "target_node_id": "prompt_1",
          "target_port": "input"
        },
        {
          "id": "edge_prompt_output",
          "source_node_id": "prompt_1",
          "source_port": "output",
          "target_node_id": "output_1",
          "target_port": "input"
        }
      ]
    }
  }' | python -m json.tool
```

Note the returned `workflow_id`.

### Trigger the workflow

```bash
export WORKFLOW_ID="<workflow_id from above>"

curl -s -X POST http://localhost:8000/workflows/$WORKFLOW_ID/trigger \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "input": { "name": "World" } }' | python -m json.tool
```

Note the returned `run_id`.

### Check execution result

```bash
export RUN_ID="<run_id from above>"

curl -s http://localhost:8000/executions/$RUN_ID \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
# "status": "SUCCESS", "output": { "greeting": "Hello, World!" }
```

---

## 12. Start the frontend (optional)

```bash
# Install dependencies
cd packages/workflow-ui
npm install

# Point at the local API
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Start dev server
npm run dev
```

Open **http://localhost:3000** — login with the account from Step 11.

> **Note:** The frontend is not yet built (F-1 through F-6 are pending in
> TASKS.md). This step is a placeholder for when development begins.

---

## 13. Monitor and debug

| URL | What you see |
|---|---|
| http://localhost:8000/docs | Swagger UI — try every API endpoint live |
| http://localhost:8000/redoc | ReDoc — clean API reference |
| http://localhost:5555 | Flower — Celery task monitor (`admin` / `devpassword`) |
| http://localhost:8081 | Mongo Express — browse MongoDB collections (`admin` / `devpassword`) |

### Tail API logs

```bash
# API server logs are already in your terminal.
# For structured JSON logs, set LOG_LEVEL=DEBUG in .env and restart.
```

### Tail worker logs

```bash
# Celery worker logs are in the terminal where you ran make run-worker.
# For task detail: open Flower at http://localhost:5555
```

### Run the test suite

```bash
# Unit tests only (no Docker required)
make test-unit

# All tests (Docker must be running)
make test

# Coverage report → opens ./coverage_html/index.html
make test-cov
```

---

## 14. CLI quickstart

```bash
# Install (already done by make install-dev)
wf --help

# Login
wf auth login --url http://localhost:8000

# List workflows
wf workflow list

# Trigger a workflow
wf run trigger <workflow_id> --input '{"name": "World"}'

# Stream logs from a run
wf run logs <run_id> --follow
```

---

## 15. Known limitations (as of 2026-03-31)

These are tracked in `TASKS.md` — all pending fixes are FIX-12 through FIX-20.

| Limitation | Impact | Fix |
|---|---|---|
| `auth_service` not wired in `main.py` | All protected routes 500 without Step 6 patch | FIX-13 |
| `fire_schedule` task is a stub | Scheduled triggers never fire automatically | FIX-16 |
| `send_notification` task is a stub | Webhook/email notifications not dispatched | FIX-17 |
| No frontend built yet | UI not available | F-1 through F-6 |
| gVisor (Tier 2/3 sandbox) requires Linux + gVisor installed | `code_execution` nodes at Tier 2+ fail on Mac/Windows | FIX-6 (tracked) — set `SANDBOX_TIER2_ENABLED=false` in `.env` to fall back to Tier 1 |
| MFA, HUMAN_WAITING nodes are feature-flagged off | `MCP_NODE_ENABLED=false`, `HUMAN_NODE_ENABLED=false` in `.env` | Set to `true` when ready |

---

## 16. Stop everything

```bash
# Stop infrastructure (data volumes preserved)
make dev-down

# Stop infrastructure AND wipe all data
docker compose -f docker-compose.dev.yml down -v
```

---

## Directory reference

```
dk-platform/
├── packages/
│   ├── workflow-engine/   ← SDK — all business logic (Layers A–D + Phase 7 Chat)
│   ├── workflow-api/      ← FastAPI delivery layer (HTTP + WebSocket)
│   ├── workflow-worker/   ← Celery delivery layer (async task execution)
│   ├── workflow-cli/      ← CLI delivery layer (wf command)
│   └── workflow-ui/       ← Next.js 14 frontend (not yet built)
├── docs/
│   ├── api/openapi.yaml          ← Full API spec (54 paths)
│   ├── frontend/app-handover.md  ← Frontend team handover (all modules)
│   ├── frontend/chat-module.md   ← Chat + DAG builder UI spec
│   └── frontend/handover.md      ← Schema corrections reference
├── infra/                 ← SQL migrations, MongoDB init, K8s manifests
├── keys/                  ← JWT key pair (git-ignored)
├── docker-compose.dev.yml ← Local infrastructure
├── Makefile               ← All developer commands
└── .env.example           ← Environment variable reference
```
