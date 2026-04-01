# workflow-engine SDK — Overview
## The Core Product

---

## 1. Mental Model

> `workflow-engine` is not a dependency you install. It is the proprietary Python library you are authoring. Everything else (API, Worker, CLI, UI) is a delivery mechanism for this SDK.

```
workflow-engine knows NOTHING about:     workflow-engine knows EVERYTHING about:
  ✗ FastAPI                                ✓ What a workflow DAG is
  ✗ Celery                                 ✓ How to parse and validate it
  ✗ Click                                  ✓ How to execute nodes in topological order
  ✗ HTTP request/response                  ✓ How to call LLMs (Gemini/Claude/OpenAI/Bedrock)
  ✗ Task queues                            ✓ How to sandbox user Python code
  ✗ Web frameworks                         ✓ How to manage run lifecycle state
  ✗ AWS-specific APIs                      ✓ How to cache LLM responses semantically
                                           ✓ How to detect and mask PII
                                           ✓ How to track token usage and cost
```

The SDK is a standalone Python package with its own `pyproject.toml`. It can be:
- Installed via `pip install ./packages/workflow-engine` (monorepo)
- Published to a private PyPI registry
- Versioned independently (`workflow-engine==1.3.0`)

---

## 2. Internal 4 Sub-Layer Model

```
SDK SUB-LAYER A — DOMAIN MODELS (foundation)
  engine.config    EngineConfig — injected by consumer at startup
  engine.models    All Pydantic v2 domain objects
        │
        ▼  (B imports A only)
SDK SUB-LAYER B — STRUCTURAL LOGIC (shape, not execution)
  engine.dag        DAG parsing → ExecutionPlan
  engine.nodes      NodeTypeRegistry + 7 built-in node type definitions
  engine.validation ValidationPipeline → list of errors
        │
        ▼  (C imports A + B)
SDK SUB-LAYER C — RUNTIME EXECUTION
  engine.executor   RunOrchestrator + NodeExecutor
  engine.state      StateMachine + StateStore
  engine.context    ContextManager + S3Store + RedisStore
        │
        ▼  (D imports A + B + C as needed)
SDK SUB-LAYER D — PLATFORM SERVICES (cross-cutting)
  engine.providers     LLM abstraction (Gemini/Claude/OpenAI/Bedrock)
  engine.sandbox       Python code sandbox (RestrictedPython + gVisor)
  engine.integrations  MCP client + REST adapter + OAuth
  engine.cache         Semantic cache (pgvector) + MCP cache (Redis TTL)
  engine.versioning    Immutable snapshot management
  engine.privacy       PII detection + masking (Presidio)
  engine.events        Domain event bus + AuditLogger
  engine.auth          Token, password, API key, MFA
  engine.billing       UsageTracker + QuotaChecker + CostCalculator
  engine.health        Dependency health checks
  engine.scheduler     Cron evaluation + trigger dispatch
  engine.notifications Email + in-app notification channels
```

**Golden rule:** No circular imports. `engine.models` imports nothing from the SDK. `engine.dag` imports from `engine.models` only. `engine.executor` imports from models, dag, nodes, state, and context.

---

## 3. Complete Module Map

| # | Module | Sub-layer | Primary Responsibility |
|---|---|---|---|
| 0 | `engine.config` | A | Configuration injection |
| 1 | `engine.models` | A | All domain data models |
| 2 | `engine.dag` | B | Workflow topology analysis |
| 3 | `engine.nodes` | B | Node type system + registry |
| 4 | `engine.validation` | B | Pre-execution validation |
| 5 | `engine.executor` | C | Drive full workflow run |
| 6 | `engine.state` | C | Run/node lifecycle state |
| 7 | `engine.context` | C | Inter-node data transfer |
| 8 | `engine.sandbox` | D | Safe Python code execution |
| 9 | `engine.providers` | D | LLM abstraction + routing |
| 10 | `engine.integrations` | D | MCP + REST + Webhooks + OAuth |
| 11 | `engine.cache` | D | LLM + MCP response caching |
| 12 | `engine.versioning` | D | Immutable snapshot management |
| 13 | `engine.privacy` | D | PII scan + mask + GDPR |
| 14 | `engine.events` | D | Domain event bus |
| 15 | `engine.auth` | D | Authentication primitives |
| 16 | `engine.billing` | D | Usage tracking + quota enforcement |
| 17 | `engine.health` | D | Infrastructure health probing |
| 18 | `engine.scheduler` | D | Cron trigger evaluation |
| 19 | `engine.notifications` | D | Email + in-app notifications |

