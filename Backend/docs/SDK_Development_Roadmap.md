# workflow-engine SDK — Development Roadmap
### AI Workflow Builder Platform | Senior Solution Architect & AI Engineer Output

> **Scope:** This document covers the complete development lifecycle of the `workflow-engine` SDK — the core Python library that is the product. All other services (API, Worker, CLI, UI) are thin consumers of this SDK and are excluded from this roadmap.

---

## Table of Contents

1. [High-Level SDK Architecture Overview](#1-high-level-sdk-architecture-overview)
2. [SDK Internal Layer Model](#2-sdk-internal-layer-model)
3. [Module-wise Breakdown](#3-module-wise-breakdown)
4. [Sub-module Decomposition](#4-sub-module-decomposition)
5. [Step-by-Step Development Roadmap](#5-step-by-step-development-roadmap)
6. [Recommended Tech Stack](#6-recommended-tech-stack)
7. [Design Considerations](#7-design-considerations)
8. [SDK Project Structure](#8-sdk-project-structure)
9. [Core Interfaces & Abstractions](#9-core-interfaces--abstractions)
10. [Versioning & Packaging Strategy](#10-versioning--packaging-strategy)

---

## 1. High-Level SDK Architecture Overview

The `workflow-engine` is a standalone Python library — a proprietary SDK authored from scratch. It encapsulates every piece of workflow intelligence: DAG parsing, node execution, state management, LLM provider abstraction, code sandboxing, caching, versioning, privacy compliance, and the event bus. Nothing outside the SDK duplicates any of this logic.

### Core Design Axiom

```
workflow-engine knows NOTHING about:          workflow-engine knows EVERYTHING about:
  ✗ FastAPI                                     ✓ What a workflow DAG is
  ✗ Celery                                      ✓ How to parse & validate it
  ✗ Click                                       ✓ How to execute nodes in order
  ✗ HTTP requests/responses                     ✓ How to call LLMs (Gemini/Claude/OpenAI)
  ✗ Task queues                                 ✓ How to sandbox user Python code
  ✗ Web frameworks                              ✓ How to manage run lifecycle state
                                                ✓ How to cache LLM responses semantically
                                                ✓ How to detect & mask PII
```

### SDK Consumer Map

```
                    ┌─────────────────────────────────────────┐
                    │        workflow-engine (THE SDK)         │
                    │   Python 3.12 | Pydantic v2 | httpx     │
                    └───────────┬─────────────────────────────┘
                                │ pip install workflow-engine
            ┌───────────────────┼───────────────────────────┐
            ▼                   ▼                           ▼
     workflow-api         workflow-worker             workflow-cli
     (FastAPI shell)      (Celery shell)              (Click shell)
     Validates, versions  Executes nodes,             Validates locally,
     workflows via SDK    drives DAG via SDK          deploys via API
```

---

## 2. SDK Internal Layer Model

The SDK itself is internally organized into **4 sub-layers**. Each sub-layer has a strict dependency direction — lower layers never import from higher layers.

```
SDK SUB-LAYER A — DOMAIN MODELS (foundation — everything depends on this)
  engine.config     EngineConfig — injected by consumer at startup
  engine.models     All Pydantic v2 domain objects (WorkflowDefinition, NodeConfig, etc.)
        │
        ▼ (B imports from A only)
SDK SUB-LAYER B — STRUCTURAL LOGIC (shape, not execution)
  engine.dag        DAG parsing → ExecutionPlan
  engine.nodes      NodeTypeRegistry + 7 built-in node type definitions
  engine.validation ValidationPipeline → list of errors
        │
        ▼ (C imports from A + B)
SDK SUB-LAYER C — RUNTIME EXECUTION (actual running of workflows)
  engine.executor   RunOrchestrator + NodeExecutor
  engine.state      StateMachine + StateStore
  engine.context    ContextManager + RedisStore + GCSStore
        │
        ▼ (D imports from A + B + C as needed)
SDK SUB-LAYER D — PLATFORM SERVICES (cross-cutting capabilities)
  engine.providers  LLM provider abstraction (Gemini, Claude, OpenAI)
  engine.sandbox    Python code sandbox (RestrictedPython)
  engine.integrations MCP client + REST adapter + OAuth
  engine.cache      Semantic cache (pgvector) + MCP cache (Redis TTL)
  engine.versioning Immutable workflow version control
  engine.privacy    PII detection + masking (Presidio)
  engine.events     Domain event bus + AuditLogger
```

**Golden rule:** No circular imports. `engine.models` imports nothing from the SDK. `engine.dag` imports from `engine.models` only. `engine.executor` imports from models, dag, nodes, state, and context.

---

## 3. Module-wise Breakdown

The SDK has **15 modules** (including config), organized into the 4 sub-layers:

| # | Module | Sub-layer | Primary Responsibility | Key Output / Contract |
|---|--------|-----------|----------------------|-----------------------|
| 0 | `engine.config` | A | Configuration injection | `EngineConfig` — Pydantic settings class |
| 1 | `engine.models` | A | All domain data models | Pydantic v2 classes used everywhere |
| 2 | `engine.dag` | B | Workflow topology analysis | `ExecutionPlan` with ordered steps |
| 3 | `engine.nodes` | B | Node type system + registry | `NodeTypeRegistry` singleton |
| 4 | `engine.validation` | B | Pre-execution validation | `list[str]` of all errors found |
| 5 | `engine.executor` | C | Drive full workflow run | `RunOrchestrator.run()` entry point |
| 6 | `engine.state` | C | Run/node lifecycle state | Atomic transitions to MongoDB |
| 7 | `engine.context` | C | Inter-node data transfer | `ContextRef` (Redis or GCS URI) |
| 8 | `engine.sandbox` | D | Safe Python code execution | Sandboxed `execute(code) → dict` |
| 9 | `engine.providers` | D | LLM abstraction + routing | `BaseProvider.generate() → LLMResponse` |
| 10 | `engine.integrations` | D | MCP + REST + Webhooks + OAuth | `MCPClient`, `RESTAdapter`, `OAuthManager` |
| 11 | `engine.cache` | D | LLM + MCP response caching | Cache hit/miss for semantic + TTL |
| 12 | `engine.versioning` | D | Immutable snapshot management | `WorkflowVersion`, rollback support |
| 13 | `engine.privacy` | D | PII scan + mask + GDPR | `PIIDetector`, `PIIMasker` |
| 14 | `engine.events` | D | Domain event bus | `EventBus.publish(DomainEvent)` |

---

## 4. Sub-module Decomposition

### 4.0 engine.config

| Sub-module | File | What to Build |
|---|---|---|
| Settings class | `config.py` | `EngineConfig(BaseSettings)` with all field declarations |
| Storage fields | `config.py` | `mongodb_url`, `postgres_url`, `redis_url`, `gcs_bucket` |
| Provider fields | `config.py` | `vertex_ai_project`, `anthropic_api_key`, `openai_api_key` |
| Sandbox fields | `config.py` | `sandbox_timeout_seconds`, `sandbox_max_memory_mb`, `sandbox_max_iterations` |
| Context fields | `config.py` | `context_inline_threshold_kb`, `provider_rate_limit_window` |

---

### 4.1 engine.models

| Sub-module | File | What to Build |
|---|---|---|
| Workflow models | `workflow.py` | `WorkflowDefinition`, `WorkflowMetadata`, `RetryPolicy`, `FailureMode` enum |
| Node models | `node.py` | `NodeConfig`, `NodeType` enum, `PortDefinition`, `PortType` enum, `EdgeConfig` |
| Execution models | `execution.py` | `ExecutionRun`, `NodeExecution`, `ExecutionStatus` enum, `NodeStatus` enum |
| Version models | `version.py` | `WorkflowVersion`, `VersionDiff`, `RollbackRecord` |
| Trigger models | `trigger.py` | `TriggerConfig`, `WebhookTrigger`, `CronTrigger`, `EventTrigger` |
| Context models | `context.py` | `ExecutionContext`, `ContextRef` |
| Event models | `events.py` | `DomainEvent` base, `RunStarted`, `RunCompleted`, `RunFailed`, `NodeStarted`, `NodeCompleted`, `NodeFailed` |
| Tenant models | `tenant.py` | `Tenant`, `Subscription`, `PlanTier` enum |
| Provider models | `provider.py` | `LLMResponse`, `TokenUsage`, `ToolCall`, `ProviderConfig`, `ModelTier` enum |
| Error hierarchy | `errors.py` | `EngineError`, `ValidationError`, `CycleDetectedError`, `NodeExecutionError`, `ProviderRateLimitError`, `SandboxTimeoutError`, `PortMismatchError`, `StateTransitionError` |

---

### 4.2 engine.dag

| Sub-module | File | What to Build |
|---|---|---|
| DAG parser | `parser.py` | `DAGParser.parse(definition) → ExecutionPlan` — orchestrator |
| Topological sort | `topo_sort.py` | `_compute_adjacency()`, `_compute_in_degrees()`, `topological_sort()` via Kahn's algorithm |
| Parallel detection | `parallel.py` | `detect_parallel_groups()`, `detect_fan_in_points()` |
| Execution plan | `plan.py` | `StepType` enum, `ExecutionStep`, `ExecutionPlan`, `get_ready_nodes()` method |

---

### 4.3 engine.nodes

| Sub-module | File | What to Build |
|---|---|---|
| Registry | `registry.py` | `NodeTypeRegistry` singleton — `register()`, `get()`, `list_all()`, `get_config_schema()`, `get_ports()`, `register_plugin()` |
| Base class | `base.py` | `BaseNodeType` ABC — all required attributes and abstract `execute()` and `validate_config()` |
| AI node | `ai_node.py` | `AINodeType` — cache → rate limit → LLM generate → cache store → token track |
| MCP node | `mcp_node.py` | `MCPNodeType` — tool discover → param render → MCP call → parse |
| API node | `api_node.py` | `APINodeType` — URL/body template → auth → HTTP → parse |
| Logic node | `logic_node.py` | `LogicNodeType` — If/Else, For-Each, Switch, Merge, Delay sub-types |
| Transform node | `transform_node.py` | `TransformNodeType` — sandbox Python OR Jinja2 template |
| Trigger node | `trigger_node.py` | `TriggerNodeType` — Webhook, Cron, Manual, Event sub-types |
| Human node | `human_node.py` | `HumanNodeType` — pause, notify, wait for form, resume |
| Plugin interface | `custom.py` | `CustomNodePlugin` ABC — for tenant/third-party node registration |

---

### 4.4 engine.validation

| Sub-module | File | What to Build |
|---|---|---|
| Pipeline | `pipeline.py` | `ValidationPipeline.validate(definition, tenant?) → list[str]` |
| Schema validator | `schema.py` | `SchemaValidator` — jsonschema check per node's config_schema |
| Cycle detector | `cycle_detector.py` | `CycleDetector` — DFS with WHITE/GRAY/BLACK coloring |
| Port checker | `port_checker.py` | `PortCompatibilityChecker` — type compatibility matrix enforcement |
| Plan checker | `plan_checker.py` | `PlanAccessChecker` — node vs tenant plan tier gating |
| Orphan detector | `orphan_detector.py` | `OrphanNodeDetector` — non-trigger nodes with no incoming edges |
| Duplicate detector | `duplicate_detector.py` | `DuplicateIdDetector` — no two nodes share same ID |
| Expression validator | `expression.py` | `ExpressionValidator` — condition syntax validation |

---

### 4.5 engine.executor

| Sub-module | File | What to Build |
|---|---|---|
| Orchestrator | `orchestrator.py` | `RunOrchestrator.run()`, `_execute_single()`, `_execute_parallel()` |
| Node executor | `node_executor.py` | `NodeExecutor.execute()` — registry lookup → context build → dispatch |
| Dispatcher | `dispatcher.py` | `NodeDispatcher` — routes to correct node handler by `NodeType` |
| Retry handler | `retry.py` | `RetryHandler.compute_backoff()` — exponential backoff + jitter |
| Timeout manager | `timeout.py` | `TimeoutManager.wrap()` — `asyncio.wait_for` wrapper |

---

### 4.6 engine.state

| Sub-module | File | What to Build |
|---|---|---|
| State machine | `machine.py` | `StateMachine.transition_run()`, `StateMachine.transition_node()` |
| Transitions | `transitions.py` | `RUN_TRANSITIONS` dict, `NODE_TRANSITIONS` dict — enforced allowlists |
| Persistence | `persistence.py` | `StateStore.get_run()`, `StateStore.save_run()` — MongoDB with optimistic locking |

---

### 4.7 engine.context

| Sub-module | File | What to Build |
|---|---|---|
| Context manager | `manager.py` | `ContextManager.store_output()`, `load_output()`, `resolve_inputs()` |
| Redis store | `redis_store.py` | `RedisContextStore.set()`, `get()`, `delete()` — TTL-aware |
| GCS store | `gcs_store.py` | `GCSContextStore.upload()`, `download()` |
| Input resolver | `resolver.py` | `InputResolver` — edge traversal → port name mapping → upstream output assembly |

---

### 4.8 engine.sandbox

| Sub-module | File | What to Build |
|---|---|---|
| Sandbox manager | `manager.py` | `SandboxManager.execute()`, `SandboxTier` enum, tier selection |
| Restricted sandbox | `restricted.py` | `RestrictedPythonSandbox` — AST compile, blocked builtins, iteration guard, timeout |
| Container sandbox | `container.py` | `ContainerSandbox` stub — gVisor (v2 deferred) |
| Resource limits | `limits.py` | Timeout / memory / iteration constants + enforcement |

---

### 4.9 engine.providers

| Sub-module | File | What to Build |
|---|---|---|
| Base provider | `base.py` | `BaseProvider` ABC — `generate()`, `generate_with_tools()` |
| Provider registry | `registry.py` | `ProviderRegistry` — model-name-to-provider map |
| Tier router | `router.py` | `TierRouter.route()`, `ModelTier` enum, fallback logic |
| Gemini provider | `gemini.py` | `GeminiProvider` — Vertex AI SDK async wrapper |
| Anthropic provider | `anthropic.py` | `AnthropicProvider` — Anthropic SDK async wrapper |
| OpenAI provider | `openai.py` | `OpenAIProvider` — OpenAI SDK async wrapper |
| Tool calling | `tool_calling.py` | `ToolCallingProtocol.run_loop()` — multi-turn loop, `MAX_TOOL_TURNS=5` |
| Rate limiter | `rate_limiter.py` | `ProviderRateLimiter.acquire()` — Redis INCR-based RPM counter |
| Token counter | `token_counter.py` | `TokenCounter.count()`, `estimate_cost()` — tiktoken-based |

---

### 4.10 engine.integrations

| Sub-module | File | What to Build |
|---|---|---|
| MCP client | `mcp_client.py` | `MCPClient.list_tools()`, `call_tool()` — MCP protocol over HTTP/SSE |
| Tool executor | `tool_executor.py` | `ToolExecutor.execute()` — dispatch to MCP or REST based on tool type |
| REST adapter | `rest_adapter.py` | `RESTAdapter.call()` — Jinja2 templates, auth injection, HTTP with httpx |
| Webhook handler | `webhook_handler.py` | `WebhookHandler.validate_signature()` — HMAC-SHA256 |
| OAuth manager | `oauth_manager.py` | `OAuthManager.get_credentials()`, token refresh, PostgreSQL-backed |
| Adapter registry | `adapter_registry.py` | `AdapterRegistry` — plugin interface for custom adapters |

---

### 4.11 engine.cache

| Sub-module | File | What to Build |
|---|---|---|
| Semantic cache | `semantic.py` | `SemanticCache.check_semantic()`, `store_semantic()`, pgvector cosine similarity |
| MCP cache | `mcp_cache.py` | `MCPResponseCache.check()`, `store()` — Redis TTL |
| Key schema | `key_schema.py` | Cache key pattern constants + TTL values |

---

### 4.12 engine.versioning

| Sub-module | File | What to Build |
|---|---|---|
| Version manager | `manager.py` | `VersionManager.create_version()`, `list_versions()`, `rollback()` |
| Snapshot | `snapshot.py` | `create_snapshot()` — deep copy + freeze |
| Diff | `diff.py` | `compute_diff(v1, v2) → VersionDiff` — added/removed/changed nodes+edges |
| Pinning | `pinning.py` | `VersionPinner.pin_for_execution()`, `get_pinned()` |

---

### 4.13 engine.privacy

| Sub-module | File | What to Build |
|---|---|---|
| PII detector | `detector.py` | `PIIDetector.scan_dict()`, `scan_text()` — Presidio analyzer |
| PII masker | `masker.py` | `PIIMasker.mask_dict()`, `mask_text()` — offset-based token replacement |
| GDPR handler | `gdpr.py` | `GDPRHandler.delete_user_data()`, `check_data_residency()` |

---

### 4.14 engine.events

| Sub-module | File | What to Build |
|---|---|---|
| Event bus | `bus.py` | `EventBus.publish()`, `subscribe()` — Redis pub/sub backend |
| Handlers | `handlers.py` | `AuditEventHandler`, `MetricsEventHandler` |
| Audit logger | `audit.py` | `AuditLogger.record()` — append-only MongoDB writes |

---

## 5. Step-by-Step Development Roadmap

### Phase 0 — Foundation (Week 1)

**Objective:** Establish project scaffolding, tooling, CI, and the complete domain model layer. No logic yet — just structure and types.

| Step | Task | Output |
|---|---|---|
| 0.1 | Create monorepo structure with `packages/workflow-engine/` | Directory tree as per project structure |
| 0.2 | Write `pyproject.toml` with all dependencies declared | Installable package skeleton |
| 0.3 | Configure `ruff`, `mypy`, `pytest`, `pre-commit` hooks | Linting + type checking on commit |
| 0.4 | Set up GitHub Actions: lint → type-check → test → build | CI pipeline green on empty test suite |
| 0.5 | Implement `engine.config` — `EngineConfig` with all fields | Injected settings class |
| 0.6 | Implement `engine.models` — all 10 model files | Full domain vocabulary |
| 0.7 | Write unit tests for all models (field validation, enum values, serialization) | 100% model test coverage |
| 0.8 | Write `engine/__init__.py` public API re-exports | Clean import surface |

---

### Phase 1 — Structural Logic (Weeks 2–3)

**Objective:** Build the SDK's understanding of workflow shape — how to parse, validate, and represent a DAG.

| Step | Task | Output |
|---|---|---|
| 1.1 | Implement `engine.dag.topo_sort` — adjacency map + Kahn's algorithm | Deterministic topological order |
| 1.2 | Implement `engine.dag.parallel` — sibling detection + fan-in detection | Parallel groups and join points |
| 1.3 | Implement `engine.dag.plan` — `ExecutionPlan`, `ExecutionStep`, `StepType` | Structured execution blueprint |
| 1.4 | Implement `engine.dag.parser` — orchestrate topo sort + parallel into plan | `DAGParser.parse()` end-to-end |
| 1.5 | Write DAG tests: sequential, parallel, diamond, fork-join, complex graphs | 100% DAG branch coverage |
| 1.6 | Implement `engine.nodes.base` — `BaseNodeType` ABC | Enforced contract for all nodes |
| 1.7 | Implement `engine.nodes.registry` — singleton registry with CRUD | Registry unit tested |
| 1.8 | Stub all 7 built-in node type files (identity + ports + schema — no execute yet) | Registered in registry, queryable |
| 1.9 | Implement `engine.validation.cycle_detector` | Cycle detection with path reporting |
| 1.10 | Implement `engine.validation.port_checker` — compatibility matrix | Type-safe edge enforcement |
| 1.11 | Implement `engine.validation.schema` — jsonschema per node | Config validation per type |
| 1.12 | Implement `engine.validation.orphan_detector`, `duplicate_detector`, `plan_checker`, `expression` | All 7 checkers complete |
| 1.13 | Implement `engine.validation.pipeline` — orchestrates all checkers | `validate()` returns all errors |
| 1.14 | Write validation tests: valid workflows, each error type, multi-error accumulation | 100% validation branch coverage |

---

### Phase 2 — Runtime Execution Core (Weeks 4–5)

**Objective:** Build the execution runtime — state machine, context manager, and orchestrator. At the end of this phase, a workflow with stub nodes can be "run" end-to-end.

| Step | Task | Output |
|---|---|---|
| 2.1 | Implement `engine.state.transitions` — full transition allowlist tables | Enforced valid state machine |
| 2.2 | Implement `engine.state.persistence` — `StateStore` with MongoDB motor | Persistent state with optimistic locking |
| 2.3 | Implement `engine.state.machine` — `StateMachine.transition_run()` and `transition_node()` | Atomic state changes with timestamps |
| 2.4 | Write state machine tests: all valid transitions, all invalid transitions rejected | Full transition matrix tested |
| 2.5 | Implement `engine.context.redis_store` — TTL-aware Redis CRUD | Small output store |
| 2.6 | Implement `engine.context.gcs_store` — GCS upload/download | Large output store |
| 2.7 | Implement `engine.context.resolver` — edge traversal → port name mapping | Input resolution |
| 2.8 | Implement `engine.context.manager` — routing logic + `resolve_inputs()` | `store_output()` and `load_output()` |
| 2.9 | Write context tests with mocked Redis and GCS | Storage routing tested |
| 2.10 | Implement `engine.executor.retry` — exponential backoff with jitter | `RetryHandler` unit tested |
| 2.11 | Implement `engine.executor.timeout` — `asyncio.wait_for` wrapper | Timeout cancellation tested |
| 2.12 | Implement `engine.executor.dispatcher` — node type routing | Correct dispatch by `NodeType` |
| 2.13 | Implement `engine.executor.node_executor` — registry lookup + context build + dispatch | Single-node execution |
| 2.14 | Implement `engine.executor.orchestrator` — full run loop with parallel support | `RunOrchestrator.run()` working |
| 2.15 | Write executor integration tests with stub node types and real state+context (testcontainers) | End-to-end run lifecycle validated |

---

### Phase 3 — Platform Services (Weeks 6–8)

**Objective:** Build all sub-layer D capabilities — providers, sandbox, integrations, cache, versioning, privacy, events.

| Step | Task | Output |
|---|---|---|
| 3.1 | Implement `engine.sandbox.limits` — resource limit constants | Configurable limits |
| 3.2 | Implement `engine.sandbox.restricted` — `RestrictedPythonSandbox` with all guards | Safe code execution |
| 3.3 | Implement `engine.sandbox.manager` — tier selection and dispatch | `SandboxManager.execute()` |
| 3.4 | Write sandbox tests: safe code, blocked builtins, timeout, iteration limit, memory | Security controls validated |
| 3.5 | Implement `engine.providers.base` — `BaseProvider` ABC + `LLMResponse` | Provider interface |
| 3.6 | Implement `engine.providers.registry` — model-name map | Provider lookup |
| 3.7 | Implement `engine.providers.router` — `TierRouter` with fallback chain | Tier-based routing |
| 3.8 | Implement `engine.providers.rate_limiter` — Redis INCR-based RPM | Rate limit enforcement |
| 3.9 | Implement `engine.providers.token_counter` — tiktoken + cost matrix | Token and cost tracking |
| 3.10 | Implement `GeminiProvider` — Vertex AI async wrapper | Gemini Flash + Pro calls |
| 3.11 | Implement `AnthropicProvider` — Anthropic SDK async wrapper | Claude Haiku/Sonnet/Opus calls |
| 3.12 | Implement `OpenAIProvider` — OpenAI SDK async wrapper | GPT-4o-mini + GPT-4o calls |
| 3.13 | Implement `engine.providers.tool_calling` — `ToolCallingProtocol.run_loop()` | Multi-turn tool use |
| 3.14 | Write provider tests with mocked LLM responses; rate limit tests | Provider abstraction tested |
| 3.15 | Implement `engine.integrations.mcp_client` — tool discovery + execution | MCP protocol client |
| 3.16 | Implement `engine.integrations.rest_adapter` — templated HTTP calls + auth | Authenticated REST calls |
| 3.17 | Implement `engine.integrations.webhook_handler` — HMAC-SHA256 validation | Secure webhook ingestion |
| 3.18 | Implement `engine.integrations.oauth_manager` — token lifecycle | OAuth2 credential management |
| 3.19 | Implement `engine.integrations.adapter_registry` — plugin interface | Third-party adapter support |
| 3.20 | Write integration tests for MCP, REST, and webhook scenarios | Integration layer tested |
| 3.21 | Implement `engine.cache.key_schema` — all key patterns + TTL constants | Cache key standards |
| 3.22 | Implement `engine.cache.mcp_cache` — Redis TTL cache | MCP response caching |
| 3.23 | Implement `engine.cache.semantic` — embedding + pgvector similarity search | Semantic LLM cache |
| 3.24 | Write cache tests: hit, miss, similarity threshold, TTL expiry | Cache correctness tested |
| 3.25 | Implement `engine.versioning.snapshot` — deep copy + freeze | Immutable snapshots |
| 3.26 | Implement `engine.versioning.diff` — structural diff computation | Human-readable version diff |
| 3.27 | Implement `engine.versioning.pinning` — run-to-version mapping | Execution pinning |
| 3.28 | Implement `engine.versioning.manager` — full CRUD + rollback | Version management |
| 3.29 | Write versioning tests: create, list, diff, rollback scenarios | Versioning tested |
| 3.30 | Implement `engine.privacy.detector` — Presidio analyzer integration | PII entity detection |
| 3.31 | Implement `engine.privacy.masker` — offset-based token replacement | PII masking |
| 3.32 | Implement `engine.privacy.gdpr` — cross-store deletion pipeline | GDPR compliance |
| 3.33 | Write privacy tests: PII types, masking correctness, GDPR deletion | Privacy controls tested |
| 3.34 | Implement `engine.events.bus` — Redis pub/sub backend | Event publishing |
| 3.35 | Implement `engine.events.handlers` — audit + metrics handlers | Built-in event consumers |
| 3.36 | Implement `engine.events.audit` — append-only MongoDB writes | Audit trail |
| 3.37 | Write event bus tests: publish, subscribe, audit records | Event system tested |

---

### Phase 4 — Node Implementations (Week 9)

**Objective:** Implement the full `execute()` method for all 7 built-in node types. This phase depends on providers, integrations, cache, and sandbox being complete.

| Step | Task | Output |
|---|---|---|
| 4.1 | Implement `TriggerNodeType.execute()` — webhook, cron, manual, event payload production | Trigger execution working |
| 4.2 | Implement `AINodeType.execute()` — cache → rate limit → LLM → cache store → token track | Full AI node pipeline |
| 4.3 | Implement `MCPNodeType.execute()` — tool discover → params → MCP call → parse | MCP node execution |
| 4.4 | Implement `APINodeType.execute()` — template render → auth → HTTP → parse | HTTP integration node |
| 4.5 | Implement `LogicNodeType.execute()` — If/Else, For-Each, Switch, Merge, Delay | All logic sub-types |
| 4.6 | Implement `TransformNodeType.execute()` — sandbox Python + Jinja2 template | Data transform execution |
| 4.7 | Implement `HumanNodeType.execute()` — pause, notify, suspend, resume | Human-in-the-loop flow |
| 4.8 | Implement `CustomNodePlugin` ABC + `register_plugin()` on registry | Plugin system operational |
| 4.9 | Write end-to-end node execution tests for all 7 types with mocked services | All nodes tested in isolation |
| 4.10 | Write full workflow integration tests (5+ complex workflow scenarios) | Real workflows run end-to-end |

---

### Phase 5 — Hardening, Docs & Packaging (Week 10)

**Objective:** Production-readiness — observability hooks, documentation, packaging, and final QA.

| Step | Task | Output |
|---|---|---|
| 5.1 | Add OpenTelemetry trace instrumentation to executor, providers, integrations | Distributed tracing spans |
| 5.2 | Add Prometheus metric counters/histograms to providers, executor, cache | Metrics emitted |
| 5.3 | Audit all public API entry points for type correctness (`mypy --strict`) | Zero type errors |
| 5.4 | Write `CHANGELOG.md` for v1.0.0 | Release notes |
| 5.5 | Write `README.md` — quick start, install, basic usage | Developer onboarding |
| 5.6 | Write full API reference docstrings on all public classes and methods | Docstring coverage |
| 5.7 | Generate Sphinx or mkdocs HTML docs from docstrings | Documentation site |
| 5.8 | Run full test suite with `testcontainers` (real Mongo, Redis, Postgres) | Integration test suite green |
| 5.9 | Run `snyk test` + `pip-audit` on dependencies | Zero known CVEs |
| 5.10 | Finalize `pyproject.toml` classifiers, entry points, and build metadata | Package ready for registry |
| 5.11 | Build wheel + sdist: `python -m build` | `workflow_engine-1.0.0-py3-none-any.whl` |
| 5.12 | Publish to internal PyPI registry (or test.pypi.org for validation) | Installable from registry |

---

## 6. Recommended Tech Stack

### Core SDK Dependencies

| Library | Version | Role |
|---|---|---|
| `python` | 3.12+ | Runtime — use `match/case`, `asyncio.TaskGroup`, structural pattern matching |
| `pydantic` | v2.x | All domain models — fast validation, JSON schema generation |
| `pydantic-settings` | v2.x | `EngineConfig` — env var injection |
| `httpx` | 0.27+ | Async HTTP client for REST adapter and provider calls |
| `motor` | 3.x | Async MongoDB driver — state, audit, versioning |
| `redis[asyncio]` | 5.x | Async Redis — context store, rate limiting, pub/sub, cache |
| `asyncpg` | 0.29+ | Async PostgreSQL — pgvector semantic cache, OAuth credentials |
| `pgvector` | 0.3+ | Python pgvector extension for cosine similarity |
| `tiktoken` | 0.7+ | Token counting for OpenAI + Claude models |
| `RestrictedPython` | 7.x | AST-level Python sandboxing for TRANSFORM nodes |
| `presidio-analyzer` | 2.x | PII detection engine (Microsoft) |
| `presidio-anonymizer` | 2.x | PII masking/anonymization |
| `google-cloud-storage` | 2.x | GCS async blob storage for large outputs |
| `google-cloud-aiplatform` | 1.x | Vertex AI SDK for Gemini |
| `anthropic` | 0.x | Official Anthropic SDK for Claude |
| `openai` | 1.x | Official OpenAI SDK for GPT |
| `mcp` | latest | MCP protocol client SDK |
| `authlib` | 1.x | OAuth2 client + server primitives |
| `opentelemetry-sdk` | 1.x | Distributed tracing |
| `jinja2` | 3.x | Template rendering for prompts and API bodies |
| `jsonschema` | 4.x | Runtime JSON Schema validation for node configs |

### Development / QA Dependencies

| Library | Version | Role |
|---|---|---|
| `pytest` | 8.x | Test runner |
| `pytest-asyncio` | 0.23+ | Async test support |
| `testcontainers` | 4.x | Real MongoDB, Redis, Postgres in tests |
| `pytest-cov` | 5.x | Coverage reporting |
| `ruff` | 0.5+ | Linter + formatter (replaces flake8 + black) |
| `mypy` | 1.10+ | Static type checker |
| `pre-commit` | 3.x | Git hooks for lint + type check |
| `pact-python` | 2.x | Provider/consumer contract tests |

---

## 7. Design Considerations

### 7.1 Scalability

| Concern | Design Decision |
|---|---|
| **Parallel node execution** | `asyncio.gather()` in orchestrator; Celery `group/chord` at delivery layer — SDK expresses intent, delivery layer implements it |
| **Large output data** | Context manager auto-routes to GCS for outputs > 64KB — prevents Redis memory exhaustion |
| **Concurrent tenant isolation** | Semaphore logic lives in the delivery layer (API); SDK is stateless across tenants |
| **LLM rate limits** | Redis-based per-model RPM counter in `ProviderRateLimiter`; TierRouter falls back across model tiers |
| **Semantic cache** | pgvector cosine similarity prevents redundant LLM calls for semantically identical prompts |

### 7.2 Extensibility

| Extension Point | Mechanism |
|---|---|
| **New node types** | Register in `NodeTypeRegistry` — executor, validation, and UI pick up automatically |
| **New LLM providers** | Implement `BaseProvider` ABC + register in `ProviderRegistry` |
| **New integration adapters** | Implement adapter + register in `AdapterRegistry` |
| **Tenant custom nodes** | `CustomNodePlugin` ABC — plugged in at worker startup from tenant config |
| **New validation rules** | Add new checker class → register in `ValidationPipeline.checks` list |

### 7.3 Maintainability

| Concern | Decision |
|---|---|
| **Zero framework coupling** | `pyproject.toml` explicitly forbids `fastapi`, `celery`, `click` |
| **Single source of truth** | All models live in `engine.models` — API and worker never define their own schemas |
| **Strict import direction** | Sub-layer A → B → C → D only — CI import-linter enforces this |
| **Pure unit tests** | Engine tests need no HTTP server, no broker, no database (except persistence tests) |
| **Config injection** | `EngineConfig` is always injected — SDK never reads env vars directly, making test setup trivial |

### 7.4 Security

| Concern | Control |
|---|---|
| **User code execution** | RestrictedPython blocks file system, network, dangerous builtins |
| **PII in logs** | All log output passes through `PIIMasker` before emission |
| **LLM prompt injection** | Jinja2 templates use autoescape for user-supplied values |
| **Webhook authenticity** | HMAC-SHA256 signature verification before payload processing |
| **Credential storage** | OAuth tokens stored in PostgreSQL, never in Redis or logs |
| **Version immutability** | Saved workflow versions are frozen — executing a version always runs exactly what was saved |

### 7.5 Observability

| Signal | Where Generated | Backend |
|---|---|---|
| Traces | `executor`, `providers`, `integrations` | OpenTelemetry → Jaeger / GCP Trace |
| Metrics | `providers.rate_limiter`, `cache`, `executor` | Prometheus → Grafana |
| Structured logs | All modules — PII-masked before emit | Cloud Logging |
| Audit trail | `engine.events.audit` | MongoDB `audit_log` collection — append-only |

---

## 8. SDK Project Structure

```
packages/workflow-engine/
│
├── pyproject.toml                    # Package metadata, dependencies, build config
├── CHANGELOG.md                      # Semantic version changelog
├── README.md                         # Quick start and usage guide
│
├── src/
│   └── workflow_engine/
│       ├── __init__.py               # Public API re-exports
│       ├── config.py                 # EngineConfig (pydantic-settings)
│       │
│       ├── models/                   # SUB-LAYER A — Domain models
│       │   ├── __init__.py
│       │   ├── workflow.py           # WorkflowDefinition, WorkflowMetadata, RetryPolicy
│       │   ├── node.py               # NodeConfig, NodeType, PortDefinition, EdgeConfig
│       │   ├── execution.py          # ExecutionRun, NodeExecution, ExecutionStatus, NodeStatus
│       │   ├── version.py            # WorkflowVersion, VersionDiff, RollbackRecord
│       │   ├── trigger.py            # TriggerConfig, WebhookTrigger, CronTrigger
│       │   ├── context.py            # ExecutionContext, ContextRef
│       │   ├── events.py             # DomainEvent base + all subtypes
│       │   ├── tenant.py             # Tenant, Subscription, PlanTier
│       │   ├── provider.py           # LLMResponse, TokenUsage, ToolCall
│       │   └── errors.py             # Full typed exception hierarchy
│       │
│       ├── dag/                      # SUB-LAYER B — Topology
│       │   ├── __init__.py
│       │   ├── parser.py             # DAGParser.parse() → ExecutionPlan
│       │   ├── topo_sort.py          # Kahn's algorithm
│       │   ├── parallel.py           # Parallel branch detection
│       │   └── plan.py               # ExecutionPlan, ExecutionStep, StepType
│       │
│       ├── nodes/                    # SUB-LAYER B — Node type system
│       │   ├── __init__.py
│       │   ├── registry.py           # NodeTypeRegistry singleton
│       │   ├── base.py               # BaseNodeType ABC
│       │   ├── ai_node.py            # AINodeType
│       │   ├── mcp_node.py           # MCPNodeType
│       │   ├── api_node.py           # APINodeType
│       │   ├── logic_node.py         # LogicNodeType (5 sub-types)
│       │   ├── transform_node.py     # TransformNodeType
│       │   ├── trigger_node.py       # TriggerNodeType (4 sub-types)
│       │   ├── human_node.py         # HumanNodeType
│       │   └── custom.py             # CustomNodePlugin ABC
│       │
│       ├── validation/               # SUB-LAYER B — Validation pipeline
│       │   ├── __init__.py
│       │   ├── pipeline.py           # ValidationPipeline
│       │   ├── schema.py             # SchemaValidator
│       │   ├── cycle_detector.py     # CycleDetector (DFS)
│       │   ├── port_checker.py       # PortCompatibilityChecker
│       │   ├── plan_checker.py       # PlanAccessChecker
│       │   ├── orphan_detector.py    # OrphanNodeDetector
│       │   ├── duplicate_detector.py # DuplicateIdDetector
│       │   └── expression.py         # ExpressionValidator
│       │
│       ├── executor/                 # SUB-LAYER C — Execution engine
│       │   ├── __init__.py
│       │   ├── orchestrator.py       # RunOrchestrator
│       │   ├── node_executor.py      # NodeExecutor
│       │   ├── dispatcher.py         # NodeDispatcher
│       │   ├── retry.py              # RetryHandler
│       │   └── timeout.py            # TimeoutManager
│       │
│       ├── state/                    # SUB-LAYER C — State machine
│       │   ├── __init__.py
│       │   ├── machine.py            # StateMachine
│       │   ├── transitions.py        # Transition allowlists
│       │   └── persistence.py        # StateStore (MongoDB)
│       │
│       ├── context/                  # SUB-LAYER C — Data passing
│       │   ├── __init__.py
│       │   ├── manager.py            # ContextManager
│       │   ├── redis_store.py        # RedisContextStore
│       │   ├── gcs_store.py          # GCSContextStore
│       │   └── resolver.py           # InputResolver
│       │
│       ├── sandbox/                  # SUB-LAYER D — Code execution
│       │   ├── __init__.py
│       │   ├── manager.py            # SandboxManager
│       │   ├── restricted.py         # RestrictedPythonSandbox
│       │   ├── container.py          # ContainerSandbox (stub, v2)
│       │   └── limits.py             # Resource limit constants
│       │
│       ├── providers/                # SUB-LAYER D — LLM abstraction
│       │   ├── __init__.py
│       │   ├── base.py               # BaseProvider ABC
│       │   ├── registry.py           # ProviderRegistry
│       │   ├── router.py             # TierRouter
│       │   ├── gemini.py             # GeminiProvider
│       │   ├── anthropic.py          # AnthropicProvider
│       │   ├── openai.py             # OpenAIProvider
│       │   ├── tool_calling.py       # ToolCallingProtocol
│       │   ├── rate_limiter.py       # ProviderRateLimiter
│       │   └── token_counter.py      # TokenCounter
│       │
│       ├── integrations/             # SUB-LAYER D — External services
│       │   ├── __init__.py
│       │   ├── mcp_client.py         # MCPClient
│       │   ├── tool_executor.py      # ToolExecutor
│       │   ├── rest_adapter.py       # RESTAdapter
│       │   ├── webhook_handler.py    # WebhookHandler
│       │   ├── oauth_manager.py      # OAuthManager
│       │   └── adapter_registry.py   # AdapterRegistry
│       │
│       ├── cache/                    # SUB-LAYER D — Caching
│       │   ├── __init__.py
│       │   ├── semantic.py           # SemanticCache (pgvector)
│       │   ├── mcp_cache.py          # MCPResponseCache (Redis)
│       │   └── key_schema.py         # Key pattern constants
│       │
│       ├── versioning/               # SUB-LAYER D — Version control
│       │   ├── __init__.py
│       │   ├── manager.py            # VersionManager
│       │   ├── snapshot.py           # create_snapshot()
│       │   ├── diff.py               # compute_diff()
│       │   └── pinning.py            # VersionPinner
│       │
│       ├── privacy/                  # SUB-LAYER D — Compliance
│       │   ├── __init__.py
│       │   ├── detector.py           # PIIDetector (Presidio)
│       │   ├── masker.py             # PIIMasker
│       │   └── gdpr.py               # GDPRHandler
│       │
│       └── events/                   # SUB-LAYER D — Event bus
│           ├── __init__.py
│           ├── bus.py                # EventBus (Redis pub/sub)
│           ├── handlers.py           # AuditEventHandler, MetricsEventHandler
│           └── audit.py              # AuditLogger (MongoDB)
│
└── tests/
    ├── conftest.py                   # Shared fixtures, testcontainers setup
    ├── test_config/
    ├── test_models/
    ├── test_dag/
    ├── test_nodes/
    ├── test_validation/
    ├── test_executor/
    ├── test_state/
    ├── test_context/
    ├── test_sandbox/
    ├── test_providers/
    ├── test_integrations/
    ├── test_cache/
    ├── test_versioning/
    ├── test_privacy/
    └── test_events/
```

---

## 9. Core Interfaces & Abstractions

### 9.1 BaseNodeType — The Node Contract

Every node type must implement this interface. This is the single most important abstraction in the SDK.

```python
class BaseNodeType(ABC):
    # Identity (class attributes — set on the class, not instance)
    name:          NodeType          # Enum value — stored in DB
    display_name:  str               # Shown in UI palette
    category:      str               # UI palette grouping
    description:   str               # Tooltip text
    min_plan:      PlanTier          # Plan required to use this node
    sandbox_tier:  SandboxTier|None  # If None, no sandbox needed

    # Ports (class attributes)
    input_ports:   list[PortDefinition]
    output_ports:  list[PortDefinition]

    # Config (class attribute)
    config_schema: dict  # JSON Schema — drives UI form + validation

    # Methods
    @abstractmethod
    async def execute(
        self,
        config: dict,              # User-configured settings
        inputs: dict,              # Resolved from upstream nodes by port name
        ctx: ExecutionContext,     # Access to sandbox, cache, providers, integrations
    ) -> dict:                     # Output dict keyed by output port names
        ...

    def validate_config(self, config: dict) -> list[str]:
        """Override for cross-field validation. Default: JSON Schema check only."""
        ...
```

### 9.2 BaseProvider — The LLM Contract

```python
class BaseProvider(ABC):
    name:   str        # e.g., "anthropic"
    models: list[str]  # e.g., ["claude-haiku", "claude-sonnet", "claude-opus"]

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        config: dict,
    ) -> LLMResponse: ...

    @abstractmethod
    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        config: dict,
        messages: list[dict] | None = None,
    ) -> LLMResponse: ...
```

### 9.3 EngineConfig — Configuration Injection

```python
class EngineConfig(BaseSettings):
    # Always injected by consumers — SDK never reads env vars directly
    mongodb_url:                  str
    postgres_url:                 str
    redis_url:                    str
    gcs_bucket:                   str  = "workflow-artifacts"
    vertex_ai_project:            str  = ""
    anthropic_api_key:            str  = ""
    openai_api_key:               str  = ""
    sandbox_timeout_seconds:      int  = 30
    sandbox_max_memory_mb:        int  = 256
    sandbox_max_iterations:       int  = 10_000
    context_inline_threshold_kb:  int  = 64
    provider_rate_limit_window:   int  = 60
```

### 9.4 ValidationPipeline — The Validation Contract

```python
class ValidationPipeline:
    def validate(
        self,
        definition: WorkflowDefinition,
        tenant: Tenant | None = None,
    ) -> list[str]:
        """
        Run all registered checkers.
        Returns: empty list if valid, list of all error messages if invalid.
        Never raises — always returns the complete error list.
        """
```

### 9.5 RunOrchestrator — The Execution Entry Point

```python
class RunOrchestrator:
    async def run(
        self,
        run: ExecutionRun,
        definition: WorkflowDefinition,
    ) -> ExecutionRun:
        """
        Drive a complete workflow run from start to finish.
        Called by: Celery worker task (and directly in tests).
        Returns: final ExecutionRun state.
        """
```

---

## 10. Versioning & Packaging Strategy

### 10.1 Semantic Versioning

The SDK follows strict **Semantic Versioning** (`MAJOR.MINOR.PATCH`):

| Change Type | Version Bump | Examples |
|---|---|---|
| Breaking API change | MAJOR (`2.0.0`) | Renaming `NodeType` enum values, changing `execute()` signature |
| New backward-compatible feature | MINOR (`1.1.0`) | New node type, new provider, new validation checker |
| Bug fix | PATCH (`1.0.1`) | Fix retry backoff calculation, fix cycle detector edge case |

**Non-negotiable rule:** Once a `NodeType` enum value is published, it is **permanent**. Rename = breaking change = MAJOR bump. This is because enum values are persisted in MongoDB.

### 10.2 pyproject.toml Configuration

```toml
[project]
name = "workflow-engine"
version = "1.0.0"
description = "AI Workflow Builder — Core SDK"
requires-python = ">=3.12"
license = { text = "Proprietary" }

dependencies = [
    "pydantic>=2.7,<3",
    "pydantic-settings>=2.3,<3",
    "httpx>=0.27,<1",
    "motor>=3.4,<4",
    "redis[asyncio]>=5.0",
    "asyncpg>=0.29,<1",
    "pgvector>=0.3,<1",
    "tiktoken>=0.7,<1",
    "RestrictedPython>=7.0,<8",
    "presidio-analyzer>=2.2,<3",
    "presidio-anonymizer>=2.2,<3",
    "google-cloud-storage>=2.16,<3",
    "google-cloud-aiplatform>=1.50,<2",
    "anthropic>=0.28,<1",
    "openai>=1.30,<2",
    "mcp>=1.0,<2",
    "authlib>=1.3,<2",
    "jinja2>=3.1,<4",
    "jsonschema>=4.22,<5",
    "opentelemetry-sdk>=1.24,<2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 10.3 Distribution Channels

| Environment | Method | When |
|---|---|---|
| Local dev (monorepo) | `pip install -e ./packages/workflow-engine` | Daily development |
| Internal staging | Push to internal Artifactory / private PyPI | On merge to `main` |
| Production consumers | Pin exact version: `workflow-engine==1.2.3` | On release tag |
| Open-source (future) | Publish to PyPI | When public release decision made |

### 10.4 Dependency Pinning in Consumers

Consumers pin the SDK to an exact version in their `pyproject.toml`:

```toml
# In workflow-api/pyproject.toml
dependencies = [
    "workflow-engine==1.2.3",   # Always pin exact — never use >=
    "fastapi>=0.111,<1",
    ...
]
```

This prevents silent breaking changes when the SDK is updated. All three consumers (API, worker, CLI) must be updated together when the SDK version is bumped.

### 10.5 CI/CD Release Flow

```
Developer pushes to feature branch
          │
          ▼
CI: ruff lint → mypy --strict → pytest (unit) → pytest (integration w/ testcontainers)
          │ all green
          ▼
PR merged to main
          │
          ▼
CI: build wheel + sdist → publish to internal PyPI (pre-release suffix: 1.1.0rc1)
          │
          ▼
QA signs off on consumers running rc version
          │
          ▼
Release tag v1.1.0 → CI publishes final 1.1.0 to internal PyPI
          │
          ▼
Consumer repos update pinned version → deploy
```

---

> **workflow-engine SDK Roadmap v1.0**
> 15 modules | 4 internal sub-layers | 5 development phases | 10 weeks | Python 3.12 + Pydantic v2
> Built by: Senior Solution Architect + Senior AI Engineer
