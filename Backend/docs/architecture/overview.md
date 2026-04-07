# Architecture Overview
## AI Workflow Builder Platform — System Architecture v1.0
**Last updated:** 2026-04-07 — aligned with implemented codebase

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
║  Sub-Layer A: engine.config · engine.models · engine.errors · engine.ports   ║
║  Sub-Layer B: engine.graph · engine.nodes (17 types + registry)              ║
║  Sub-Layer C: engine.execution (orchestrator · state_machine · context ·     ║
║               retry_timeout · pii_scanner)                                   ║
║  Sub-Layer D: engine.chat · engine.providers · engine.sandbox                ║
║               engine.integrations · engine.cache · engine.auth               ║
║               engine.billing · engine.storage · engine.privacy               ║
║               engine.events · engine.observability · engine.scheduler        ║
║               engine.notifications · engine.health · engine.versioning       ║
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
workflow-worker (Celery)     Thin task shell — builds RunOrchestrator, calls .run()
       │ imports SDK
       ▼
workflow-engine (SDK)        DAG traversal via asyncio.gather() (one task per layer)
       │                     CodeExecutionNode: RestrictedPython sandbox (Tier 1)
       ▼
Isolated Execution           Tier 0 (direct) · Tier 1 (RestrictedPython)
                             Tier 2 (gVisor) · Tier 3 (Firecracker) — planned
       │
       ▼
LLM APIs / External APIs / Databases
```

---

## 6. Communication Patterns

### REST (Synchronous)
All CRUD operations, workflow saves, execution triggers. Every request authenticated via JWT Bearer or `X-API-Key` header. Structured JSON responses. SDK `ValidationError` maps to HTTP 422.

### WebSocket (Real-time)
`WS /api/v1/ws/executions/{run_id}` — WebSocket hub subscribes to Redis PubSub channel `run:{run_id}:events` and fans out typed events (`node_state`, `run_complete`, `run_waiting_human`) to the browser. Auth via `?token=<jwt>` query param (browsers cannot set Authorization headers on WS connections).

### Celery/Redis Queue (Async)
`execute_workflow.delay(run_id, tenant_id, workflow_id)` fires after API creates `ExecutionRun`. Five queues:
- `default` — workflow execution, cleanup
- `ai-heavy` — LLM-intensive node executions
- `critical` — webhook triggers, human node callbacks
- `scheduled` — cron-triggered workflow dispatch (beat fires every 30s)
- `DLQ` — dead-letter queue for exhausted retries

### Chat WebSocket
`WS /api/v1/chat/sessions/ws/chat/{session_id}` — Lightweight phase-signal streaming during AI workflow creation. Auth via `?token=<jwt>`. Rich payload (clarification questions, WorkflowDefinition) always fetched via REST — not sent over WS.

---

## 7. Technology Stack Summary

| Layer | Technology | Version |
|---|---|---|
| SDK Runtime | Python | 3.12+ |
| Domain Models | Pydantic | v2.x |
| HTTP Client | httpx | 0.27+ |
| MongoDB Driver | motor | 3.x |
| Redis Client | redis[asyncio] | 5.x |
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