---

## 4. Package Structure

```
packages/workflow-engine/
├── pyproject.toml               # name="workflow-engine", version="1.0.0"
│                                # deps: pydantic, httpx, motor, aioredis, asyncpg
│                                # NO fastapi, NO celery, NO click
└── src/workflow_engine/
    ├── __init__.py              # Public API re-exports
    ├── config.py                # EngineConfig
    │
    ├── models/
    │   ├── errors.py            # Exception hierarchy (built first)
    │   ├── tenant.py            # Tenant, PlanTier, IsolationModel
    │   ├── node.py              # NodeConfig, NodeType, PortDefinition
    │   ├── workflow.py          # WorkflowDefinition, WorkflowMetadata
    │   ├── execution.py         # ExecutionRun, NodeExecution, ExecutionStatus
    │   ├── trigger.py           # TriggerConfig subtypes
    │   ├── context.py           # ExecutionContext, ContextRef
    │   ├── events.py            # DomainEvent subtypes
    │   ├── version.py           # WorkflowVersion, VersionDiff
    │   ├── provider.py          # LLMResponse, TokenUsage, ToolCall
    │   ├── requests.py          # SDK-level request schemas
    │   └── responses.py         # PaginatedResponse, ErrorResponse
    │
    ├── dag/
    │   ├── plan.py              # ExecutionPlan, ExecutionStep, StepType
    │   ├── topo_sort.py         # Kahn's algorithm
    │   ├── parallel.py          # Parallel branch detection
    │   └── parser.py            # DAGParser.parse() → ExecutionPlan
    │
    ├── nodes/
    │   ├── base.py              # BaseNodeType ABC
    │   ├── registry.py          # NodeTypeRegistry singleton
    │   ├── trigger_node.py      # TriggerNodeType
    │   ├── ai_node.py           # AINodeType
    │   ├── api_node.py          # APINodeType
    │   ├── logic_node.py        # LogicNodeType
    │   ├── transform_node.py    # TransformNodeType
    │   ├── mcp_node.py          # MCPNodeType
    │   └── human_node.py        # HumanNodeType
    │
    ├── validation/
    │   ├── pipeline.py          # ValidationPipeline (runs all checkers)
    │   ├── cycle_detector.py
    │   ├── duplicate_detector.py
    │   ├── orphan_detector.py
    │   ├── schema.py
    │   ├── port_checker.py
    │   ├── plan_checker.py
    │   └── expression.py
    │
    ├── executor/
    │   ├── orchestrator.py      # RunOrchestrator — main entry point
    │   ├── node_executor.py
    │   ├── dispatcher.py
    │   ├── retry.py
    │   └── timeout.py
    │
    ├── state/
    │   ├── transitions.py
    │   ├── persistence.py
    │   └── machine.py
    │
    ├── context/
    │   ├── redis_store.py
    │   ├── s3_store.py          # S3 replaces GCS
    │   ├── resolver.py
    │   ├── manager.py
    │   └── trace.py             # OTel context propagation
    │
    ├── sandbox/
    │   ├── limits.py
    │   ├── restricted.py        # Tier 1: RestrictedPython
    │   ├── container.py         # Tier 2: gVisor
    │   ├── microvm.py           # Tier 3: Firecracker
    │   └── manager.py           # Tier selection and dispatch
    │
    ├── providers/
    │   ├── base.py
    │   ├── registry.py
    │   ├── router.py
    │   ├── gemini.py
    │   ├── anthropic.py
    │   ├── openai.py
    │   ├── bedrock.py           # Amazon Bedrock provider
    │   ├── tool_calling.py
    │   ├── rate_limiter.py
    │   └── token_counter.py
    │
    ├── integrations/
    │   ├── mcp_client.py
    │   ├── tool_executor.py
    │   ├── rest_adapter.py
    │   ├── webhook_handler.py
    │   ├── oauth_manager.py
    │   └── connectors/          # Built-in service connectors
    │       ├── slack.py
    │       ├── email.py
    │       ├── discord.py
    │       ├── teams.py
    │       ├── google_sheets.py
    │       ├── s3_connector.py
    │       ├── onedrive.py
    │       ├── postgres_connector.py
    │       ├── mysql_connector.py
    │       ├── mongodb_connector.py
    │       ├── redis_connector.py
    │       ├── github.py
    │       └── salesforce.py
    │
    ├── cache/
    │   ├── key_schema.py
    │   ├── mcp_cache.py
    │   └── semantic.py
    │
    ├── versioning/
    │   ├── snapshot.py
    │   ├── diff.py
    │   ├── pinning.py
    │   └── manager.py
    │
    ├── privacy/
    │   ├── detector.py
    │   ├── masker.py
    │   └── gdpr.py
    │
    ├── events/
    │   ├── bus.py
    │   ├── handlers.py
    │   └── audit.py
    │
    ├── auth/
    │   ├── models.py
    │   ├── token.py
    │   ├── password.py
    │   ├── api_key.py
    │   ├── session.py
    │   └── mfa.py
    │
    ├── billing/
    │   ├── models.py
    │   ├── cost_calculator.py
    │   ├── quota_checker.py
    │   ├── usage_tracker.py
    │   └── report.py
    │
    ├── health/
    │   ├── models.py
    │   ├── checker.py
    │   └── reporter.py
    │
    ├── scheduler/
    │   ├── cron_evaluator.py
    │   ├── trigger_finder.py
    │   └── dispatcher.py
    │
    └── notifications/
        ├── dispatcher.py
        ├── models.py
        └── channels/
            ├── email.py
            └── inapp.py
```

