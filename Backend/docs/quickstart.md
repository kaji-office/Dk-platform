# DK Platform — Quickstart Guide

Choose the setup path that matches your environment:

| Path | Best for | Requires |
|---|---|---|
| **[A] Make](#path-a--make-recommended)** | Fastest start — one-liners | Python 3.12, Docker |
| **[B] Docker Compose (manual)](#path-b--docker-compose-no-make)** | Portable, no Make | Python 3.12, Docker |
| **[C] Native services](#path-c--native-services-no-docker)** | Already have Postgres/Mongo/Redis running | Python 3.12, running services |

Steps 1–3 (clone, keys, `.env`) are identical for all paths — only the **infrastructure** setup differs.

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.12+ | `python3 --version` |
| OpenSSL | any | `openssl version` |
| Docker + Compose v2 | 24+ | `docker compose version` *(paths A & B only)* |
| Node.js | 18 LTS | `node --version` *(frontend only)* |

---

## Step 1 — Clone

```bash
git clone <repo-url> dk-platform
cd dk-platform
```

---

## Step 2 — Generate JWT key pair

RS256 tokens require a private/public key pair. Run once:

```bash
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

> `keys/` is git-ignored. Never commit these files.

---

## Step 3 — Configure `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in these sections:

### LLM provider key (at least one required)

```bash
ANTHROPIC_API_KEY=sk-ant-...        # Claude — recommended
# OR
OPENAI_API_KEY=sk-...               # GPT-4o
# OR — Gemini (platform default model)
VERTEX_AI_PROJECT=your-gcp-project
VERTEX_AI_LOCATION=us-central1
```

If using OpenAI as default, also add:
```bash
DEFAULT_LLM_PROVIDER=openai
```

### JWT keys

```bash
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_REFRESH_SECRET=<run: openssl rand -hex 32>
```

### Infrastructure URLs

Set these based on your chosen path:

**Path A or B (Docker):**
```bash
MONGODB_URL=mongodb://localhost:27017/workflow_platform
POSTGRES_URL=postgresql://workflow:devpassword@localhost:5432/workflow_platform
POSTGRES_URL_ASYNCPG=postgresql+asyncpg://workflow:devpassword@localhost:5432/workflow_platform
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
S3_BUCKET=workflow-platform-dev
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
```

**Path C (native services — no Redis password):**
```bash
MONGODB_URL=mongodb://localhost:27017/workflow_platform
POSTGRES_URL=postgresql://workflow:devpassword@localhost:5432/workflow_platform
POSTGRES_URL_ASYNCPG=postgresql+asyncpg://workflow:devpassword@localhost:5432/workflow_platform
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### Optional — SMTP (email verification + password reset)

Omitting `SMTP_HOST` is fine for development — the platform starts normally and skips sending emails:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@example.com
APP_URL=http://localhost:3000
```

---

## Path A — Make (recommended)

> Requires: Python 3.12, Docker, Make

### A1. Start infrastructure

```bash
make dev
```

Starts 6 containers in the background:

| Container | Port | What |
|---|---|---|
| `wf_postgres` | 5432 | PostgreSQL 16 + pgvector |
| `wf_mongodb` | 27017 | MongoDB 7 |
| `wf_redis` | 6379 | Redis 7 |
| `wf_localstack` | 4566 | S3 (LocalStack) |
| `wf_flower` | 5555 | Celery task monitor |
| `wf_mongo_express` | 8081 | MongoDB UI |

Wait until all containers are healthy:
```bash
docker compose -f docker-compose.dev.yml ps
# All rows should show (healthy)
```

### A2. Install Python packages

```bash
make install-dev
```

### A3. Run migrations

```bash
make migrate
```

This runs Alembic (`upgrade head`) and bootstraps MongoDB indexes.

Apply the webhooks table migration manually (not yet in Alembic):
```bash
docker exec -i wf_postgres psql -U workflow -d workflow_platform \
  < infra/database/postgres/migrations/002_webhooks.sql
```

### A4. Start the API server

```bash
make run-api
```

### A5. Start the Celery worker (new terminal)

```bash
make run-worker
```

### A6. Start Celery beat — for scheduled triggers (new terminal)

```bash
make run-scheduler
```

### A7. Verify

```bash
curl http://localhost:8000/health
# {"status":"healthy","version":"1.0.0","checks":{"postgres":"ok","mongodb":"ok","redis":"ok"}}
```

Open **http://localhost:8000/docs** for the interactive API explorer.

### Stopping

```bash
make dev-down          # stop containers, keep data volumes
# OR to wipe all data:
docker compose -f docker-compose.dev.yml down -v
```

---

## Path B — Docker Compose (no Make)

> Requires: Python 3.12, Docker Compose v2

### B1. Start infrastructure

```bash
docker compose -f docker-compose.dev.yml up -d
```

Wait until healthy:
```bash
docker compose -f docker-compose.dev.yml ps
```

### B2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

### B3. Install Python packages

```bash
pip install -e "packages/workflow-engine[dev]"
pip install -e "packages/workflow-api[dev]"
pip install -e "packages/workflow-worker[dev]"
pip install -e "packages/workflow-cli[dev]"
```

### B4. Run migrations

The PostgreSQL container auto-applies `001_initial_schema.sql` on first start.
Apply the webhooks migration and run Alembic for subsequent changes:

```bash
docker exec -i wf_postgres psql -U workflow -d workflow_platform \
  < infra/database/postgres/migrations/002_webhooks.sql

cd packages/workflow-api && alembic upgrade head && cd ../..
```

Bootstrap MongoDB indexes:
```bash
python -m workflow_engine.infra.mongodb_indexes
```

### B5. Start the API server

```bash
uvicorn workflow_api.main:app --reload --host 0.0.0.0 --port 8000
```

### B6. Start the Celery worker (new terminal)

```bash
source .venv/bin/activate
celery -A workflow_worker.celery_app worker \
  --loglevel=info \
  --queues=default,ai-heavy,critical,scheduled \
  --concurrency=4
```

### B7. Start Celery beat — for scheduled triggers (new terminal)

```bash
source .venv/bin/activate
celery -A workflow_worker.celery_app beat \
  --loglevel=info \
  --scheduler celery.beat:PersistentScheduler
```

### B8. Verify

```bash
curl http://localhost:8000/health
```

### Stopping

```bash
docker compose -f docker-compose.dev.yml down          # keep data
docker compose -f docker-compose.dev.yml down -v       # wipe data
```

---

## Path C — Native services (no Docker)

> Requires: Python 3.12, MongoDB + PostgreSQL + Redis already running as system services

**Expected connection details:**

| Service | Port | Credentials |
|---|---|---|
| PostgreSQL | 5432 | user: `workflow`, password: `devpassword`, db: `workflow_platform` |
| MongoDB | 27017 | no auth |
| Redis | 6379 | no password |

### C1. Create the PostgreSQL database and user

Skip if already done:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER workflow WITH PASSWORD 'devpassword';
CREATE DATABASE workflow_platform OWNER workflow;
GRANT ALL PRIVILEGES ON DATABASE workflow_platform TO workflow;
SQL
```

Enable required extensions (requires `postgresql-<ver>-pgvector`):

```bash
psql postgresql://workflow:devpassword@localhost:5432/workflow_platform <<'SQL'
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS vector;
SQL
```

> Install pgvector if needed:
> ```bash
> sudo apt install postgresql-16-pgvector   # replace 16 with your PG version
> ```

### C2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### C3. Install Python packages

```bash
pip install -e "packages/workflow-engine[dev]"
pip install -e "packages/workflow-api[dev]"
pip install -e "packages/workflow-worker[dev]"
pip install -e "packages/workflow-cli[dev]"
```

### C4. Run migrations

Apply the initial schema:
```bash
psql postgresql://workflow:devpassword@localhost:5432/workflow_platform \
  -f infra/database/postgres/migrations/001_initial_schema.sql
```

Apply the webhooks table:
```bash
psql postgresql://workflow:devpassword@localhost:5432/workflow_platform \
  -f infra/database/postgres/migrations/002_webhooks.sql
```

Run Alembic for any subsequent migrations:
```bash
cd packages/workflow-api && alembic upgrade head && cd ../..
```

Bootstrap MongoDB indexes:
```bash
python -m workflow_engine.infra.mongodb_indexes
```

### C5. Start the API server

```bash
uvicorn workflow_api.main:app --reload --host 0.0.0.0 --port 8000
```

### C6. Start the Celery worker (new terminal)

```bash
source .venv/bin/activate
celery -A workflow_worker.celery_app worker \
  --loglevel=info \
  --queues=default,ai-heavy,critical,scheduled \
  --concurrency=4
```

### C7. Start Celery beat — for scheduled triggers (new terminal)

```bash
source .venv/bin/activate
celery -A workflow_worker.celery_app beat \
  --loglevel=info \
  --scheduler celery.beat:PersistentScheduler
```

### C8. Verify

```bash
curl http://localhost:8000/health
# {"status":"healthy","version":"1.0.0","checks":{"postgres":"ok","mongodb":"ok","redis":"ok"}}
```

---

## First API calls (all paths)

### Register an account

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "password123",
    "name": "Admin User",
    "tenant_name": "My Company"
  }' | python3 -m json.tool
```

Copy the `access_token` from the response.

### Create and trigger a workflow

```bash
TOKEN="<paste access_token>"

# Create workflow
curl -s -X POST http://localhost:8000/api/v1/workflows \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hello World",
    "definition": {
      "nodes": {
        "trigger_1":  { "type": "ManualTriggerNode", "config": {}, "position": { "x": 0, "y": 0 } },
        "template_1": {
          "type": "TemplatingNode",
          "config": { "template": "Hello, {{ payload.name }}!" },
          "position": { "x": 300, "y": 0 }
        },
        "output_1": { "type": "OutputNode", "config": {}, "position": { "x": 600, "y": 0 } }
      },
      "edges": [
        { "id": "e1", "source_node_id": "trigger_1",  "source_port": "default", "target_node_id": "template_1", "target_port": "default" },
        { "id": "e2", "source_node_id": "template_1", "source_port": "default", "target_node_id": "output_1",   "target_port": "default" }
      ]
    }
  }' | python3 -m json.tool
# Note the workflow_id

WORKFLOW_ID="<paste workflow_id>"

# Trigger
curl -s -X POST "http://localhost:8000/api/v1/workflows/$WORKFLOW_ID/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "input_data": { "name": "World" } }' | python3 -m json.tool
# Note the run_id
# ManualTriggerNode wraps input_data as {"payload": {...}},
# so {{ payload.name }} in the template resolves to "World".

RUN_ID="<paste run_id>"

# Poll for result (usually done within 5s)
curl -s "http://localhost:8000/api/v1/executions/$RUN_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# "status": "SUCCESS"
# output_data: {"value": {"rendered": "Hello, World!"}}
```

### Chat-driven workflow creation

```bash
# Create a session
curl -s -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Lead scoring"}' | python3 -m json.tool
# Note the session_id

SESSION_ID="<paste session_id>"

# Send a message
curl -s -X POST "http://localhost:8000/api/v1/chat/sessions/$SESSION_ID/message" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "I need a workflow that scores leads from a CRM webhook"}' \
  | python3 -m json.tool
# Keep sending messages until phase = COMPLETE

# Real-time streaming via WebSocket (requires wscat: npm install -g wscat)
wscat -c "ws://localhost:8000/api/v1/chat/sessions/ws/chat/$SESSION_ID?token=$TOKEN"
# Then type: {"type":"message","content":"score leads from Salesforce webhook"}
```

---

## CLI

```bash
source .venv/bin/activate   # if using venv

wf --help
wf auth login --url http://localhost:8000
wf workflow list
wf run trigger <workflow_id> --input '{"name": "World"}'
wf run logs <run_id> --follow
```

---

## Tests

```bash
source .venv/bin/activate

# Unit tests — no services needed
pytest packages/workflow-engine/tests/unit -v

# API tests — needs running services
pytest packages/workflow-api/tests -v

# All tests with coverage
pytest packages/workflow-engine/tests \
  --cov=packages/workflow-engine/src/workflow_engine \
  --cov-report=html:coverage_html \
  --cov-report=term-missing \
  --cov-fail-under=85
# Open coverage_html/index.html for the report
```

Make equivalents: `make test-unit` / `make test-api` / `make test-cov`

---

## Code quality

```bash
ruff check packages/                             # lint
ruff format packages/ && ruff check --fix packages/  # format
mypy packages/workflow-engine/src/workflow_engine --strict  # type check
cd packages/workflow-engine && lint-imports      # layer boundary check
```

Make equivalent: `make check`

---

## Frontend (when F-1 is built)

```bash
cd packages/workflow-ui
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_WS_URL=ws://localhost:8000" >> .env.local
npm run dev
# Open http://localhost:3000
```

Make equivalent: `make run-ui`

> Frontend tasks F-1 through F-6 are pending — see TASKS.md.

---

## Debug & monitor

| URL | What |
|---|---|
| http://localhost:8000/docs | Swagger UI — try every endpoint live |
| http://localhost:8000/redoc | ReDoc — clean API reference |
| http://localhost:5555 | Flower — Celery task monitor (`admin` / `devpassword`) — Docker paths only |
| http://localhost:8081 | Mongo Express — browse collections (`admin` / `devpassword`) — Docker paths only |

---

## Known limitations (2026-04-01)

| Limitation | Workaround |
|---|---|
| `fire_schedule` Celery task is a stub | Scheduled triggers do not fire automatically yet |
| `send_notification` task is a stub | Outbound webhook / email delivery not dispatched from worker |
| Frontend (F-1 – F-6) not built yet | Use `/docs` Swagger UI or the CLI |
| gVisor (Tier 2 sandbox) requires Linux + gVisor installed | Set `SANDBOX_TIER2_ENABLED=false` in `.env` to use Tier 1 (subprocess) |
| MFA and HumanInput nodes are off by default | Set `MCP_NODE_ENABLED=true` / `HUMAN_NODE_ENABLED=true` in `.env` |

---

## Make command reference

For those using Make — full equivalents for every command above:

| Make command | Direct equivalent |
|---|---|
| `make keys` | `mkdir -p keys && openssl genrsa -out keys/private.pem 2048 && openssl rsa -in keys/private.pem -pubout -out keys/public.pem` |
| `make dev` | `docker compose -f docker-compose.dev.yml up -d` |
| `make dev-down` | `docker compose -f docker-compose.dev.yml down` |
| `make install-dev` | `pip install -e "packages/workflow-engine[dev]" && pip install -e "packages/workflow-api[dev]" && pip install -e "packages/workflow-worker[dev]" && pip install -e "packages/workflow-cli[dev]"` |
| `make migrate` | `cd packages/workflow-api && alembic upgrade head && cd ../.. && python -m workflow_engine.infra.mongodb_indexes` |
| `make run-api` | `uvicorn workflow_api.main:app --reload --host 0.0.0.0 --port 8000` |
| `make run-worker` | `celery -A workflow_worker.celery_app worker --loglevel=info --queues=default,ai-heavy,critical,scheduled --concurrency=4` |
| `make run-scheduler` | `celery -A workflow_worker.celery_app beat --loglevel=info --scheduler celery.beat:PersistentScheduler` |
| `make run-ui` | `cd packages/workflow-ui && npm run dev` |
| `make test-unit` | `pytest packages/workflow-engine/tests/unit -v` |
| `make test-api` | `pytest packages/workflow-api/tests -v` |
| `make test-cov` | `pytest packages/workflow-engine/tests --cov=... --cov-fail-under=85` |
| `make lint` | `ruff check packages/` |
| `make format` | `ruff format packages/ && ruff check --fix packages/` |
| `make typecheck` | `mypy packages/workflow-engine/src/workflow_engine --strict` |
| `make check` | `make lint && make typecheck && make layer-check` |

---

## Directory reference

```
dk-platform/
├── packages/
│   ├── workflow-engine/   ← SDK — all business logic
│   ├── workflow-api/      ← FastAPI delivery layer (HTTP + WebSocket)
│   ├── workflow-worker/   ← Celery delivery layer
│   ├── workflow-cli/      ← CLI (wf command)
│   └── workflow-ui/       ← Next.js 14 frontend (pending F-1 – F-6)
├── docs/
│   ├── api/openapi.yaml          ← Full API spec (all paths + schemas)
│   ├── frontend/handover.md      ← Schema corrections + WebSocket protocol
│   ├── frontend/chat-module.md   ← Chat UI TypeScript spec
│   └── frontend/overview.md      ← Tech stack, canvas state, auth flow
├── infra/
│   └── database/postgres/migrations/  ← Raw SQL (001 initial, 002 webhooks)
├── keys/                  ← JWT key pair (git-ignored)
├── .env.example           ← All environment variable reference
├── docker-compose.dev.yml ← Docker infrastructure stack
└── Makefile               ← Shorthand for all commands above
```
