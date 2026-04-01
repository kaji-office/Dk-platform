# Architecture Overview
## AI Workflow Builder Platform — System Architecture v1.0

---

## 1. Platform Vision

A production-grade AI workflow automation platform that enables users to visually compose, execute, and monitor DAG-based AI pipelines. The platform is comparable to n8n (workflow automation) combined with Vellum (LLM orchestration) — but built on a proprietary SDK that is the core product.

**Two user personas:**
- **Visual Builder** — Business users who drag, drop, and configure nodes without writing code
- **Code-Augmented Builder** — Developers or advanced users who combine visual composition with inline code (prompts, Python transforms, conditional expressions)

---

## 2. Five-Layer Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  LAYER 5 — PRESENTATION                                                      ║
║  workflow-ui (Next.js 14 + App Router)                                       ║
║  @workflow/react (component library)                                         ║
║  Communicates ONLY via HTTPS/WebSocket. Never imports the SDK.               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 4 — DELIVERY                                                          ║
║  workflow-api (FastAPI)    workflow-worker (Celery)    workflow-cli (Click)  ║
║  Thin shells. No workflow logic. All intelligence delegated to SDK.          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 3 — SDK CORE  ◄── THE PRODUCT                                        ║
║  workflow-engine (Python library — authored from scratch)                    ║
║  Sub-Layer A: engine.config · engine.models                                  ║
║  Sub-Layer B: engine.dag · engine.nodes · engine.validation                  ║
║  Sub-Layer C: engine.executor · engine.state · engine.context                ║
║  Sub-Layer D: engine.providers · engine.sandbox · engine.integrations        ║
║               engine.cache · engine.versioning · engine.privacy              ║
║               engine.events · engine.auth · engine.billing                   ║
║               engine.health · engine.scheduler · engine.notifications        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 2 — MESSAGE BUS & ASYNC TRANSPORT                                     ║
║  ElastiCache Redis 7 (Celery broker · pub/sub · rate limits · context store) ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 1 — PERSISTENCE & EXTERNAL SERVICES                                   ║
║  RDS PostgreSQL 16   MongoDB Atlas   S3   LLM APIs   AWS CloudWatch          ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 3. Layer Responsibility Rules

| Rule | What It Prevents |
|---|---|
| Layer 5 (UI) never imports the SDK | Frontend logic drift; JS reimplementing Python rules |
| Layer 4 (Delivery) contains no workflow logic | Duplicate execution paths; untestable business rules |
| SDK Sub-Layer A imports nothing from B/C/D | Circular imports; bloated model layer |
| SDK Sub-Layer B never executes code | Mixing parsing with execution |
| SDK Sub-Layer C never calls FastAPI/Celery | Framework lock-in |
| SDK Sub-Layer D modules never call each other arbitrarily | Spaghetti dependencies |
| Layer 2 SDK deps exclude all web/task frameworks | Forces clean architecture boundary |

---

## 4. Runtime Components

| Component | Process | Role |
|---|---|---|
| **workflow-api** | FastAPI + Uvicorn | HTTP/WS gateway, auth, rate limiting, tenant semaphore |
| **workflow-worker** | Celery (N workers) | Executes nodes, manages run lifecycle, drives DAG |
| **workflow-scheduler** | Celery Beat (1 replica) | Cron triggers, periodic cleanup tasks |
| **workflow-cli** | Click (local process) | Validate, deploy, run, tail logs from terminal |
| **workflow-ui** | Next.js (Node.js) | Visual DAG editor, execution monitoring |

---

## 5. End-to-End Request Flow

```
User opens browser
       │
       ▼
workflow-ui (Next.js)        Renders DAG canvas via React Flow
       │ HTTPS/WSS
       ▼
workflow-api (FastAPI)       Thin HTTP shell — validates JWT, delegates to SDK
       │ imports SDK
       ▼
workflow-engine (SDK)        Validates, versions, parses DAG
       │ dispatches via Redis/Celery
       ▼
workflow-worker (Celery)     Thin task shell — calls RunOrchestrator
       │ imports SDK
       ▼
workflow-engine (SDK)        Executes nodes in isolation tiers
       │
       ▼
Isolated Execution           Tier 0-3 based on node type
       │
       ▼
LLM APIs / External APIs / Databases
```

---

## 6. Communication Patterns

### REST (Synchronous)
All CRUD operations, workflow saves, execution triggers. Every request authenticated via JWT Bearer or `X-API-Key` header. Structured JSON responses. SDK `ValidationError` maps to HTTP 422.

### WebSocket (Real-time)
`WS /api/v2/ws/runs/{run_id}` — SDK EventBus publishes to Redis `ws:run:{id}`. WebSocketHub subscribes per-connection and fans out typed events to the browser. Heartbeat every 30s.

### Celery/Redis Queue (Async)
`orchestrate_run.delay(run_id, definition)` fires after API creates `ExecutionRun`. Three queues:
- `default` — orchestration, cleanup
- `ai-heavy` — LLM-intensive node executions
- `critical` — webhook triggers, human node callbacks

### SSE (Log Streaming)
`GET /api/v2/logs/stream?run_id=X` — Server-Sent Events for log tailing in the Observability page.

---

## 7. Technology Stack Summary

| Layer | Technology | Version |
|---|---|---|
| SDK Runtime | Python | 3.12+ |
| Domain Models | Pydantic | v2.x |
| HTTP Client | httpx | 0.27+ |
| MongoDB Driver | motor | 3.x |
| Redis Client | aioredis | 2.x |
| PostgreSQL Driver | asyncpg + pgvector | 0.29+ |
| API Framework | FastAPI | 0.111+ |
| Task Queue | Celery | 5.x |
| CLI Framework | Click | 8.x |
| Frontend Framework | Next.js | 14 (App Router) |
| Canvas / DAG | React Flow | v12 |
| State Management | Zustand + TanStack Query | v5 |
| Styling | Tailwind CSS + shadcn/ui | latest |
| Code Editor | Monaco Editor | latest |
| Cloud Provider | AWS | — |
| Container Orchestration | EKS | 1.29+ |
| Observability | AWS CloudWatch + X-Ray | — |

---

## 8. Key Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Tenancy Model | Hybrid (Shared + Dedicated) | Plan-tier determines isolation level |
| Execution Isolation | 4-tier (Tier 0–3) | Cost-proportional isolation per node type |
| Billing Model | Composite (5 components) | Accurately reflects actual resource consumption |
| Node Authorship | Platform team only | Controlled quality, versioned with SDK |
| User Logic Entry | TransformNode sandbox | Safe, isolated, billable code execution |
| Auth Strategy | Email + OAuth + SSO | Covers all user segments from free to enterprise |
| Cloud Provider | AWS | EKS, RDS, S3, CloudWatch, Bedrock |
| Compliance | GDPR + SOC 2 (v1.0) | EU market + enterprise buyers |
| Region Strategy | us-east-1 → eu-west-1 → ap-southeast-1 | Phased expansion |

See `/architecture/decision-log.md` for full ADR (Architecture Decision Records).