---

## 5. Public API Surface (`__init__.py`)

The SDK exposes a clean public interface. Consumers import only from the top level:

```python
from workflow_engine import (
    # Config
    EngineConfig,

    # Models
    WorkflowDefinition, NodeConfig, NodeType,
    ExecutionRun, ExecutionStatus, NodeStatus,
    WorkflowVersion, Tenant, PlanTier,

    # Errors
    EngineError, ValidationError, NodeExecutionError,
    NotFoundError, QuotaExceededError,

    # Core operations
    validate,           # engine.validation.pipeline.validate()
    parse_dag,          # engine.dag.parser.DAGParser().parse()
    create_version,     # engine.versioning.manager.create_version()
    RunOrchestrator,    # engine.executor.orchestrator.RunOrchestrator

    # Registry
    NodeTypeRegistry,

    # Events
    EventBus,
)
```

---

## 6. SDK Dependencies (`pyproject.toml`)

```toml
[project]
name = "workflow-engine"
version = "1.0.0"
requires-python = ">=3.12"

dependencies = [
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "httpx>=0.27",
    "motor>=3.4",
    "aioredis>=2.0",
    "asyncpg>=0.29",
    "pgvector>=0.3",
    "tiktoken>=0.7",
    "RestrictedPython>=7.0",
    "presidio-analyzer>=2.2",
    "presidio-anonymizer>=2.2",
    "boto3>=1.34",           # S3 operations
    "aioboto3>=12.0",        # Async S3
    "anthropic>=0.28",
    "openai>=1.30",
    "google-cloud-aiplatform>=1.50",
    "boto3-stubs[bedrock-runtime]",
    "mcp>=1.0",
    "authlib>=1.3",
    "opentelemetry-sdk>=1.24",
    "opentelemetry-instrumentation-httpx>=0.45",
    "jinja2>=3.1",
    "jsonschema>=4.22",
    "python-croniter>=2.0",
    "pyotp>=2.9",            # TOTP/MFA
    "bcrypt>=4.1",
    "PyJWT>=2.8",
]

# FORBIDDEN: fastapi, celery, click, starlette, uvicorn, boto3-based AWS services
# SDK must remain framework-agnostic
```
