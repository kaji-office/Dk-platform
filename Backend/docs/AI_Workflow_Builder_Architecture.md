# AI Workflow Builder Platform — Architecture v4.0

## Engine-First Architecture: You Are Building Your Own SDK

> **The most important mental model:** `workflow-engine` is not a third-party dependency.
> **You are authoring it from scratch.** It is your proprietary Python library — your SDK.
> Everything else (API, Worker, CLI, UI) imports and consumes this SDK.

| | |
|---|---|
| **Core Principle** | `workflow-engine` is the product. API and UI are delivery mechanisms. |
| **SDK Distribution** | Internal pip package (monorepo). Published to PyPI or private registry when open-sourced. |
---

## Table of Contents

1. [What "SDK" Means Here — Mental Model](#1-what-sdk-means-here--mental-model)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Package Structure & Dependency Map](#3-package-structure--dependency-map)
4. [workflow-engine — The SDK (Core Library)](#4-workflow-engine--the-sdk-core-library)
   - 4.0 engine.config
   - 4.1 engine.models
   - 4.2 engine.dag
   - 4.3 engine.nodes
   - **4.3.1 Adding New Node Types in the Future**
   - 4.4 engine.validation
   - 4.5 engine.executor
   - 4.6 engine.state
   - 4.7 engine.context
   - 4.8 engine.sandbox
   - 4.9 engine.providers
   - 4.10 engine.integrations
   - 4.11 engine.cache
   - 4.12 engine.versioning
   - 4.13 engine.privacy
   - 4.14 engine.events
5. [workflow-api — FastAPI Backend](#5-workflow-api--fastapi-backend)
6. [workflow-worker — Celery Task Workers](#6-workflow-worker--celery-task-workers)
7. [workflow-cli — Command-Line Interface](#7-workflow-cli--command-line-interface)
8. [workflow-ui & @workflow/react — Frontend](#8-workflow-ui--workflowreact--frontend)
9. [Data Flow — End-to-End (23 Steps)](#9-data-flow--end-to-end-23-steps)
10. [Storage Architecture](#10-storage-architecture)
11. [Infrastructure & Observability](#11-infrastructure--observability)
12. [Testing Strategy](#12-testing-strategy)
13. [Technology Stack](#13-technology-stack)

---

## 1. What "SDK" Means Here — Mental Model

### 1.1 You Are Authoring the SDK

When you install `requests` or `pydantic`, you're consuming a library someone else wrote.
In this platform, **`workflow-engine` is the library you are writing from scratch.**

It is a standalone Python package with its own `pyproject.toml`. It can be:
- Installed via `pip install ./packages/workflow-engine` (local monorepo)
- Published to a private PyPI registry for external teams to consume
- Versioned independently (e.g., `workflow-engine==1.3.0`)

**The SDK contains all the intelligence of the platform.** It knows:
- What a workflow DAG is and how to parse it
- How to execute nodes in topological order (including parallel branches)
- What the 7 node types are and how each one behaves
- How to validate a workflow before saving it
- How to manage state transitions (PENDING → RUNNING → SUCCESS)
- How to call LLM providers (Gemini, Claude, OpenAI)
- How to sandbox user-provided Python code
- How to cache LLM responses semantically

**What the SDK does NOT know:**
- That FastAPI exists
- That Celery exists
- That Next.js exists
- Any HTTP request/response structure
- Any web framework concept

### 1.2 SDK Architecture Layers — Detailed Breakdown

The platform is organized into **5 distinct layers**. Understanding which layer each piece of code belongs to prevents logic from leaking into the wrong place.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  LAYER 5 — PRESENTATION                                                      ║
║  What the user sees and touches. No business logic here.                     ║
║                                                                              ║
║   workflow-ui (Next.js)          @workflow/react (npm)                       ║
║   ┌──────────────────────────────────────────────────────┐                  ║
║   │ WorkflowCanvas  NodePalette  RunMonitor  VersionHist │                  ║
║   │ NodeConfigPanel  ExecutionLog                        │                  ║
║   └──────────────────────────────────────────────────────┘                  ║
║   Communicates ONLY via HTTP/WebSocket. Never imports the SDK.               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 4 — DELIVERY (Consumer Services)                                      ║
║  Thin shells that receive requests and delegate entirely to the SDK.         ║
║  No workflow logic lives here — just transport, auth, and task dispatch.     ║
║                                                                              ║
║   workflow-api (FastAPI)    workflow-worker (Celery)    workflow-cli (Click) ║
║   ┌───────────────────┐     ┌──────────────────────┐   ┌────────────────┐   ║
║   │ routes/           │     │ tasks/               │   │ commands/      │   ║
║   │ websocket/        │     │   orchestrator.py    │   │   validate     │   ║
║   │ auth/             │     │   node_runner.py     │   │   deploy       │   ║
║   │ middleware/       │     │   cleanup.py         │   │   run          │   ║
║   │ dependencies.py   │     │ signals.py           │   │   logs         │   ║
║   └───────────────────┘     └──────────────────────┘   └────────────────┘   ║
║   All three import workflow-engine. All three are replaceable.               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 3 — SDK CORE (workflow-engine)  ◄── YOU BUILD THIS                   ║
║  The entire intelligence of the platform lives here.                         ║
║  Divided into 4 internal sub-layers:                                         ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  SDK SUB-LAYER A — DOMAIN MODELS  (everything depends on this)      │    ║
║  │                                                                     │    ║
║  │   engine.models                   engine.config                    │    ║
║  │   ┌─────────────────────────┐     ┌────────────────────────────┐   │    ║
║  │   │ WorkflowDefinition      │     │ EngineConfig               │   │    ║
║  │   │ NodeConfig / NodeType   │     │   mongodb_url              │   │    ║
║  │   │ EdgeConfig              │     │   redis_url                │   │    ║
║  │   │ ExecutionRun            │     │   gcs_bucket               │   │    ║
║  │   │ ExecutionStatus (enum)  │     │   sandbox_timeout_seconds  │   │    ║
║  │   │ NodeExecution           │     │   provider API keys        │   │    ║
║  │   │ WorkflowVersion         │     └────────────────────────────┘   │    ║
║  │   │ PortDefinition          │     Injected by consumer at startup.  │    ║
║  │   │ Tenant / PlanTier       │     SDK never reads env vars itself.  │    ║
║  │   │ LLMResponse / TokenUsage│                                       │    ║
║  │   │ DomainEvent subtypes    │                                       │    ║
║  │   │ Typed exception classes │                                       │    ║
║  │   └─────────────────────────┘                                       │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  SDK SUB-LAYER B — STRUCTURAL LOGIC  (DAG + Nodes + Validation)     │    ║
║  │  Understands workflow shape. Does NOT execute anything.             │    ║
║  │                                                                     │    ║
║  │   engine.dag            engine.nodes          engine.validation     │    ║
║  │   ┌──────────────┐      ┌──────────────────┐  ┌──────────────────┐  │    ║
║  │   │ DAGParser    │      │ NodeTypeRegistry  │  │ValidationPipeline│  │    ║
║  │   │ topo_sort    │      │ BaseNodeType(ABC) │  │ SchemaValidator  │  │    ║
║  │   │ parallel     │      │ AINodeType        │  │ CycleDetector    │  │    ║
║  │   │ ExecutionPlan│      │ MCPNodeType       │  │ PortChecker      │  │    ║
║  │   │ ExecutionStep│      │ APINodeType       │  │ PlanAccessChecker│  │    ║
║  │   │ StepType enum│      │ LogicNodeType     │  │ OrphanDetector   │  │    ║
║  │   └──────────────┘      │ TransformNodeType │  │ ExpressionValid. │  │    ║
║  │                         │ TriggerNodeType   │  └──────────────────┘  │    ║
║  │   API queries registry  │ HumanNodeType     │  API + CLI both call   │    ║
║  │   for UI palette.       │ CustomNodeType    │  validate() before     │    ║
║  │   Executor queries it   └──────────────────┘  saving or deploying.  │    ║
║  │   for execute() dispatch.                                            │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  SDK SUB-LAYER C — RUNTIME EXECUTION  (State + Executor + Context)  │    ║
║  │  Runs the workflow. Manages lifecycle. Passes data between nodes.   │    ║
║  │                                                                     │    ║
║  │  engine.executor     engine.state        engine.context             │    ║
║  │  ┌───────────────┐   ┌─────────────────┐ ┌────────────────────┐    │    ║
║  │  │RunOrchestrator│   │StateMachine     │ │ContextManager      │    │    ║
║  │  │NodeExecutor   │   │StateStore(Mongo)│ │RedisContextStore   │    │    ║
║  │  │NodeDispatcher │   │RUN_TRANSITIONS  │ │GCSContextStore     │    │    ║
║  │  │RetryHandler   │   │NODE_TRANSITIONS │ │InputResolver       │    │    ║
║  │  │TimeoutManager │   └─────────────────┘ └────────────────────┘    │    ║
║  │  └───────────────┘                                                  │    ║
║  │  Celery worker calls RunOrchestrator.run(). That's the only entry   │    ║
║  │  point from the delivery layer into runtime execution.              │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  SDK SUB-LAYER D — PLATFORM SERVICES  (cross-cutting concerns)      │    ║
║  │  Reusable capabilities called by executor and node types.           │    ║
║  │                                                                     │    ║
║  │  engine.providers  engine.integrations  engine.sandbox              │    ║
║  │  ┌─────────────┐   ┌─────────────────┐  ┌──────────────────────┐   │    ║
║  │  │BaseProvider │   │MCPClient        │  │SandboxManager        │   │    ║
║  │  │GeminiProvider   │ToolExecutor     │  │RestrictedPythonSandbox   │   ║
║  │  │AnthropicProv│   │RESTAdapter      │  │Tier2ContainerSandbox │   │    ║
║  │  │OpenAIProvider   │WebhookHandler   │  │Resource limits       │   │    ║
║  │  │TierRouter   │   │OAuthManager     │  └──────────────────────┘   │    ║
║  │  │RateLimiter  │   │AdapterRegistry  │                             │    ║
║  │  │ToolCalling  │   └─────────────────┘  engine.cache               │    ║
║  │  │TokenCounter │                        ┌──────────────────────┐   │    ║
║  │  └─────────────┘   engine.versioning    │SemanticCache         │   │    ║
║  │                    ┌─────────────────┐  │MCPResponseCache      │   │    ║
║  │  engine.privacy    │VersionManager   │  │KeySchema             │   │    ║
║  │  ┌─────────────┐   │Snapshot         │  └──────────────────────┘   │    ║
║  │  │PIIDetector  │   │VersionDiff      │                             │    ║
║  │  │PIIMasker    │   │VersionPinner    │  engine.events              │    ║
║  │  │GDPRHandler  │   └─────────────────┘  ┌──────────────────────┐  │    ║
║  │  └─────────────┘                        │EventBus              │  │    ║
║  │                                         │AuditLogger           │  │    ║
║  │                                         │MetricsHandler        │  │    ║
║  │                                         └──────────────────────┘  │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 2 — SDK DEPENDENCIES  (pip packages the SDK itself depends on)        ║
║  The SDK is allowed to depend ONLY on these. No web frameworks.              ║
║                                                                              ║
║   pydantic-v2   httpx   motor(async-mongo)   aioredis   tiktoken            ║
║   RestrictedPython   presidio-analyzer   google-cloud-storage               ║
║   asyncpg(pgvector)   mcp-sdk   authlib                                     ║
║                                                                              ║
║   FORBIDDEN in SDK's pyproject.toml:  fastapi  celery  click  starlette     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 1 — INFRASTRUCTURE  (external services the SDK talks to)              ║
║                                                                              ║
║   PostgreSQL+pgvector   MongoDB   Redis   GCS   Vertex AI   Anthropic API   ║
║   OpenAI API   MCP Servers   External REST APIs                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

**Layer responsibility rules (never violate these):**

| Rule | What it prevents |
|---|---|
| Layer 5 (UI) never imports the SDK | Frontend logic drift; JS reimplementing Python rules |
| Layer 4 (Delivery) contains no workflow logic | Duplicate execution paths; untestable business rules |
| SDK Sub-Layer A (Models) imports nothing from B/C/D | Circular imports; bloated model layer |
| SDK Sub-Layer B (Structural) never executes code | Mixing parsing with execution; hard to test |
| SDK Sub-Layer C (Runtime) never calls FastAPI/Celery | Framework lock-in; test brittleness |
| SDK Sub-Layer D (Services) never calls each other arbitrarily | Spaghetti dependencies; provider calling versioning, etc. |
| Layer 2 (SDK deps) excludes all web/task frameworks | Forces clean architecture boundary |

### 1.3 Why SDK-First Solves Real Problems

| If logic lived in... | The problem |
|---|---|
| The API service | CLI can't validate without making HTTP calls. Workers can't reuse logic. Testing requires a running server. |
| The Celery workers | API can't validate a workflow before dispatching. Huge round-trip cost for basic checks. |
| The UI (frontend) | Business rules drift between JS and Python. Bugs are guaranteed. Client-side security issues. |
| **The SDK (our approach)** | One codebase. API, workers, and CLI all import the same `validate()`, `execute()`, `parse()`. Test directly with `pytest`, no servers needed. |

### 1.4 The SDK as the DAG Knowledge Base

The UI creates a visual DAG (Directed Acyclic Graph). The user drags nodes and draws edges. This produces a JSON structure like:

```json
{
  "workflow_id": "send-welcome-email",
  "nodes": [
    { "id": "trigger-1", "type": "TRIGGER", "config": { "trigger_type": "webhook" } },
    { "id": "ai-1",      "type": "AI",      "config": { "model": "gemini-flash", "prompt_template": "Write a welcome email for {{input.name}}" } },
    { "id": "api-1",     "type": "API",     "config": { "url": "https://mail.service/send", "method": "POST" } }
  ],
  "edges": [
    { "source": "trigger-1", "source_port": "output", "target": "ai-1",  "target_port": "prompt" },
    { "source": "ai-1",      "source_port": "response", "target": "api-1", "target_port": "body" }
  ]
}
```

**The SDK is the only place that understands this JSON.** When the API receives this from the UI:
1. It calls `engine.validation.validate(definition)` — SDK parses and validates
2. It calls `engine.versioning.create_version(definition)` — SDK creates an immutable snapshot
3. When executing, it calls `engine.dag.DAGParser().parse(definition)` — SDK builds the execution plan

The worker uses the same SDK to actually execute every node. The CLI uses it to validate locally. One SDK, three consumers, zero duplication.

---

## 2. System Architecture Overview

### 2.1 Runtime Components

| Component | Process | Role | SDK Modules Used |
|---|---|---|---|
| **workflow-api** | FastAPI (uvicorn) | HTTP/WS endpoints, auth, rate limiting, tenant semaphore | `models`, `validation`, `dag`, `versioning`, `events`, `privacy`, `nodes.registry` |
| **workflow-worker** | Celery (N workers) | Executes nodes, manages run lifecycle, drives DAG | `executor`, `state`, `context`, `sandbox`, `providers`, `integrations`, `cache`, `dag` |
| **workflow-scheduler** | Celery beat | Cron triggers, scheduled workflow runs | `models`, `events` |
| **workflow-cli** | CLI process | Deploy, validate, run, tail logs locally | `models`, `validation`, `dag`, `versioning`, `nodes.registry` |
| **workflow-ui** | Next.js (Node.js) | Visual DAG editor, execution monitoring | None — calls API over HTTP/WS only |

### 2.2 Infrastructure Dependencies

| Service | Purpose | Used By |
|---|---|---|
| **PostgreSQL + pgvector** | Users, tenants, billing, semantic cache embeddings, credentials | workflow-api, workflow-engine (SDK) |
| **MongoDB** | Workflow definitions, versions, execution logs, audit trail | workflow-api, workflow-engine (SDK) |
| **Redis** | Task queue (Celery broker), rate limits, exec context (≤64KB), pub/sub, DLQ, semaphores | workflow-api, workflow-worker |
| **GCS** | Large node outputs (>64KB), uploaded files, exported bundles | workflow-engine SDK (context module) |
| **Kubernetes (GKE)** | Container orchestration, autoscaling | All services |

### 2.3 How the SDK Flows Through the System

```
User opens browser
       │
       ▼
workflow-ui (Next.js)           ← Renders DAG canvas via React Flow
       │ HTTP/WS
       ▼
workflow-api (FastAPI)          ← Thin HTTP shell
       │ imports SDK
       ▼
workflow-engine (YOUR SDK)      ← Validates, versions, parses DAG
       │ dispatches via Redis
       ▼
workflow-worker (Celery)        ← Thin task shell
       │ imports SDK
       ▼
workflow-engine (SAME SDK)      ← Actually executes nodes, manages state
       │
       ▼
LLM APIs / MCP Servers / External APIs / Databases
```

---

## 3. Package Structure & Dependency Map

```
ai-workflow-platform/
│
├── packages/
│   │
│   ├── workflow-engine/                  # ═══ YOUR SDK — BUILD THIS FIRST ═══
│   │   ├── pyproject.toml               # name = "workflow-engine", version = "1.0.0"
│   │   │                                # dependencies: pydantic, httpx, redis, motor, tiktoken
│   │   │                                # NO fastapi, NO celery, NO click
│   │   └── src/workflow_engine/
│   │       ├── __init__.py              # Public API re-exports (what consumers import)
│   │       ├── config.py                # EngineConfig — injected by consumers at startup
│   │       │
│   │       ├── models/                  # § 4.1 — All domain models (Pydantic v2)
│   │       │   ├── __init__.py
│   │       │   ├── workflow.py          #   WorkflowDefinition, WorkflowMetadata
│   │       │   ├── node.py              #   NodeConfig, NodeType enum, PortDefinition, EdgeConfig
│   │       │   ├── execution.py         #   ExecutionRun, NodeExecution, ExecutionStatus enum
│   │       │   ├── version.py           #   WorkflowVersion, VersionDiff, RollbackRecord
│   │       │   ├── trigger.py           #   TriggerConfig, WebhookTrigger, CronTrigger
│   │       │   ├── context.py           #   ExecutionContext, ContextRef
│   │       │   ├── events.py            #   DomainEvent subtypes (RunStarted, NodeCompleted, etc.)
│   │       │   ├── tenant.py            #   Tenant, Subscription, PlanTier enum
│   │       │   ├── provider.py          #   ProviderConfig, ModelTier enum, TokenUsage
│   │       │   └── errors.py            #   Typed exception hierarchy
│   │       │
│   │       ├── dag/                     # § 4.2 — DAG parser & resolver
│   │       │   ├── __init__.py
│   │       │   ├── parser.py            #   DAGParser — builds ExecutionPlan from WorkflowDefinition
│   │       │   ├── topo_sort.py         #   Kahn's algorithm — topological ordering
│   │       │   ├── parallel.py          #   Parallel branch detection & grouping
│   │       │   └── plan.py              #   ExecutionPlan, ExecutionStep, StepType enum
│   │       │
│   │       ├── nodes/                   # § 4.3 — Node type system (7 built-in types)
│   │       │   ├── __init__.py
│   │       │   ├── registry.py          #   NodeTypeRegistry (singleton) — source of truth
│   │       │   ├── base.py              #   BaseNodeType (ABC) — interface all nodes implement
│   │       │   ├── ai_node.py           #   AINodeType — LLM prompt/generation/extraction
│   │       │   ├── mcp_node.py          #   MCPNodeType — MCP server tool invocation
│   │       │   ├── api_node.py          #   APINodeType — HTTP/REST/GraphQL requests
│   │       │   ├── logic_node.py        #   LogicNodeType — If/Else, For-Each, Switch, Merge, Delay
│   │       │   ├── transform_node.py    #   TransformNodeType — JSON mapping, Python code
│   │       │   ├── trigger_node.py      #   TriggerNodeType — Webhook, Cron, Manual, Event
│   │       │   ├── human_node.py        #   HumanNodeType — Approval gates (pause + resume)
│   │       │   └── custom.py            #   CustomNodeType — user-defined extensions
│   │       │
│   │       ├── validation/              # § 4.4 — Workflow validation pipeline
│   │       │   ├── __init__.py
│   │       │   ├── pipeline.py          #   ValidationPipeline — runs all checks, collects all errors
│   │       │   ├── schema.py            #   SchemaValidator — per-node JSON schema check
│   │       │   ├── cycle_detector.py    #   CycleDetector — DFS-based DAG cycle detection
│   │       │   ├── port_checker.py      #   PortCompatibilityChecker — type-safe edge connections
│   │       │   ├── plan_checker.py      #   PlanAccessChecker — subscription plan gating
│   │       │   ├── orphan_detector.py   #   OrphanNodeDetector — no floating disconnected nodes
│   │       │   ├── duplicate_detector.py#   DuplicateIdDetector — unique node IDs
│   │       │   └── expression.py        #   ExpressionValidator — condition syntax validation
│   │       │
│   │       ├── executor/                # § 4.5 — Node execution orchestrator
│   │       │   ├── __init__.py
│   │       │   ├── orchestrator.py      #   RunOrchestrator — drives entire DAG run
│   │       │   ├── node_executor.py     #   NodeExecutor — executes a single node
│   │       │   ├── dispatcher.py        #   Dispatches node to correct handler by type
│   │       │   ├── retry.py             #   RetryHandler — exponential backoff + jitter
│   │       │   └── timeout.py           #   TimeoutManager — per-node execution timeouts
│   │       │
│   │       ├── state/                   # § 4.6 — Run & node state machine
│   │       │   ├── __init__.py
│   │       │   ├── machine.py           #   StateMachine — run + node state transitions
│   │       │   ├── transitions.py       #   Valid transition rules (enforced, no illegal jumps)
│   │       │   └── persistence.py       #   StateStore — persists state to MongoDB
│   │       │
│   │       ├── context/                 # § 4.7 — Execution context (inter-node data passing)
│   │       │   ├── __init__.py
│   │       │   ├── manager.py           #   ContextManager — store/load node outputs
│   │       │   ├── redis_store.py       #   Small outputs (≤64KB) stored in Redis (24h TTL)
│   │       │   ├── gcs_store.py         #   Large outputs (>64KB) stored in GCS
│   │       │   └── resolver.py          #   InputResolver — resolves upstream refs for a node
│   │       │
│   │       ├── sandbox/                 # § 4.8 — User code execution sandbox
│   │       │   ├── __init__.py
│   │       │   ├── manager.py           #   SandboxManager — tier selection and dispatch
│   │       │   ├── restricted.py        #   Tier 1: RestrictedPython (in-process, AST-level)
│   │       │   ├── container.py         #   Tier 2: gVisor ephemeral container (v3.2)
│   │       │   └── limits.py            #   Resource limits: timeout, memory, iteration count
│   │       │
│   │       ├── providers/               # § 4.9 — LLM provider abstraction
│   │       │   ├── __init__.py
│   │       │   ├── base.py              #   BaseProvider (ABC) — unified generate() interface
│   │       │   ├── registry.py          #   ProviderRegistry — maps model names to providers
│   │       │   ├── router.py            #   TierRouter — capability-based routing + fallback
│   │       │   ├── gemini.py            #   GeminiProvider — Vertex AI SDK wrapper
│   │       │   ├── anthropic.py         #   AnthropicProvider — Claude SDK wrapper
│   │       │   ├── openai.py            #   OpenAIProvider — OpenAI SDK wrapper
│   │       │   ├── tool_calling.py      #   ToolCallingProtocol — multi-turn tool use loop
│   │       │   ├── rate_limiter.py      #   ProviderRateLimiter — per-model RPM counter (Redis)
│   │       │   └── token_counter.py     #   Token counting + cost tracking (tiktoken)
│   │       │
│   │       ├── integrations/            # § 4.10 — MCP & external service adapters
│   │       │   ├── __init__.py
│   │       │   ├── mcp_client.py        #   MCPClient — connects to MCP server, discovers tools
│   │       │   ├── tool_executor.py     #   ToolExecutor — dispatches tool calls to MCP/REST
│   │       │   ├── rest_adapter.py      #   REST/GraphQL adapter with template-based auth
│   │       │   ├── webhook_handler.py   #   Webhook ingestion, HMAC validation, payload parsing
│   │       │   ├── oauth_manager.py     #   OAuth2 credential lifecycle (refresh, revoke)
│   │       │   └── adapter_registry.py  #   Plug-and-play adapter plugin interface
│   │       │
│   │       ├── cache/                   # § 4.11 — Caching layer
│   │       │   ├── __init__.py
│   │       │   ├── semantic.py          #   SemanticCache — pgvector cosine similarity cache
│   │       │   ├── mcp_cache.py         #   MCPResponseCache — TTL-based tool response cache
│   │       │   └── key_schema.py        #   Cache key patterns and TTL constants
│   │       │
│   │       ├── versioning/              # § 4.12 — Immutable workflow version control
│   │       │   ├── __init__.py
│   │       │   ├── manager.py           #   VersionManager — create, list, rollback
│   │       │   ├── snapshot.py          #   Snapshot — creates frozen immutable copy
│   │       │   ├── diff.py              #   VersionDiff — compute human-readable diff
│   │       │   └── pinning.py           #   VersionPinner — pins a version for execution
│   │       │
│   │       ├── privacy/                 # § 4.13 — PII detection & compliance
│   │       │   ├── __init__.py
│   │       │   ├── detector.py          #   PIIDetector — Presidio-based PII scanning
│   │       │   ├── masker.py            #   PIIMasker — mask/redact before logging
│   │       │   └── gdpr.py              #   GDPRHandler — deletion pipelines, data residency
│   │       │
│   │       └── events/                  # § 4.14 — Domain event bus
│   │           ├── __init__.py
│   │           ├── bus.py               #   EventBus — in-process publish/subscribe
│   │           ├── handlers.py          #   Built-in handlers (audit logger, metrics emitter)
│   │           └── audit.py             #   AuditLogger — append-only audit trail to MongoDB
│   │
│   ├── workflow-api/                    # ═══ FASTAPI SERVICE (thin consumer of SDK) ═══
│   │   ├── pyproject.toml               # depends on: workflow-engine
│   │   └── src/workflow_api/
│   │       ├── main.py                  # FastAPI app instance + lifespan hooks
│   │       ├── routes/                  # HTTP endpoint handlers
│   │       │   ├── workflows.py         #   CRUD: create, list, get, update, delete
│   │       │   ├── executions.py        #   Trigger run, get status, cancel, list history
│   │       │   ├── versions.py          #   List versions, get diff, rollback
│   │       │   ├── nodes.py             #   List node types, get schema, validate config
│   │       │   └── webhooks.py          #   Inbound webhook receiver endpoint
│   │       ├── websocket/               # Real-time event streaming
│   │       │   ├── hub.py               #   WebSocket hub (Redis Pub/Sub → WS client)
│   │       │   └── events.py            #   Typed WS event schema
│   │       ├── auth/                    # JWT validation, OAuth2 flows, API key management
│   │       ├── middleware/              # Rate limiting, tenant context injection, CORS
│   │       └── dependencies.py          # FastAPI DI: SDK config, DB sessions, semaphore
│   │
│   ├── workflow-worker/                 # ═══ CELERY WORKERS (thin consumer of SDK) ═══
│   │   ├── pyproject.toml               # depends on: workflow-engine
│   │   └── src/workflow_worker/
│   │       ├── celery_app.py            # Celery application config + broker URL
│   │       ├── tasks/
│   │       │   ├── orchestrator.py      #   Main task: receives run → calls SDK RunOrchestrator
│   │       │   ├── node_runner.py       #   Per-node task: calls SDK NodeExecutor (for parallel)
│   │       │   └── cleanup.py           #   Post-run: semaphore release, temp data cleanup
│   │       └── signals.py               # task_success/failure hooks → SDK state transitions
│   │
│   ├── workflow-cli/                    # ═══ CLI TOOL (thin consumer of SDK) ═══
│   │   ├── pyproject.toml               # depends on: workflow-engine
│   │   └── src/workflow_cli/
│   │       ├── main.py                  # Click entry point + command group
│   │       └── commands/
│   │           ├── deploy.py            #   YAML → SDK validate → API deploy call
│   │           ├── run.py               #   Trigger execution via API
│   │           ├── validate.py          #   SDK validate locally (NO API call needed)
│   │           ├── logs.py              #   Stream logs via WebSocket connection
│   │           └── versions.py          #   List / rollback via API
│   │
│   └── workflow-react/                  # ═══ REACT COMPONENT LIBRARY (npm package) ═══
│       ├── package.json                 # name: "@workflow/react"
│       └── src/
│           ├── WorkflowCanvas.tsx       # React Flow DAG editor canvas
│           ├── NodePalette.tsx          # Draggable node type sidebar
│           ├── RunMonitor.tsx           # Real-time execution overlay on canvas
│           ├── VersionHistory.tsx       # Version list + diff viewer + rollback button
│           ├── NodeConfigPanel.tsx      # Dynamic form generated from SDK node schema
│           └── ExecutionLog.tsx         # Scrolling per-node log stream
│
├── apps/
│   └── workflow-ui/                     # ═══ NEXT.JS APPLICATION ═══
│       ├── package.json                 # depends on: @workflow/react
│       └── src/app/                     # App Router pages and layouts
│
└── deploy/
    ├── docker/                          # Dockerfile per service (api, worker)
    ├── k8s/                             # Kubernetes manifests (deployments, services, HPA)
    └── terraform/                       # GKE, CloudSQL, Memorystore, GCS bucket IaC
```

---

## 4. workflow-engine — The SDK (Core Library)

> **This is the most important section.** You build every module in this section yourself.
> The SDK has zero knowledge of FastAPI, Celery, Click, or Next.js.
> All configuration (DB connections, Redis URLs, GCS credentials) is **injected by the consumer** at startup.

---

### 4.0 engine.config — Configuration Injection

**What it is:** A Pydantic settings class. Consumers (API, worker, CLI) create an `EngineConfig` instance with their environment variables and pass it into the SDK at startup. The SDK never reads env vars directly.

**Why it exists:** Allows the same SDK code to run in different environments (production API, local CLI, test suite) without modification.

**Must-have components:**

| Component | Type | Purpose |
|---|---|---|
| `EngineConfig` | `pydantic_settings.BaseSettings` | Master config class |
| `mongodb_url` | `str` | MongoDB connection URI |
| `postgres_url` | `str` | PostgreSQL connection URI (for cache embeddings) |
| `redis_url` | `str` | Redis connection URI |
| `gcs_bucket` | `str` | GCS bucket name for large outputs |
| `vertex_ai_project` | `str` | GCP project for Vertex AI (Gemini) |
| `anthropic_api_key` | `str` | Anthropic API key (Claude) |
| `openai_api_key` | `str` | OpenAI API key |
| `sandbox_timeout_seconds` | `int` | Max execution time for user code (default 30) |
| `sandbox_max_memory_mb` | `int` | Memory ceiling for sandbox (default 256) |
| `sandbox_max_iterations` | `int` | Loop guard for sandbox (default 10,000) |
| `context_inline_threshold_kb` | `int` | Size threshold: Redis vs GCS routing (default 64) |
| `provider_rate_limit_window` | `int` | RPM window in seconds (default 60) |

```python
# workflow_engine/config.py
from pydantic_settings import BaseSettings

class EngineConfig(BaseSettings):
    mongodb_url: str
    postgres_url: str
    redis_url: str
    gcs_bucket: str = "workflow-artifacts"
    vertex_ai_project: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    sandbox_timeout_seconds: int = 30
    sandbox_max_memory_mb: int = 256
    sandbox_max_iterations: int = 10_000
    context_inline_threshold_kb: int = 64

    class Config:
        env_file = ".env"
```

---

### 4.1 engine.models — Domain Models

**What it is:** All Pydantic v2 data models that represent the core domain objects. Every other SDK module uses these. They are the shared vocabulary of the entire system.

**Why it exists:** Enforces a single canonical shape for every data structure. When the API receives JSON from the UI, it deserializes into these models. When the worker executes a node, it reads from these models. No ambiguity.

**Must-have components:**

| File | Class | Key Fields |
|---|---|---|
| `workflow.py` | `WorkflowDefinition` | `workflow_id`, `name`, `nodes: list[NodeConfig]`, `edges: list[EdgeConfig]`, `retry_policy`, `failure_mode` |
| `workflow.py` | `WorkflowMetadata` | `created_at`, `updated_at`, `tenant_id`, `tags`, `description` |
| `node.py` | `NodeConfig` | `id`, `type: NodeType`, `config: dict`, `retry_policy`, `timeout_seconds` |
| `node.py` | `NodeType` | Enum: `TRIGGER`, `AI`, `MCP`, `API`, `LOGIC`, `TRANSFORM`, `HUMAN` |
| `node.py` | `PortDefinition` | `name`, `data_type: PortType`, `required: bool` |
| `node.py` | `EdgeConfig` | `source`, `source_port`, `target`, `target_port` |
| `execution.py` | `ExecutionRun` | `run_id`, `workflow_id`, `version`, `status: ExecutionStatus`, `tenant_id`, `trigger_input`, `started_at`, `completed_at`, `node_states: dict[str, NodeExecution]`, `context_refs` |
| `execution.py` | `NodeExecution` | `node_id`, `status: NodeStatus`, `attempt`, `started_at`, `completed_at`, `duration_ms`, `error` |
| `execution.py` | `ExecutionStatus` | Enum: `PENDING`, `QUEUED`, `RUNNING`, `SUCCESS`, `FAILED`, `CANCELLED` |
| `execution.py` | `NodeStatus` | Enum: `PENDING`, `RUNNING`, `RETRYING`, `SUCCESS`, `FAILED`, `SKIPPED` |
| `version.py` | `WorkflowVersion` | `version_number`, `workflow_id`, `snapshot: WorkflowDefinition`, `created_at`, `created_by`, `is_frozen: bool` |
| `version.py` | `VersionDiff` | `from_version`, `to_version`, `added_nodes`, `removed_nodes`, `changed_nodes`, `changed_edges` |
| `trigger.py` | `TriggerConfig` | `trigger_type`, `path`, `cron_expr`, `event_name` |
| `context.py` | `ExecutionContext` | `run_id`, `node_id`, `tenant_id`, `config: EngineConfig`, `sandbox`, `cache`, `rate_limiter`, `provider_registry`, `tool_calling` |
| `context.py` | `ContextRef` | `uri` (redis:// or gcs://), `size_bytes` |
| `events.py` | `DomainEvent` (base) | `event_id`, `event_type`, `run_id`, `tenant_id`, `timestamp` |
| `events.py` | `RunStarted`, `RunCompleted`, `RunFailed` | Run lifecycle events |
| `events.py` | `NodeStarted`, `NodeCompleted`, `NodeFailed` | Node lifecycle events |
| `tenant.py` | `Tenant` | `tenant_id`, `plan: PlanTier`, `max_concurrent_runs`, `api_key_hash` |
| `tenant.py` | `PlanTier` | Enum: `FREE`, `PRO`, `ENTERPRISE` |
| `provider.py` | `LLMResponse` | `text`, `structured_output`, `tool_calls`, `token_usage: TokenUsage`, `cost`, `finish_reason` |
| `provider.py` | `TokenUsage` | `input_tokens`, `output_tokens`, `total_tokens` |
| `errors.py` | Exception hierarchy | `EngineError`, `ValidationError`, `CycleDetectedError`, `NodeExecutionError`, `ProviderRateLimitError`, `SandboxTimeoutError`, `PortMismatchError` |

---

### 4.2 engine.dag — DAG Parser & Resolver

**What it is:** Takes a `WorkflowDefinition` (nodes + edges) and produces an `ExecutionPlan` — an ordered list of steps that tells the executor exactly what to run and in what order.

**Why it exists:** The executor doesn't need to think about topology. It just walks the plan. Parallel branches are detected here and expressed as `PARALLEL` steps, which the worker converts to Celery `group()` calls.

**Must-have components:**

| File | Class/Function | Responsibility |
|---|---|---|
| `parser.py` | `DAGParser.parse(definition)` | Orchestrates topo sort + parallel detection → returns `ExecutionPlan` |
| `topo_sort.py` | `topological_sort(nodes, adj, in_degrees)` | Kahn's BFS algorithm — produces linear order from DAG |
| `topo_sort.py` | `_compute_adjacency(definition)` | Builds `{node_id: [target_ids]}` adjacency map from edges |
| `topo_sort.py` | `_compute_in_degrees(nodes, adj)` | Counts incoming edges per node for Kahn's algorithm |
| `parallel.py` | `detect_parallel_groups(topo_order, adj)` | Finds sibling nodes (same depth, no dependency between them) |
| `parallel.py` | `detect_fan_in_points(groups, adj)` | Finds nodes that wait for multiple parallel branches |
| `plan.py` | `StepType` | Enum: `SEQUENTIAL`, `PARALLEL`, `FAN_IN` |
| `plan.py` | `ExecutionStep` | `node_ids: list[str]`, `step_type: StepType` |
| `plan.py` | `ExecutionPlan` | `steps: list[ExecutionStep]`, `fan_out_points`, `fan_in_points`, `get_ready_nodes(completed)` |

**Example output for a workflow with parallel branches:**

```
Input:  trigger → [ai_node, api_node] → merge_node
Output: ExecutionPlan(
  steps=[
    ExecutionStep(node_ids=["trigger"],          step_type=SEQUENTIAL),
    ExecutionStep(node_ids=["ai_node","api_node"], step_type=PARALLEL),
    ExecutionStep(node_ids=["merge_node"],        step_type=FAN_IN),
  ]
)
```

---

### 4.3 engine.nodes — Node Type System

**What it is:** Defines the 7 built-in node types. Each type has a config schema (used to generate UI forms), port definitions (used for edge type-checking), and an `execute()` method (called at runtime).

**Why it exists:** The node registry is the single source of truth for what node types exist. The API queries it to populate the node palette in the UI. The validator uses it to check port types. The executor uses it to run nodes.

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `registry.py` | `NodeTypeRegistry` | Singleton. Registers all node types. Used by API, validator, executor, CLI. |
| `registry.py` | `.register(node_type)` | Add a node type (built-in or custom extension) |
| `registry.py` | `.get(type_name)` | Look up a node type by `NodeType` enum value |
| `registry.py` | `.list_all()` | Return all types (for UI palette endpoint) |
| `registry.py` | `.get_config_schema(type_name)` | Return JSON Schema for config panel generation |
| `registry.py` | `.get_ports(type_name)` | Return `(input_ports, output_ports)` tuple |
| `base.py` | `BaseNodeType` (ABC) | Abstract interface: `name`, `display_name`, `category`, `description`, `input_ports`, `output_ports`, `config_schema`, `min_plan`, `sandbox_tier`, `async execute(config, inputs, ctx) → dict`, `validate_config(config) → list[str]` |
| `ai_node.py` | `AINodeType` | Cache check → rate limit → LLM call → cache store → token tracking |
| `mcp_node.py` | `MCPNodeType` | Discover tool schema → build params → call MCP server → parse response |
| `api_node.py` | `APINodeType` | Render URL/headers/body templates → resolve auth → HTTP call → parse response |
| `logic_node.py` | `LogicNodeType` | Evaluate condition → route to `true_output` or `false_output` port |
| `transform_node.py` | `TransformNodeType` | Run Python in sandbox OR render Jinja2 template |
| `trigger_node.py` | `TriggerNodeType` | Produces initial payload (executed by scheduler/webhook handler) |
| `human_node.py` | `HumanNodeType` | Pause run, notify assignee, wait for form submission, resume |
| `custom.py` | `CustomNodeType` | Plugin interface for user-defined node types |

**Node type config schemas (used for dynamic UI form generation):**

| Node Type | Required Config | Optional Config |
|---|---|---|
| `AI` | `model`, `prompt_template` | `output_schema`, `tools_enabled`, `temperature`, `max_tokens` |
| `MCP` | `server_url`, `tool_name` | `params_template`, `auth_config` |
| `API` | `url`, `method` | `headers`, `body_template`, `auth_type`, `timeout_seconds` |
| `LOGIC` | `logic_type` | `condition` (if_else/switch), `delay_seconds` (delay), `item_path` (for_each) |
| `TRANSFORM` | — | `code` (Python), `template` (Jinja2) |
| `TRIGGER` | `trigger_type` | `path` (webhook), `cron_expr` (cron), `event_name` (event) |
| `HUMAN` | `assignee` | `form_schema`, `timeout_hours`, `escalation_policy` |

---

### 4.3.1 Adding New Node Types in the Future

This section is the **complete playbook** for every time you or your team needs to introduce a new node type — whether it's a built-in type added to the SDK, a tenant-specific custom node, or a plugin published by a third party.

The SDK is designed so that adding a new node type **never requires changes to the executor, the DAG parser, the state machine, or the validation pipeline**. You only touch the nodes layer, the models layer, and the UI layer. Everything else picks it up automatically via the registry.

---

#### Step 0 — Decide Which Node Category It Belongs To

Before writing code, classify the new node:

| Category | Example New Nodes | SDK Sub-Layer |
|---|---|---|
| **AI** | Image generation node, audio transcription node, embedding node | Sub-Layer D (providers) |
| **Integration** | Database query node, Slack message node, email send node | Sub-Layer D (integrations) |
| **Logic/Control** | Rate-limit gate node, circuit-breaker node, A/B split node | Sub-Layer B (nodes) |
| **Data** | CSV parser node, XML transform node, schema validator node | Sub-Layer B (nodes) |
| **Human/Approval** | Multi-approver node, SLA-timer node | Sub-Layer B (nodes) |
| **Custom (tenant)** | Any node a tenant writes for their own workflow | Plugin layer |

---

#### Step 1 — Add the NodeType Enum Value

Open `workflow_engine/models/node.py`. Add your new type to the `NodeType` enum:

```python
# workflow_engine/models/node.py

class NodeType(str, Enum):
    TRIGGER   = "TRIGGER"
    AI        = "AI"
    MCP       = "MCP"
    API       = "API"
    LOGIC     = "LOGIC"
    TRANSFORM = "TRANSFORM"
    HUMAN     = "HUMAN"
    # ─── ADD YOUR NEW TYPE HERE ───
    DATABASE  = "DATABASE"   # ← example: new database query node
    EMAIL     = "EMAIL"      # ← example: new email send node
```

**Rule:** The enum value is what gets stored in MongoDB and sent in workflow JSON. Once published, never rename it — it would break all existing saved workflows that use it.

---

#### Step 2 — Create the Node File

Create a new file in `workflow_engine/nodes/`. The filename convention is `{type_name}_node.py`.

```
workflow_engine/nodes/
├── database_node.py    ← new file you create
├── email_node.py       ← new file you create
```

Every new node file must implement `BaseNodeType`. Here is the complete contract:

```python
# workflow_engine/nodes/database_node.py

from workflow_engine.nodes.base import BaseNodeType
from workflow_engine.models.node import NodeType, PortDefinition, PortType
from workflow_engine.models.tenant import PlanTier
from workflow_engine.models.context import ExecutionContext


class DatabaseNodeType(BaseNodeType):
    # ── IDENTITY ──────────────────────────────────────────────────
    name         = NodeType.DATABASE          # must match the enum value you added
    display_name = "Database Query"           # shown in UI node palette
    category     = "Integration"              # UI palette grouping
    description  = "Run a SQL query against a connected database and return results as JSON"
    min_plan     = PlanTier.PRO               # FREE / PRO / ENTERPRISE
    sandbox_tier = None                       # set to SandboxTier.TIER_1 if node runs user code

    # ── PORTS ─────────────────────────────────────────────────────
    # Ports define what edges can connect to/from this node in the UI.
    # The port_checker uses these to validate edge type compatibility.
    input_ports = [
        PortDefinition(name="query_params", data_type=PortType.JSON,  required=False),
        PortDefinition(name="limit",        data_type=PortType.INT,   required=False),
    ]
    output_ports = [
        PortDefinition(name="rows",         data_type=PortType.ARRAY),
        PortDefinition(name="row_count",    data_type=PortType.INT),
        PortDefinition(name="error",        data_type=PortType.TEXT),
    ]

    # ── CONFIG SCHEMA ─────────────────────────────────────────────
    # This JSON Schema is served by GET /api/v2/nodes/types/DATABASE/schema
    # The UI's NodeConfigPanel renders a form from this automatically.
    # Add every config field the user can set in the panel here.
    config_schema = {
        "type": "object",
        "properties": {
            "connection_id": {
                "type": "string",
                "description": "ID of the saved database credential in the tenant's vault"
            },
            "query_template": {
                "type": "string",
                "description": "SQL query with Jinja2 variable refs e.g. SELECT * FROM users WHERE id = {{input.user_id}}"
            },
            "database_type": {
                "type": "string",
                "enum": ["postgresql", "mysql", "sqlite"],
                "default": "postgresql"
            },
            "timeout_seconds": {
                "type": "integer",
                "default": 30,
                "minimum": 1,
                "maximum": 300
            },
        },
        "required": ["connection_id", "query_template"],
    }

    # ── CUSTOM VALIDATION (optional) ──────────────────────────────
    # Called by SchemaValidator during ValidationPipeline.
    # Return a list of error strings (empty = valid).
    # Use this for cross-field validation that JSON Schema can't express.
    def validate_config(self, config: dict) -> list[str]:
        errors = super().validate_config(config)  # runs JSON Schema check
        if "{{" not in config.get("query_template", ""):
            errors.append("DATABASE node: query_template has no template variables — consider using a static query node instead")
        return errors

    # ── EXECUTION ─────────────────────────────────────────────────
    # Called by NodeExecutor at runtime.
    # inputs:  dict keyed by input port names (values resolved from upstream nodes)
    # config:  dict of user-configured settings (from config_schema)
    # ctx:     ExecutionContext — access to sandbox, cache, rate_limiter, providers, etc.
    # Returns: dict keyed by output port names
    async def execute(self, config: dict, inputs: dict, ctx: ExecutionContext) -> dict:
        # 1. Resolve credentials from tenant vault
        credentials = await ctx.integrations.oauth_manager.get_credentials(
            integration_id=config["connection_id"],
            tenant_id=ctx.tenant_id,
        )

        # 2. Render query template with inputs
        query = render_template(config["query_template"], inputs)

        # 3. Execute via REST adapter (or a dedicated DB adapter)
        adapter = ctx.integrations.rest_adapter
        result = await adapter.call(
            config={
                "url": credentials.connection_string,
                "method": "POST",
                "body_template": '{"query": "{{ query }}", "params": {{ params }}}',
                "timeout_seconds": config.get("timeout_seconds", 30),
            },
            inputs={"query": query, "params": inputs.get("query_params", {})},
        )

        # 4. Return keyed by output port names
        return {
            "rows":      result.get("data", []),
            "row_count": len(result.get("data", [])),
            "error":     result.get("error", ""),
        }
```

---

#### Step 3 — Register the Node in the Registry

Open `workflow_engine/nodes/registry.py`. Import your new class and register it in `__init__`:

```python
# workflow_engine/nodes/registry.py

from workflow_engine.nodes.ai_node        import AINodeType
from workflow_engine.nodes.mcp_node       import MCPNodeType
from workflow_engine.nodes.api_node       import APINodeType
from workflow_engine.nodes.logic_node     import LogicNodeType
from workflow_engine.nodes.transform_node import TransformNodeType
from workflow_engine.nodes.trigger_node   import TriggerNodeType
from workflow_engine.nodes.human_node     import HumanNodeType
# ─── ADD YOUR IMPORT HERE ───────────────────────────────────────
from workflow_engine.nodes.database_node  import DatabaseNodeType
from workflow_engine.nodes.email_node     import EmailNodeType

class NodeTypeRegistry:
    def __init__(self):
        self._types: dict[NodeType, BaseNodeType] = {}
        # Built-in types
        self.register(AINodeType())
        self.register(MCPNodeType())
        self.register(APINodeType())
        self.register(LogicNodeType())
        self.register(TransformNodeType())
        self.register(TriggerNodeType())
        self.register(HumanNodeType())
        # ─── ADD YOUR REGISTRATION HERE ─────────────────────────
        self.register(DatabaseNodeType())
        self.register(EmailNodeType())
```

**That's it for the SDK.** The registry is the only file that changes outside your new node file. The executor, validation pipeline, DAG parser, and state machine all discover the new type automatically.

---

#### Step 4 — Update the Validation Pipeline (if needed)

The `ValidationPipeline` runs `SchemaValidator` against every node's config. Because your node defined a `config_schema`, this works automatically with **zero changes** to `validation/`.

The only time you need to touch validation is:

| Scenario | What to add |
|---|---|
| New node needs a cross-field validation rule | Override `validate_config()` in your node class (Step 2 above) |
| New node requires a new plan tier | Add the tier to `PlanTier` enum in `models/tenant.py` and update `PlanAccessChecker` |
| New node introduces a new port data type | Add the type to `PortType` enum and update the compatibility matrix in `port_checker.py` |

---

#### Step 5 — Update the UI (Frontend)

The UI does **not** need hardcoded knowledge of node types. It discovers them from the API:

```
GET /api/v2/nodes/types
→ API calls engine.nodes.registry.list_all()
→ Returns all registered types including your new DATABASE node
→ UI renders it in the NodePalette automatically
```

```
GET /api/v2/nodes/types/DATABASE/schema
→ API calls engine.nodes.registry.get_config_schema("DATABASE")
→ Returns your config_schema JSON Schema
→ UI's NodeConfigPanel renders a form from it automatically
```

**You only need to add custom UI code if:**

| Scenario | What to build |
|---|---|
| Custom visual appearance on the canvas | Add a React Flow custom node renderer in `@workflow/react` |
| Custom config panel widget (e.g., a SQL editor instead of a textarea) | Add a custom panel component in `NodeConfigPanel.tsx` keyed by node type |
| Special edge rendering (e.g., conditional branch labels) | Add an edge label renderer in `WorkflowCanvas.tsx` |

For most new nodes, the default form renderer from the JSON Schema is sufficient and requires no frontend changes.

---

#### Step 6 — Write Tests

SDK tests run directly against the library — no HTTP server, no Celery, no database (for unit tests):

```python
# packages/workflow-engine/tests/test_nodes/test_database_node.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from workflow_engine.nodes.database_node import DatabaseNodeType
from workflow_engine.models.node import NodeType
from workflow_engine.models.tenant import PlanTier


class TestDatabaseNodeType:

    def test_metadata(self):
        node = DatabaseNodeType()
        assert node.name == NodeType.DATABASE
        assert node.min_plan == PlanTier.PRO
        assert len(node.input_ports) == 2
        assert len(node.output_ports) == 3

    def test_config_schema_requires_connection_id_and_query(self):
        node = DatabaseNodeType()
        schema = node.config_schema
        assert "connection_id" in schema["required"]
        assert "query_template" in schema["required"]

    def test_validate_config_warns_on_static_query(self):
        node = DatabaseNodeType()
        errors = node.validate_config({
            "connection_id": "db-prod",
            "query_template": "SELECT * FROM users",  # no {{ }} variables
        })
        assert any("no template variables" in e for e in errors)

    @pytest.mark.asyncio
    async def test_execute_returns_rows_and_count(self):
        node = DatabaseNodeType()

        # Mock the execution context
        ctx = MagicMock()
        ctx.tenant_id = "tenant-123"
        ctx.integrations.oauth_manager.get_credentials = AsyncMock(return_value=MagicMock(
            connection_string="postgresql://..."
        ))
        ctx.integrations.rest_adapter.call = AsyncMock(return_value={
            "data": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            "error": "",
        })

        result = await node.execute(
            config={"connection_id": "db-prod", "query_template": "SELECT * FROM users WHERE id = {{input.user_id}}"},
            inputs={"query_params": {"user_id": 1}},
            ctx=ctx,
        )

        assert result["row_count"] == 2
        assert result["rows"][0]["name"] == "Alice"
        assert result["error"] == ""
```

Also add an integration test to confirm the registry picks it up:

```python
# packages/workflow-engine/tests/test_nodes/test_registry.py

def test_registry_includes_database_node():
    registry = NodeTypeRegistry()
    node_type = registry.get(NodeType.DATABASE)
    assert node_type.display_name == "Database Query"

def test_registry_list_all_includes_database():
    registry = NodeTypeRegistry()
    types = [nt.name for nt in registry.list_all()]
    assert NodeType.DATABASE in types
```

---

#### Step 7 — Version and Deploy

Because the new node type is a change to the SDK, it requires a version bump:

```toml
# packages/workflow-engine/pyproject.toml
[project]
name = "workflow-engine"
version = "1.1.0"   # bump minor version for new node type
```

Then redeploy all three consumers (API, worker, CLI) so they all run the same SDK version. The new node appears in the palette immediately after deployment.

---

#### Summary — Complete Checklist for Adding a New Node

```
□ Step 0  Classify the node (AI / Integration / Logic / Data / Human / Custom)
□ Step 1  Add NodeType.YOUR_TYPE to models/node.py NodeType enum
□ Step 2  Create packages/workflow-engine/src/workflow_engine/nodes/your_node.py
            □ Set: name, display_name, category, description, min_plan
            □ Define: input_ports (list[PortDefinition])
            □ Define: output_ports (list[PortDefinition])
            □ Define: config_schema (JSON Schema dict)
            □ Override: validate_config() if cross-field rules needed
            □ Implement: async execute(config, inputs, ctx) → dict
□ Step 3  Register in NodeTypeRegistry.__init__() in nodes/registry.py
□ Step 4  Add validation rules only if needed (new port type / new plan tier)
□ Step 5  Add custom UI only if needed (most nodes work with auto-generated form)
□ Step 6  Write unit tests (metadata, config schema, execute mock)
            Write registry test (get() + list_all())
□ Step 7  Bump SDK version, redeploy API + Worker + CLI
```

**What you do NOT need to change when adding a new node:**

| Component | Why it's untouched |
|---|---|
| `engine.dag` | Topology parsing is node-type agnostic |
| `engine.executor` (RunOrchestrator) | Walks the plan; dispatches to registry; registry handles it |
| `engine.state` | State transitions are run/node lifecycle, not node-type specific |
| `engine.context` | Input/output storage is port-based, not node-type specific |
| `workflow-api` routes | GET /nodes/types auto-serves from registry; no route changes needed |
| `workflow-worker` tasks | orchestrate_run delegates to executor; executor delegates to registry |
| `workflow-cli` validate command | ValidationPipeline discovers new node via registry |

---

### 4.3.2 Plugin System — Third-Party & Tenant Custom Nodes

For nodes that should not live inside the SDK itself (tenant-specific logic, third-party integrations), the SDK exposes a plugin registration API:

```python
# workflow_engine/nodes/custom.py

class CustomNodePlugin:
    """
    Interface for registering external node types into the SDK registry
    without modifying SDK source code.

    Usage (in a tenant's custom plugin package):

        from workflow_engine.nodes.custom import CustomNodePlugin
        from workflow_engine.nodes.registry import NodeTypeRegistry

        class MyTenantNode(CustomNodePlugin):
            name         = "TENANT_CRMSYNC"
            display_name = "CRM Sync"
            category     = "Integration"
            # ... ports, config_schema, execute() ...

        # In the consumer (API/worker startup):
        registry = NodeTypeRegistry()
        registry.register_plugin(MyTenantNode())
    """

    @abstractmethod
    async def execute(self, config: dict, inputs: dict, ctx: ExecutionContext) -> dict:
        ...
```

Plugins can be:
- **Tenant-scoped** — registered only for a specific tenant at worker startup (loaded from tenant config in MongoDB)
- **Platform-wide** — registered at SDK init level; available to all tenants
- **PyPI packages** — external packages that implement `CustomNodePlugin` and are installed into the worker Docker image

---

**What it is:** A pipeline that runs a series of checkers against a `WorkflowDefinition` and returns all errors at once (not just the first). Consumers (API + CLI) both use this before saving or deploying.

**Why it exists:** Prevents invalid workflows from ever being saved or executed. The CLI can validate a YAML file locally without any API call. The same logic runs server-side, ensuring consistency.

**Must-have components:**

| File | Class | Checks Performed |
|---|---|---|
| `pipeline.py` | `ValidationPipeline.validate(definition, tenant)` | Orchestrates all checkers, collects and returns all error messages |
| `schema.py` | `SchemaValidator` | Each node's `config` dict matches its type's `config_schema` (jsonschema validation) |
| `cycle_detector.py` | `CycleDetector` | DFS-based cycle detection — edges must form a DAG |
| `port_checker.py` | `PortCompatibilityChecker` | Connected ports have compatible `PortType` values (type compatibility matrix) |
| `plan_checker.py` | `PlanAccessChecker` | Node types available on the tenant's `PlanTier` (e.g., HUMAN node requires PRO plan) |
| `orphan_detector.py` | `OrphanNodeDetector` | Every non-trigger node has at least one incoming edge |
| `duplicate_detector.py` | `DuplicateIdDetector` | No two nodes share the same `id` |
| `expression.py` | `ExpressionValidator` | Condition expressions in LOGIC nodes are syntactically valid Python/Jinja2 |

**Port type compatibility matrix:**

```
ANY   → accepts: TEXT, JSON, ARRAY, INT, FLOAT, BOOL, ANY
TEXT  → accepts: TEXT, ANY
JSON  → accepts: JSON, ANY
ARRAY → accepts: ARRAY, JSON, ANY
INT   → accepts: INT, FLOAT, ANY
FLOAT → accepts: FLOAT, ANY
BOOL  → accepts: BOOL, ANY
```

**Consumer usage example:**

```python
# In workflow-api (server-side save):
from workflow_engine.validation import ValidationPipeline
from workflow_engine.nodes import NodeTypeRegistry

pipeline = ValidationPipeline(NodeTypeRegistry())
errors = pipeline.validate(definition, tenant=current_tenant)
if errors:
    raise HTTPException(422, detail={"validation_errors": errors})

# In workflow-cli (local, no network):
from workflow_engine.validation import ValidationPipeline
errors = pipeline.validate(WorkflowDefinition.from_yaml("./flow.yaml"))
```

---

### 4.5 engine.executor — Node Execution Orchestrator

**What it is:** The execution engine. `RunOrchestrator` drives a complete workflow run from start to finish. `NodeExecutor` executes a single node. The Celery worker is a thin wrapper that creates and calls the orchestrator.

**Why it exists:** All execution logic lives here, not in Celery tasks. This means the orchestration logic can be tested directly without a Celery broker, and can be reused by any future consumer (e.g., a streaming API endpoint).

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `orchestrator.py` | `RunOrchestrator` | Drives full workflow run: parse plan → walk steps → execute each step → manage state |
| `orchestrator.py` | `RunOrchestrator.run(run, definition)` | Entry point: transition to RUNNING → walk plan → handle success/failure |
| `orchestrator.py` | `_execute_single(run, definition, node_id)` | Execute one node with retry loop |
| `orchestrator.py` | `_execute_parallel(run, definition, node_ids)` | Execute multiple nodes concurrently (asyncio.gather) |
| `node_executor.py` | `NodeExecutor.execute(node_config, inputs, run)` | Look up type in registry → build ExecutionContext → call `node_type.execute()` |
| `dispatcher.py` | `NodeDispatcher` | Routes execution to correct node handler based on `NodeType` |
| `retry.py` | `RetryHandler.compute_backoff(policy, attempt)` | Exponential backoff with jitter |
| `timeout.py` | `TimeoutManager.wrap(coro, timeout_seconds)` | Cancels coroutine if it exceeds per-node timeout |

**Retry policy model:**

```python
class RetryPolicy(BaseModel):
    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 60.0
    jitter: bool = True
    retryable_errors: list[str] = ["ProviderRateLimitError", "TimeoutError"]
```

**Failure modes:**

| Mode | Behaviour |
|---|---|
| `FAIL_ALL` (default) | Any node failure cancels the entire run |
| `SKIP_AND_CONTINUE` | Failed node is marked SKIPPED; its downstream nodes are also skipped; run continues via other branches |
| `FAIL_BRANCH` | Only the failed branch stops; parallel branches continue |

---

### 4.6 engine.state — State Machine

**What it is:** Manages and enforces lifecycle state transitions for both runs and individual nodes. Persists all state changes to MongoDB with optimistic locking.

**Why it exists:** State transitions must be atomic and auditable. An invalid transition (e.g., FAILED → SUCCESS) must be rejected. All state changes are persisted immediately and consistently.

**Must-have components:**

| File | Class/Object | Responsibility |
|---|---|---|
| `machine.py` | `StateMachine` | Validates and applies state transitions for runs and nodes |
| `machine.py` | `StateMachine.transition_run(run_id, new_status, error?)` | Run-level transition with timestamp recording |
| `machine.py` | `StateMachine.transition_node(run_id, node_id, new_status, error?)` | Node-level transition with attempt counter and duration recording |
| `transitions.py` | `RUN_TRANSITIONS: dict` | Valid transitions for `ExecutionStatus` (enforced as allowlist) |
| `transitions.py` | `NODE_TRANSITIONS: dict` | Valid transitions for `NodeStatus` (enforced as allowlist) |
| `persistence.py` | `StateStore` | MongoDB read/write with optimistic locking via `version` field |
| `persistence.py` | `StateStore.get_run(run_id)` | Load current run state |
| `persistence.py` | `StateStore.save_run(run)` | Persist updated run state |

**Valid transition tables:**

```
# Run transitions:
PENDING   → QUEUED, CANCELLED
QUEUED    → RUNNING, CANCELLED
RUNNING   → SUCCESS, FAILED, CANCELLED
SUCCESS   → (terminal)
FAILED    → (terminal)
CANCELLED → (terminal)

# Node transitions:
PENDING   → RUNNING, SKIPPED
RUNNING   → SUCCESS, FAILED, RETRYING
RETRYING  → RUNNING
SUCCESS   → (terminal)
FAILED    → (terminal)
SKIPPED   → (terminal)
```

---

### 4.7 engine.context — Execution Context Manager

**What it is:** Manages how node outputs are stored and how downstream nodes receive inputs. Routes output storage between Redis (small outputs) and GCS (large outputs). Resolves upstream references when a node is about to execute.

**Why it exists:** Nodes don't pass data directly to each other — there's no in-memory pipeline. Each node stores its output via the context manager, and downstream nodes load only the fields they need. This works across workers, time gaps, and retries.

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `manager.py` | `ContextManager` | Routes output storage + loads upstream inputs |
| `manager.py` | `store_output(run_id, node_id, output: dict) → ContextRef` | Serialise output → route to Redis or GCS based on size |
| `manager.py` | `load_output(ref: ContextRef) → dict` | Load from Redis or GCS based on URI scheme |
| `manager.py` | `resolve_inputs(run_id, node_id, definition) → dict` | Walk edges, load all upstream outputs, assemble input dict by port name |
| `redis_store.py` | `RedisContextStore` | `set(key, value, ttl)`, `get(key)`, `delete(key)` |
| `gcs_store.py` | `GCSContextStore` | `upload(path, data)`, `download(path) → bytes` |
| `resolver.py` | `InputResolver` | Traverses edge definitions, maps `source_port → target_port` values |

**Storage routing logic:**

```
serialized = json.dumps(output).encode()
if len(serialized) <= threshold_bytes:   # default: 64KB
    store in Redis  →  ContextRef(uri="redis://ctx:{run_id}:{node_id}")
else:
    store in GCS    →  ContextRef(uri="gcs://{run_id}/{node_id}/output.json")
```

---

### 4.8 engine.sandbox — Code Execution Sandbox

**What it is:** Executes user-provided Python code (from TRANSFORM nodes) in a restricted, resource-limited environment. Prevents access to the file system, network, and dangerous built-ins.

**Why it exists:** TRANSFORM nodes allow users to write Python code. This code must not be able to read files, make network requests, exhaust memory, or run infinite loops.

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `manager.py` | `SandboxManager` | Selects tier and dispatches execution |
| `manager.py` | `SandboxTier` | Enum: `TIER_1` (RestrictedPython), `TIER_2` (container, v3.2) |
| `manager.py` | `execute(code, variables, timeout, tier) → dict` | Entry point for all code execution |
| `restricted.py` | `RestrictedPythonSandbox` | AST-level Python restriction via RestrictedPython library |
| `restricted.py` | `BLOCKED_BUILTINS` | Set: `open`, `exec`, `eval`, `__import__`, `compile`, `globals`, `locals`, `getattr`, `setattr`, `delattr` |
| `restricted.py` | `execute(code, variables, timeout) → dict` | Compile → build safe globals → inject iteration guard → execute with timeout |
| `container.py` | `ContainerSandbox` | gVisor ephemeral container (v3.2 — not in current sprint) |
| `limits.py` | Resource limits | Timeout: 30s, Memory: 256MB, Iterations: 10,000 (all configurable via `EngineConfig`) |

**User code contract:**

```python
# Users write code that reads from `input` and assigns to `output`:
input = {"text": "hello world", "count": 3}

# User code:
words = input["text"].split()
output = {"repeated": words * input["count"]}

# SDK injects `input` as a variable; reads `output` variable after execution.
```

---

### 4.9 engine.providers — LLM Provider Abstraction

**What it is:** A unified interface for calling any LLM. Hides the differences between Vertex AI (Gemini), Anthropic (Claude), and OpenAI (GPT). Handles multi-turn tool calling loops, per-model rate limiting, and token cost tracking.

**Why it exists:** Node code should call `provider.generate(prompt, config)` without caring which LLM is underneath. Swapping providers, falling back on rate limits, and tracking costs all happen here.

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `base.py` | `BaseProvider` (ABC) | `generate(prompt, config) → LLMResponse`, `generate_with_tools(prompt, tools, config) → LLMResponse` |
| `registry.py` | `ProviderRegistry` | Maps model name strings to provider instances; lookup by model name |
| `router.py` | `TierRouter` | Routes to best available model; falls back within same tier when rate-limited |
| `router.py` | `ModelTier` | Enum: `TIER_1` (fast/cheap), `TIER_2` (balanced), `TIER_3` (premium) |
| `gemini.py` | `GeminiProvider` | Vertex AI SDK wrapper; handles Gemini Flash and Pro |
| `anthropic.py` | `AnthropicProvider` | Anthropic SDK wrapper; handles Haiku, Sonnet, Opus |
| `openai.py` | `OpenAIProvider` | OpenAI SDK wrapper; handles GPT-4o-mini and GPT-4o |
| `tool_calling.py` | `ToolCallingProtocol` | Multi-turn loop: prompt → tool_use → execute tool → tool_result → repeat until text response |
| `tool_calling.py` | `MAX_TOOL_TURNS = 5` | Hard limit to prevent infinite tool use loops |
| `rate_limiter.py` | `ProviderRateLimiter` | Redis-based per-model RPM counter; `acquire(model)` blocks or raises |
| `token_counter.py` | `TokenCounter` | tiktoken-based input token counting; cost calculation per model |

**Model tier routing table:**

| Model | Tier | Fallback |
|---|---|---|
| `gemini-flash`, `claude-haiku` | TIER_1 (fast) | Try other TIER_1, then TIER_2 |
| `claude-sonnet`, `gpt-4o-mini` | TIER_2 (balanced) | Try other TIER_2, then TIER_3 |
| `claude-opus`, `gpt-4o` | TIER_3 (premium) | Raise `ProviderRateLimitError` if all limited |

---

### 4.10 engine.integrations — MCP & External Adapters

**What it is:** Everything needed to call external services — MCP tool servers, REST/GraphQL APIs, and incoming webhooks. Also manages OAuth2 credential lifecycle.

**Why it exists:** MCP nodes need to discover available tools and execute them. API nodes need authenticated HTTP calls with templated parameters. Webhook triggers need payload validation and parsing.

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `mcp_client.py` | `MCPClient` | Connect to MCP server; call `tools/list` to discover available tools and their schemas |
| `mcp_client.py` | `MCPClient.list_tools(server_url) → list[ToolSchema]` | Returns available tools + their input schemas |
| `mcp_client.py` | `MCPClient.call_tool(server_url, tool_name, arguments) → dict` | Executes a tool and returns its result |
| `tool_executor.py` | `ToolExecutor` | Dispatches tool calls from `ToolCallingProtocol` to MCP or REST adapters |
| `tool_executor.py` | `execute(tool_name, arguments, ctx) → dict` | Route to MCP or REST based on tool registry |
| `rest_adapter.py` | `RESTAdapter` | HTTP calls with Jinja2 URL/body templating, auth header injection |
| `rest_adapter.py` | `RESTAdapter.call(config, inputs) → dict` | Render templates → resolve auth → make HTTP call → parse JSON response |
| `webhook_handler.py` | `WebhookHandler` | Receives inbound webhook payloads; validates HMAC signature; parses body |
| `webhook_handler.py` | `validate_signature(payload, secret, signature)` | HMAC-SHA256 signature verification |
| `oauth_manager.py` | `OAuthManager` | Loads credentials from PostgreSQL; refreshes expired tokens; stores updated tokens |
| `oauth_manager.py` | `get_credentials(integration_id, tenant_id) → OAuthCredentials` | Returns valid (refreshed if needed) credentials |
| `adapter_registry.py` | `AdapterRegistry` | Plugin interface; allows third-party adapters to register themselves |

---

### 4.11 engine.cache — Caching Layer

**What it is:** Two caches — semantic LLM response cache (pgvector cosine similarity) and MCP tool response cache (simple TTL-based). Reduces LLM costs and latency for repeated/similar prompts.

**Why it exists:** LLM API calls are expensive and slow. If a prompt is semantically similar to a recent prompt (not necessarily identical), we can return the cached response. MCP tool calls are also cacheable for idempotent tools.

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `semantic.py` | `SemanticCache` | pgvector-backed similarity cache for LLM responses |
| `semantic.py` | `check_semantic(prompt, model) → LLMResponse \| None` | Embed prompt → cosine similarity search → return if similarity > threshold |
| `semantic.py` | `store_semantic(prompt, model, response)` | Embed prompt → store (embedding, response) in PostgreSQL |
| `semantic.py` | `similarity_threshold: float = 0.92` | Configurable similarity cutoff (0.0–1.0) |
| `mcp_cache.py` | `MCPResponseCache` | Redis TTL-based cache for MCP tool responses |
| `mcp_cache.py` | `check(tool_name, arguments_hash) → dict \| None` | Hash arguments → Redis GET |
| `mcp_cache.py` | `store(tool_name, arguments_hash, response, ttl)` | Redis SET with configurable TTL |
| `key_schema.py` | Cache key constants | `ai_cache:{hash}` (7d), `mcp_cache:{tool}:{hash}` (configurable), `rate:{provider}:{model}:{window}` (60s) |

---

### 4.12 engine.versioning — Immutable Version Control

**What it is:** Every time a workflow is saved, the SDK creates an immutable versioned snapshot. When execution begins, the exact version used is pinned — changes to the workflow definition cannot affect in-flight runs.

**Why it exists:** Without versioning, editing a workflow while it's running could corrupt execution. Version history enables rollback and auditability. Immutable snapshots enable safe parallel execution.

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `manager.py` | `VersionManager` | Create, list, get, rollback workflow versions |
| `manager.py` | `create_version(definition, created_by) → WorkflowVersion` | Freeze definition → assign version number → persist to MongoDB |
| `manager.py` | `list_versions(workflow_id) → list[WorkflowVersion]` | Return chronological version list |
| `manager.py` | `rollback(workflow_id, version_number) → WorkflowVersion` | Create new version that is a copy of an older version |
| `snapshot.py` | `create_snapshot(definition) → WorkflowDefinition` | Deep copy + freeze (no further mutations allowed) |
| `diff.py` | `compute_diff(v1, v2) → VersionDiff` | Human-readable diff: added/removed/changed nodes and edges |
| `pinning.py` | `pin_for_execution(workflow_id, version_number)` | Store `run_id → version_number` mapping; used to load the exact definition at execution time |
| `pinning.py` | `get_pinned(run_id) → WorkflowVersion` | Retrieve the pinned version for a given run |

---

### 4.13 engine.privacy — PII Detection & Compliance

**What it is:** Scans input/output data for PII (names, emails, phone numbers, credit card numbers, etc.) and masks it before logging. Handles GDPR deletion requests.

**Why it exists:** Workflow inputs and LLM outputs may contain sensitive user data. This data must never appear in unmasked logs. GDPR requires deletion of user data across all stores.

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `detector.py` | `PIIDetector` | Microsoft Presidio-based PII entity recognition |
| `detector.py` | `scan_dict(data: dict) → list[PIIDetection]` | Recursively scans all string values in a dict for PII entities |
| `detector.py` | `scan_text(text: str) → list[PIIDetection]` | Scan a single string; returns list of `{entity_type, start, end, score}` |
| `masker.py` | `PIIMasker` | Replaces detected PII with type-coded tokens |
| `masker.py` | `mask_dict(data: dict) → dict` | Returns a copy of the dict with PII replaced (e.g., `[EMAIL_ADDRESS]`) |
| `masker.py` | `mask_text(text: str, detections) → str` | Apply masks to a string using detection offsets |
| `gdpr.py` | `GDPRHandler` | Handles right-to-erasure: delete user data from MongoDB, PostgreSQL, Redis, GCS |
| `gdpr.py` | `delete_user_data(tenant_id, user_id)` | Coordinates deletion across all stores |
| `gdpr.py` | `check_data_residency(tenant_id) → str` | Returns required data region (e.g., `eu`, `us`) |

---

### 4.14 engine.events — Domain Event Bus

**What it is:** In-process publish/subscribe event system. When execution progresses (node starts, node completes, run finishes), the SDK publishes domain events. The API's WebSocket hub subscribes and forwards events to the browser.

**Why it exists:** Decouples execution logic from real-time streaming. The executor doesn't know about WebSockets. It just publishes events. The API layer listens and forwards them to clients over WebSocket connections.

**Must-have components:**

| File | Class | Responsibility |
|---|---|---|
| `bus.py` | `EventBus` | In-process pub/sub; supports Redis pub/sub as backend for cross-process delivery |
| `bus.py` | `publish(event: DomainEvent)` | Publish to Redis channel `ws:run:{run_id}` |
| `bus.py` | `subscribe(channel, handler)` | Register a handler for a channel |
| `handlers.py` | `AuditEventHandler` | Calls `AuditLogger.record(event)` on every event |
| `handlers.py` | `MetricsEventHandler` | Increments Prometheus counters on node complete/fail events |
| `audit.py` | `AuditLogger` | Appends immutable audit records to MongoDB `audit_log` collection |
| `audit.py` | `record(event: DomainEvent)` | Persists: event type, run ID, tenant ID, timestamp, masked payload |

**Event flow diagram:**

```
SDK executor                  EventBus (Redis backend)    WebSocket Hub (API layer)
     │                               │                          │
     │ publish(NodeCompleted)        │                          │
     │──────────────────────────────▶│                          │
     │                               │  Redis PUBLISH           │
     │                               │─────────────────────────▶│
     │                               │                          │ forward to WS client
     │                               │                          │──────────────────▶ Browser UI
```

---

## 5. workflow-api — FastAPI Backend

**What it is:** A thin FastAPI application. Its only job is to receive HTTP/WebSocket requests, call the appropriate SDK function, persist the result, and return a response.

**Core principle:** No workflow logic lives here. If you find yourself writing DAG logic, node handling, or state transitions in the API, it belongs in the SDK instead.

**Must-have components:**

### 5.1 Entry Point

| File | Component | Responsibility |
|---|---|---|
| `main.py` | `FastAPI app` | App instantiation; lifespan hooks (DB connection pool init, SDK config injection) |
| `main.py` | `@app.on_event("startup")` | Init: MongoDB client, PostgreSQL pool, Redis connection, EngineConfig, NodeTypeRegistry |
| `dependencies.py` | `get_engine_config()` | FastAPI DI — returns singleton `EngineConfig` |
| `dependencies.py` | `get_db()` | FastAPI DI — yields MongoDB session |
| `dependencies.py` | `get_registry()` | FastAPI DI — returns `NodeTypeRegistry` singleton |
| `dependencies.py` | `get_semaphore()` | FastAPI DI — returns `TenantSemaphore` instance |

### 5.2 Routes

| File | Endpoint | SDK Call | Action |
|---|---|---|---|
| `routes/workflows.py` | `POST /api/v2/workflows` | `engine.validation.validate()` + `engine.versioning.create_version()` | Save workflow; validate first; create version |
| `routes/workflows.py` | `GET /api/v2/workflows/{id}` | — | Return latest workflow definition |
| `routes/workflows.py` | `PUT /api/v2/workflows/{id}` | `engine.validation.validate()` + `engine.versioning.create_version()` | Update workflow; new version |
| `routes/workflows.py` | `DELETE /api/v2/workflows/{id}` | — | Soft delete workflow |
| `routes/workflows.py` | `GET /api/v2/workflows` | — | Paginated list for tenant |
| `routes/executions.py` | `POST /api/v2/executions` | `engine.versioning.pin_for_execution()` + `engine.privacy.scan_dict()` | Validate input → acquire semaphore → pin version → dispatch to Celery |
| `routes/executions.py` | `GET /api/v2/executions/{run_id}` | — | Return run status + node states |
| `routes/executions.py` | `POST /api/v2/executions/{run_id}/cancel` | `engine.state.transition_run(CANCELLED)` | Cancel in-flight run |
| `routes/executions.py` | `GET /api/v2/executions` | — | Paginated execution history |
| `routes/versions.py` | `GET /api/v2/workflows/{id}/versions` | `engine.versioning.list_versions()` | Return version list |
| `routes/versions.py` | `GET /api/v2/workflows/{id}/versions/{v1}/diff/{v2}` | `engine.versioning.compute_diff()` | Return diff between two versions |
| `routes/versions.py` | `POST /api/v2/workflows/{id}/versions/{v}/rollback` | `engine.versioning.rollback()` | Roll back to a previous version |
| `routes/nodes.py` | `GET /api/v2/nodes/types` | `engine.nodes.registry.list_all()` | Return all node types (for UI palette) |
| `routes/nodes.py` | `GET /api/v2/nodes/types/{type}/schema` | `engine.nodes.registry.get_config_schema()` | Return JSON Schema (for UI config panel) |
| `routes/webhooks.py` | `POST /api/v2/webhooks/{path}` | `engine.integrations.webhook_handler.validate()` | Validate HMAC → find trigger workflow → dispatch run |

### 5.3 WebSocket

| File | Endpoint | Responsibility |
|---|---|---|
| `websocket/hub.py` | `WS /api/v2/ws/runs/{run_id}` | Subscribe to Redis `ws:run:{run_id}` → forward events to connected WS clients |
| `websocket/hub.py` | `WebSocketHub` | Manages connection pool; handles heartbeat; cleans up on disconnect |
| `websocket/events.py` | Typed WS event schema | `RunStarted`, `NodeStarted`, `NodeCompleted`, `NodeFailed`, `RunCompleted` — typed for frontend consumption |

### 5.4 Auth & Middleware

| File | Component | Responsibility |
|---|---|---|
| `auth/jwt.py` | `JWTValidator` | Validates Bearer token; extracts tenant_id + user_id |
| `auth/api_key.py` | `APIKeyValidator` | Validates `X-API-Key` header against hashed keys in PostgreSQL |
| `auth/oauth.py` | `OAuthFlow` | OAuth2 authorization code flow for third-party integrations |
| `middleware/rate_limit.py` | `APIRateLimitMiddleware` | Per-tenant API request rate limiting (Redis counters) |
| `middleware/tenant.py` | `TenantContextMiddleware` | Injects tenant object into request state from JWT/API key |
| `middleware/cors.py` | CORS configuration | Allow UI origin; configurable per environment |
| `middleware/semaphore.py` | `TenantSemaphore` | Redis INCR/DECR: enforces `max_concurrent_runs` per tenant |

---

## 6. workflow-worker — Celery Task Workers

**What it is:** Thin Celery task definitions. Each task receives a message from the Redis queue, creates the necessary SDK objects, calls the SDK, and returns.

**Core principle:** Celery tasks are just plumbing. No logic here. The SDK does the actual work.

**Must-have components:**

| File | Component | Responsibility |
|---|---|---|
| `celery_app.py` | `celery_app` | Celery instance config: broker URL, result backend, task serializer, worker concurrency |
| `celery_app.py` | `celery_app.conf.task_routes` | Route tasks to specific queues (`default`, `ai-heavy`, `critical`) |
| `tasks/orchestrator.py` | `orchestrate_run(run_id, definition_dict)` | Main task: deserialize definition → create SDK objects → call `RunOrchestrator.run()` → release semaphore |
| `tasks/node_runner.py` | `execute_single_node(run_id, node_id, definition_dict)` | Per-node task for parallel execution: resolve inputs → execute node → store output |
| `tasks/cleanup.py` | `cleanup_run(run_id, tenant_id)` | Post-run: release semaphore, delete Redis context keys, update billing counters |
| `signals.py` | `task_failure` signal | On Celery task crash: call `engine.state.transition_run(FAILED)` + publish `RunFailed` event |

**Parallel execution with Celery group/chord:**

```python
from celery import group, chord

# When RunOrchestrator reaches a PARALLEL step:
parallel_tasks = group(
    execute_single_node.s(run_id, node_id, definition_dict)
    for node_id in ["branch_a", "branch_b", "branch_c"]
)
# chord = group + callback that runs after ALL tasks complete
join_callback = execute_single_node.s(run_id, "fan_in_node", definition_dict)
chord(parallel_tasks)(join_callback)
```

**Worker scaling:**

| Queue | Worker Type | Scaling Trigger |
|---|---|---|
| `default` | General tasks | Celery queue depth > 100 (HPA) |
| `ai-heavy` | AI/LLM nodes | Celery queue depth > 20 (expensive tasks) |
| `critical` | Human nodes, webhook triggers | Always-on, min 2 replicas |

---

## 7. workflow-cli — Command-Line Interface

**What it is:** A Click-based CLI that wraps the SDK for developer use. The key feature: `validate` works entirely locally (no API server needed) because it calls the SDK directly.

**Must-have components:**

| File | Command | SDK Used | API Call? |
|---|---|---|---|
| `commands/validate.py` | `wf validate flow.yaml` | `engine.validation.ValidationPipeline` | No |
| `commands/deploy.py` | `wf deploy flow.yaml` | `engine.validation.ValidationPipeline` (local first) | Yes (after local validation passes) |
| `commands/run.py` | `wf run <workflow-id> --input '{}'` | None | Yes |
| `commands/logs.py` | `wf logs <run-id>` | None | Yes (WS stream) |
| `commands/versions.py` | `wf versions list <workflow-id>` | None | Yes |
| `commands/versions.py` | `wf versions rollback <workflow-id> --to <version>` | None | Yes |

**Validate command output example:**
```
$ wf validate ./send-welcome.yaml
✓ Valid — 4 nodes, 3 steps, 1 parallel group
  Steps:
    1. SEQUENTIAL: trigger-webhook
    2. PARALLEL:   ai-draft-email, api-fetch-user
    3. FAN_IN:     api-send-email
```

---

## 8. workflow-ui & @workflow/react — Frontend

**What it is:** Next.js application built with `@workflow/react` component library. The UI has no SDK knowledge. It sends workflow JSON to the API and receives results.

**Architecture principle:** The UI produces a workflow JSON document. The SDK validates it. The UI doesn't know what valid means — that's the SDK's job.

**Must-have components:**

### 8.1 @workflow/react Component Library

| Component | Data Source | Updates Via | Purpose |
|---|---|---|---|
| `<WorkflowCanvas />` | `GET /api/v2/workflows/{id}` | User drag/drop (React Flow) | Main DAG editor canvas |
| `<NodePalette />` | `GET /api/v2/nodes/types` | Static (node registry) | Draggable node type sidebar |
| `<NodeConfigPanel />` | `GET /api/v2/nodes/types/{type}/schema` | User node selection | Dynamic form from SDK JSON Schema |
| `<RunMonitor />` | `WS /api/v2/ws/runs/{id}` | Real-time WebSocket events | Node status overlays on canvas |
| `<VersionHistory />` | `GET /api/v2/workflows/{id}/versions` | On panel open | Version list with diff viewer |
| `<ExecutionLog />` | `WS /api/v2/ws/runs/{id}` | Real-time WebSocket | Scrolling per-node log stream |

### 8.2 Key UI → API → SDK Data Flow

```
1. User drags "AI Prompt" node from palette onto canvas
   → React Flow adds node to graph state

2. User draws edge from Trigger "output" port to AI "prompt" port
   → React Flow adds edge with source_port and target_port

3. User clicks node → NodeConfigPanel opens
   → UI fetches GET /api/v2/nodes/types/AI/schema
   → API calls engine.nodes.registry.get_config_schema("AI")
   → UI renders dynamic form from returned JSON Schema

4. User fills config (model = "gemini-flash", prompt_template = "...")
   → Form updates node config in React state

5. User clicks "Save"
   → UI serialises React Flow graph to WorkflowDefinition JSON
   → UI posts POST /api/v2/workflows
   → API deserialises into WorkflowDefinition model
   → API calls engine.validation.validate(definition)
   → If errors: API returns 422 with error list → UI shows inline errors
   → If valid: API calls engine.versioning.create_version(definition)
   → API returns {workflow_id, version_number}

6. User clicks "Run"
   → UI posts POST /api/v2/executions {workflow_id, input: {...}}
   → API acquires semaphore → pins version → dispatches to Celery
   → API returns {run_id, status: "queued"}
   → UI opens WebSocket WS /api/v2/ws/runs/{run_id}

7. Workers execute nodes → SDK publishes events to Redis → WebSocket hub forwards
   → UI receives NodeStarted events → turns node border blue
   → UI receives NodeCompleted events → turns node border green
   → UI receives NodeFailed events → turns node border red with error tooltip
```

### 8.3 Next.js App Structure

```
apps/workflow-ui/src/app/
├── (dashboard)/
│   ├── workflows/
│   │   ├── page.tsx              # Workflow list
│   │   └── [id]/
│   │       ├── page.tsx          # Workflow editor (WorkflowCanvas)
│   │       └── runs/
│   │           └── [run_id]/
│   │               └── page.tsx  # Run detail (RunMonitor + ExecutionLog)
├── api/                          # Next.js API routes (BFF layer if needed)
└── layout.tsx
```

---

## 9. Data Flow — End-to-End Execution (23 Steps)

| # | Component | Action | SDK Module |
|---|---|---|---|
| 1 | **UI or CLI** | User designs workflow on canvas (React Flow) or YAML | — |
| 2 | **UI or CLI** | POST /api/v2/workflows with workflow JSON | — |
| 3 | **API** | Authenticate (JWT / API key) | — |
| 4 | **API** | Call `engine.validation.validate(definition, tenant)` | `validation` |
| 5 | **API** | Call `engine.versioning.create_version(definition)` | `versioning` |
| 6 | **API** | Persist definition + version to MongoDB | — |
| 7 | **UI or CLI** | POST /api/v2/executions {workflow_id, input} | — |
| 8 | **API** | Acquire tenant semaphore (Redis INCR, check vs max_slots) | — |
| 9 | **API** | Call `engine.versioning.pin_for_execution(workflow_id)` | `versioning` |
| 10 | **API** | Call `engine.privacy.scan_dict(input)` — reject if blocked PII | `privacy` |
| 11 | **API** | Create `ExecutionRun` record (status=QUEUED) in MongoDB | `models` |
| 12 | **API** | Dispatch `orchestrate_run.delay(run_id, definition_dict)` to Celery | — |
| 13 | **Worker** | Receive task; call `engine.dag.DAGParser().parse(definition)` → ExecutionPlan | `dag` |
| 14 | **Worker** | Call `engine.state.transition_run(run_id, RUNNING)` | `state` |
| 15 | **Worker** | SDK `EventBus.publish(RunStarted)` → Redis pub/sub → WS hub → UI | `events` |
| 16 | **Worker** | For each step in plan: call `engine.context.resolve_inputs(run_id, node_id)` | `context` |
| 17 | **Worker** | Call `engine.executor.NodeExecutor.execute(node_config, inputs, run)` | `executor` |
| 18 | **Worker** | (AI node) `engine.cache.check_semantic(prompt, model)` | `cache` |
| 19 | **Worker** | (AI node) `engine.providers.rate_limiter.acquire(model)` | `providers` |
| 20 | **Worker** | (AI node) `engine.providers.router.route(model).generate(prompt, config)` → LLM call | `providers` |
| 21 | **Worker** | (Tool call) `engine.integrations.tool_executor.execute(tool_name, args)` | `integrations` |
| 22 | **Worker** | `engine.context.store_output(run_id, node_id, output)` → Redis or GCS | `context` |
| 23 | **Worker** | `engine.state.transition_run(COMPLETED)` → EventBus → Redis → WS hub → UI green | `state`, `events` |

---

## 10. Storage Architecture

| Database | Owns | Rationale |
|---|---|---|
| **MongoDB** | Workflow definitions, versions (immutable), execution runs and node states, execution logs, audit trail, node configs | Document-shaped data with varying schemas per node type |
| **PostgreSQL + pgvector** | Users, tenants, subscriptions, API keys (hashed), billing records, semantic cache embeddings, OAuth credentials | ACID transactions, foreign keys, pgvector for cosine similarity search |
| **Redis** | Celery task queue, per-model rate limit counters, execution context (≤64KB node outputs), pub/sub channels, DLQ, tenant semaphore counters | Sub-millisecond ephemeral data; all reconstructible |
| **GCS** | Node outputs (>64KB), user-uploaded files, exported workflow bundles | Blob storage with configurable lifecycle policies |

**MongoDB collection structure:**

| Collection | Document shape | Index |
|---|---|---|
| `workflows` | `WorkflowDefinition` + metadata | `tenant_id`, `workflow_id` |
| `workflow_versions` | `WorkflowVersion` (immutable, never updated) | `workflow_id`, `version_number` |
| `execution_runs` | `ExecutionRun` + `node_states` map | `run_id`, `workflow_id`, `tenant_id`, `status` |
| `audit_log` | Append-only domain events | `tenant_id`, `run_id`, `timestamp` |

**Cache key patterns:**

| Key Pattern | TTL | Purpose |
|---|---|---|
| `ai_cache:{prompt_hash}:{model}` | 7 days | Semantic LLM response cache |
| `mcp_cache:{tool_name}:{args_hash}` | Configurable per tool | MCP tool response cache |
| `rate:{provider}:{model}:{window_start}` | 60s | RPM counter per model |
| `ctx:{run_id}:{node_id}` | 24h | Small node output (≤64KB) |
| `tenant:{id}:exec_slots` | No TTL (manual decr) | Concurrency semaphore counter |
| `ws:run:{run_id}` | Auto-cleanup on run end | Redis pub/sub channel for WS hub |
| `dlq:{exec_id}` | No TTL | Dead letter queue for failed tasks |

---

## 11. Infrastructure & Observability

| Concern | Technology | Detail |
|---|---|---|
| **Containers** | Docker | One Dockerfile per service (api, worker); shared base image |
| **Orchestration** | Kubernetes (GKE) | Separate Deployments for API, workers, scheduler |
| **Autoscaling** | HPA | API: scale on CPU. Workers: scale on Celery queue depth (custom metric) |
| **Tracing** | OpenTelemetry | Trace ID assigned at API entry; propagated through Redis task message to worker |
| **Metrics** | Prometheus + Grafana | Queue depth, node execution time p50/p95, cache hit rate, provider latency, token costs |
| **Logging** | Structured JSON | PII-masked via `engine.privacy.masker` before any log output |
| **Secrets** | GCP Secret Manager | Provider API keys, DB credentials, OAuth client secrets |
| **IaC** | Terraform | GKE cluster, CloudSQL (PostgreSQL), Memorystore (Redis), GCS buckets |
| **CI/CD** | GitHub Actions | `lint → unit test → integration test → build → deploy` |

**Kubernetes deployment layout:**

```
GKE Cluster
├── namespace: workflow-prod
│   ├── Deployment: workflow-api       (2-10 replicas, HPA CPU 70%)
│   ├── Deployment: workflow-worker    (2-20 replicas, HPA queue depth)
│   ├── Deployment: workflow-scheduler (1 replica, Celery beat)
│   ├── Service: workflow-api-svc      (LoadBalancer → HTTPS)
│   └── ConfigMap / SecretRef          (env vars from Secret Manager)
```

---

## 12. Testing Strategy

| Phase | Sprints | What | Target Modules | Tools |
|---|---|---|---|---|
| **Phase 1** | 1–4 | SDK unit tests | `dag`, `validation`, `state`, `nodes`, `models` | pytest |
| **Phase 2** | 3–6 | SDK integration tests | `executor` + `providers` + `context` with real Redis/Mongo | pytest + testcontainers |
| **Phase 3** | 5–6 | Contract tests | `providers` ↔ `integrations` — tool schemas match | Pact |
| **Phase 4** | 7–8 | Load + security | Full stack under 1000 concurrent runs | Locust, ZAP, Snyk |
| **Ongoing** | Post-launch | Chaos + AI quality | Pod kills, provider outages, prompt regression | Chaos Mesh, custom eval suite |

**Key testing advantage of SDK-first:** Engine tests run directly against the Python library. No HTTP server. No Celery broker. No database (unless testing persistence modules). Pure unit tests are fast and hermetic.

```python
# Example: Test DAG parallel detection — no server, no broker
def test_dag_parser_parallel_detection():
    definition = WorkflowDefinition(
        nodes=[
            NodeConfig(id="a", type=NodeType.TRIGGER),
            NodeConfig(id="b", type=NodeType.AI),
            NodeConfig(id="c", type=NodeType.MCP),
            NodeConfig(id="d", type=NodeType.TRANSFORM),
        ],
        edges=[
            EdgeConfig(source="a", target="b"),
            EdgeConfig(source="a", target="c"),
            EdgeConfig(source="b", target="d"),
            EdgeConfig(source="c", target="d"),
        ],
    )
    plan = DAGParser().parse(definition)
    assert len(plan.steps) == 3
    assert plan.steps[1].step_type == StepType.PARALLEL
    assert set(plan.steps[1].node_ids) == {"b", "c"}
    assert plan.steps[2].step_type == StepType.FAN_IN

# Example: Test validation without a server
def test_validation_rejects_cycle():
    definition = WorkflowDefinition(
        nodes=[NodeConfig(id="a", type=NodeType.AI), NodeConfig(id="b", type=NodeType.AI)],
        edges=[EdgeConfig(source="a", target="b"), EdgeConfig(source="b", target="a")],  # cycle!
    )
    errors = ValidationPipeline(NodeTypeRegistry()).validate(definition)
    assert any("Cycle detected" in e for e in errors)
```

---

## 13. Technology Stack

| Package | Technology | Purpose |
|---|---|---|
| **workflow-engine (SDK)** | Python 3.12, Pydantic v2, RestrictedPython, httpx, tiktoken, Presidio, motor (async MongoDB) | Core library — all workflow logic. This is what you build. |
| **workflow-api** | FastAPI, Starlette WebSocket, PyJWT, Redis Lua scripts | HTTP/WS shell, auth, rate limiting — thin consumer of SDK |
| **workflow-worker** | Celery 5.x, Redis (broker + result backend) | Task execution shell — thin consumer of SDK |
| **workflow-cli** | Click, Rich, httpx, websockets | CLI shell — thin consumer of SDK |
| **workflow-ui** | Next.js 14+, React Flow, Tailwind CSS, Monaco Editor | Visual DAG editor — never imports SDK |
| **@workflow/react** | React, TypeScript, React Flow | Embeddable components npm package |
| **Providers** | Vertex AI SDK, Anthropic SDK, OpenAI SDK | LLM access (inside SDK providers module) |
| **Integrations** | MCP SDK, authlib (OAuth2), aiohttp | External connections (inside SDK integrations module) |
| **Storage** | MongoDB (motor), PostgreSQL + pgvector (asyncpg), Redis (aioredis), GCS (google-cloud-storage) | Persistence |
| **Infra** | Docker, Kubernetes (GKE), Terraform, OpenTelemetry, Prometheus, Grafana | Deployment + observability |
| **Testing** | pytest, testcontainers, Locust, Pact, OWASP ZAP, Snyk | Quality assurance |

---

> **AI Workflow Builder Platform — Architecture**
> SDK-first • 14 SDK modules • 5 consumer packages • 7 node types • 23-step data flow
> The `workflow-engine` package is the product. You build it from scratch. API, Worker, CLI, and UI are thin consumers.
