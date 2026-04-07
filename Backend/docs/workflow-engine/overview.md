# workflow-engine SDK — Overview
## The Core Product

**Last updated:** 2026-04-07 — aligned with implemented codebase (`workflow-engine v1.0.0`)

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
                                           ✓ How to build AI-assisted workflows via chat
```

The SDK is a standalone Python package with its own `pyproject.toml`. It can be:
- Installed via `pip install ./packages/workflow-engine` (monorepo)
- Published to a private PyPI registry
- Versioned independently (`workflow-engine==1.0.0`)

---

## 2. Internal 4 Sub-Layer Model

```
SDK SUB-LAYER A — DOMAIN MODELS (foundation)
  engine.config      EngineConfig — injected by consumer at startup
  engine.models      All Pydantic v2 domain objects
  engine.errors      Exception hierarchy
  engine.ports       Abstract repository interfaces (never concrete)
        │
        ▼  (B imports A only)
SDK SUB-LAYER B — STRUCTURAL LOGIC (shape, not execution)
  engine.graph       GraphBuilder — DAG parsing, topological sort, port validation
  engine.nodes       NodeTypeRegistry + 17 built-in node implementations
        │
        ▼  (C imports A + B)
SDK SUB-LAYER C — RUNTIME EXECUTION
  engine.execution   RunOrchestrator + StateMachine + ContextManager + RetryHandler + PIIScanner
        │
        ▼  (D imports A + B + C as needed)
SDK SUB-LAYER D — PLATFORM SERVICES (cross-cutting)
  engine.chat          ChatOrchestrator — AI-assisted workflow creation (7-phase)
  engine.providers     LLM abstraction (Gemini/Claude/OpenAI/Bedrock/Mock)
  engine.sandbox       Python code sandbox (RestrictedPython — placeholder for gVisor/Firecracker)
  engine.integrations  MCP client + REST connectors (Slack, GitHub, Email)
  engine.cache         Semantic cache (pgvector) + Redis TTL cache
  engine.auth          JWT, password, API key, MFA, OAuth services
  engine.billing       UsageRecord, CostCalculator, QuotaChecker, Aggregator
  engine.storage       MongoDB repos + PostgreSQL repos + S3 storage
  engine.privacy       PII detection, masking, GDPR handler
  engine.events        Domain event bus
  engine.observability Structured logging, OTel tracing, Prometheus metrics
  engine.scheduler     Cron evaluation + schedule service
  engine.notifications Email + in-app notification channels
  engine.health        Dependency health probing
  engine.versioning    Immutable snapshot management
```

**Golden rule:** No circular imports. `engine.models` imports nothing from the SDK. `engine.graph` imports from `engine.models` only. `engine.execution` imports from models, graph, nodes, ports.

---

## 3. Module Map

| # | Module | Sub-layer | Primary Responsibility |
|---|---|---|---|
| 0 | `engine.config` | A | `EngineConfig` with nested `StorageConfig`, `LLMProvidersConfig`, `SandboxConfig` |
| 1 | `engine.models` | A | `WorkflowDefinition`, `ExecutionRun`, `TenantConfig`, `UserModel`, `ScheduleModel` |
| 2 | `engine.errors` | A | Exception hierarchy — `WorkflowEngineError`, `NodeExecutionError`, `SandboxTimeoutError`, `PIIBlockedError` |
| 3 | `engine.ports` | A | Abstract `ExecutionRepository`, `WorkflowRepository`, `ConversationRepository` interfaces |
| 4 | `engine.graph` | B | `GraphBuilder` — topological sort, layer grouping, DAG validation |
| 5 | `engine.nodes` | B | `NodeTypeRegistry`, `NodeType` (17 types), `BaseNodeType`, `PortCompatibilityChecker` |
| 6 | `engine.execution` | C | `RunOrchestrator`, `StateMachine`, `ContextManager`, `RetryHandler`, `TimeoutManager`, `PIIScanner` |
| 7 | `engine.chat` | D | `ChatOrchestrator` — 7-phase AI workflow creation from natural language |
| 8 | `engine.providers` | D | LLM provider factory (OpenAI, Google GenAI, Bedrock, Mock) |
| 9 | `engine.sandbox` | D | Code execution sandboxing (RestrictedPython Tier 1; gVisor/Firecracker placeholder) |
| 10 | `engine.integrations` | D | MCP client registry + built-in connectors (Slack, GitHub, Email) |
| 11 | `engine.cache` | D | `SemanticCache` (pgvector), `CachedLLM`, `RedisCache`, `KeyBuilder` |
| 12 | `engine.auth` | D | `JWTService`, `PasswordService`, `APIKeyService`, `MFAService`, `OAuthService` |
| 13 | `engine.billing` | D | `CostCalculator`, `UsageRecorder`, `QuotaChecker`, `Aggregator` |
| 14 | `engine.storage` | D | MongoDB repos (workflow, schedule, conversation) + PostgreSQL repos (tenant, user, billing) + S3 |
| 15 | `engine.privacy` | D | `PIIDetector`, `PIIMasker`, `GDPRHandler` |
| 16 | `engine.events` | D | Domain event bus |
| 17 | `engine.observability` | D | Structured logging, OTel tracing (`@trace_workflow`), Prometheus metrics |
| 18 | `engine.scheduler` | D | `SchedulerService` (cron tick), `cron_utils` |
| 19 | `engine.notifications` | D | Email + in-app notification channels |

---

## 4. Actual Package Structure

```
packages/workflow-engine/
├── pyproject.toml               # name="workflow-engine", version="1.0.0"
│                                # deps: pydantic, httpx, motor, redis[asyncio], asyncpg, etc.
│                                # FORBIDDEN: fastapi, celery, click, starlette, uvicorn
└── src/workflow_engine/
    ├── __init__.py              # Re-exports EngineConfig only
    ├── config.py                # EngineConfig (StorageConfig, TenantContextConfig, LLMProvidersConfig, SandboxConfig)
    ├── errors.py                # WorkflowEngineError, NodeExecutionError, SandboxTimeoutError,
    │                            # PIIBlockedError, WorkflowValidationError
    ├── ports.py                 # Abstract repository/port interfaces
    │
    ├── models/
    │   ├── workflow.py          # WorkflowDefinition, NodeDefinition, EdgeDefinition
    │   ├── execution.py         # ExecutionRun, NodeExecutionState, RunStatus
    │   ├── tenant.py            # TenantConfig, PlanTier, PIIPolicy, IsolationModel, UsageRecord
    │   ├── user.py              # UserModel, UserRole (OWNER, EDITOR, VIEWER)
    │   └── schedule.py          # ScheduleModel
    │
    ├── graph/
    │   ├── builder.py           # GraphBuilder.topological_sort(), topological_layers(), validate()
    │   └── validator.py         # WorkflowValidator
    │
    ├── nodes/
    │   ├── base.py              # BaseNodeType ABC, NodeOutput, NodeContext, NodeServices
    │   ├── registry.py          # NodeTypeRegistry singleton, NodeType (17 enum values),
    │   │                        # PortCompatibilityChecker, _PORT_OUTPUT_TYPES
    │   └── implementations/
    │       ├── triggers.py          # ManualTriggerNode, ScheduledTriggerNode, IntegrationTriggerNode
    │       ├── code_execution.py    # CodeExecutionNode (RestrictedPython + AST import scan)
    │       ├── prompt.py            # PromptNode (LLM call via providers)
    │       ├── agent.py             # AgentNode (tool-calling loop)
    │       ├── api_request.py       # APIRequestNode (httpx)
    │       ├── templating.py        # TemplatingNode (Jinja2)
    │       ├── control_flow.py      # ControlFlowNode (BRANCH/SWITCH/LOOP/MERGE)
    │       ├── set_state.py         # SetStateNode (run-scoped KV via Redis)
    │       ├── subworkflow.py       # SubworkflowNode (recursive orchestrator call)
    │       ├── semantic_search.py   # SemanticSearchNode
    │       ├── web_search.py        # WebSearchNode (SerpAPI)
    │       ├── mcp_node.py          # MCPNode (MCP tool execution)
    │       └── workflow_management.py # CustomNode, NoteNode, OutputNode
    │
    ├── execution/
    │   ├── orchestrator.py      # RunOrchestrator — main DAG traversal entry point
    │   │                        #   .run(workflow_def, run_id, tenant_id, trigger_input)
    │   │                        #   .resume(tenant_id, run_id, node_id, workflow_def, human_response)
    │   │                        #   .cancel(tenant_id, run_id)
    │   ├── state_machine.py     # StateMachine.transition_run() / transition_node()
    │   │                        # StateTransitionError on invalid transition
    │   ├── context_manager.py   # ContextManager.resolve_inputs() / store_output()
    │   │                        # 64KB inline threshold; large outputs offloaded to S3
    │   ├── retry_timeout.py     # RetryConfig, RetryHandler, TimeoutManager
    │   │                        # TimeoutManager.wrap() raises SandboxTimeoutError (not NodeExecutionError)
    │   └── pii_scanner.py       # PIIScanner.scan_dict() — respects TenantConfig.pii_policy
    │
    ├── chat/
    │   ├── models.py            # ConversationPhase (GATHERING/CLARIFYING/FINALIZING/GENERATING/COMPLETE)
    │   │                        # ChatSession, ChatMessage, RequirementSpec
    │   ├── orchestrator.py      # ChatOrchestrator.process_message() / update_workflow()
    │   │                        # ChatResponse, WorkflowUpdateResponse, ClarificationBlock
    │   ├── requirement_extractor.py   # RequirementExtractor
    │   ├── clarification_engine.py    # ClarificationEngine
    │   ├── dag_generator.py           # DAGGeneratorService
    │   └── workflow_layout.py         # WorkflowLayoutEngine, NodeUIConfigFactory
    │
    ├── auth/
    │   ├── jwt_service.py       # JWTService
    │   ├── password_service.py  # PasswordService (bcrypt)
    │   ├── api_key_service.py   # APIKeyService
    │   ├── mfa_service.py       # MFAService (TOTP via pyotp)
    │   ├── oauth_service.py     # OAuthService (authlib)
    │   └── rbac.py              # RBAC permission checks
    │
    ├── billing/
    │   ├── cost_calculator.py   # CostCalculator
    │   ├── usage_recorder.py    # UsageRecorder
    │   ├── aggregator.py        # Aggregator (hourly rollups)
    │   └── quota_checker.py     # QuotaChecker
    │
    ├── cache/
    │   ├── key_builder.py       # CacheKeyBuilder
    │   ├── semantic_cache.py    # SemanticCache (pgvector similarity)
    │   ├── cached_llm.py        # CachedLLM wrapper
    │   └── redis_cache.py       # RedisCache (TTL-based)
    │
    ├── events/
    │   └── bus.py               # EventBus
    │
    ├── integrations/
    │   ├── connectors/
    │   │   ├── base.py          # BaseConnector ABC
    │   │   ├── slack.py         # SlackConnector
    │   │   ├── email.py         # EmailConnector
    │   │   ├── github.py        # GitHubConnector
    │   │   └── registry.py      # ConnectorRegistry
    │   └── mcp/
    │       ├── client.py        # MCPClient
    │       └── registry.py      # MCPClientRegistry
    │
    ├── observability/
    │   ├── tracing.py           # @trace_workflow decorator (OTel)
    │   ├── logging.py           # Structured JSON logging
    │   └── metrics.py           # Prometheus metrics
    │
    ├── privacy/
    │   ├── detector.py          # PIIDetector (presidio-analyzer)
    │   ├── masker.py            # PIIMasker (presidio-anonymizer)
    │   ├── handler.py           # PIIHandler (orchestrates scan + policy)
    │   └── gdpr.py              # GDPRHandler (right to erasure, DPA)
    │
    ├── providers/
    │   ├── factory.py           # LLMProviderFactory
    │   ├── openai.py            # OpenAIProvider
    │   ├── google_genai.py      # GoogleGenAIProvider (google-genai unified SDK)
    │   └── mock.py              # MockLLMProvider (for tests)
    │
    ├── scheduler/
    │   ├── service.py           # SchedulerService.tick() — finds and fires due schedules
    │   └── cron_utils.py        # Cron expression evaluation (croniter)
    │
    ├── storage/
    │   ├── factory.py           # StorageFactory
    │   ├── s3_storage.py        # S3Storage (aioboto3)
    │   ├── mongo/
    │   │   ├── workflow_repo.py
    │   │   ├── schedule_repo.py
    │   │   └── conversation_repo.py
    │   └── postgres/
    │       ├── tenant_repo.py
    │       ├── user_repo.py
    │       └── billing_repo.py
    │
    ├── notifications/
    │   └── channels/            # Email + in-app notification channels
    │
    ├── health/                  # Dependency health probing
    ├── versioning/              # Immutable snapshot management
    └── sandbox/
        └── __init__.py          # Placeholder — CodeExecutionNode uses RestrictedPython directly;
                                 # gVisor (Tier 2) and Firecracker (Tier 3) not yet implemented
```

---

## 5. Key Models

### WorkflowDefinition

```python
class NodeDefinition(BaseModel):
    id: str
    type: str                     # NodeType enum value e.g. "CodeExecutionNode"
    config: dict[str, Any]
    position: dict[str, float]    # {"x": 0.0, "y": 0.0}

class EdgeDefinition(BaseModel):
    id: str
    source_node: str              # source node ID  ← NOT source_node_id
    target_node: str              # target node ID  ← NOT target_node_id
    source_port: str = "default"
    target_port: str = "default"

class WorkflowDefinition(BaseModel):
    id: str
    name: str
    nodes: dict[str, NodeDefinition]  # keyed by node_id
    edges: list[EdgeDefinition]
    ui_metadata: dict[str, Any]
```

### RunStatus

```python
class RunStatus(StrEnum):
    QUEUED        = "QUEUED"
    RUNNING       = "RUNNING"
    SUCCESS       = "SUCCESS"
    FAILED        = "FAILED"
    CANCELLED     = "CANCELLED"
    WAITING_HUMAN = "WAITING_HUMAN"
```

### TenantConfig

```python
class TenantConfig(BaseModel):
    tenant_id: str
    plan_tier: PlanTier = PlanTier.FREE             # FREE | STARTER | PRO | ENTERPRISE
    isolation_model: IsolationModel = IsolationModel.SHARED
    pii_policy: PIIPolicy = PIIPolicy.SCAN_WARN     # default: SCAN_WARN (not SCAN_MASK)
    quotas: dict[str, int] = {}
```

---

## 6. Public API Surface

Only `EngineConfig` is currently re-exported from `__init__.py`. Consumers import directly from sub-modules:

```python
from workflow_engine import EngineConfig

# Domain models
from workflow_engine.models import WorkflowDefinition, NodeDefinition, EdgeDefinition
from workflow_engine.models.execution import ExecutionRun, RunStatus, NodeExecutionState
from workflow_engine.models.tenant import TenantConfig, PlanTier, PIIPolicy, IsolationModel
from workflow_engine.models.user import UserModel, UserRole

# Execution
from workflow_engine.execution import RunOrchestrator
from workflow_engine.execution.state_machine import StateMachine, StateTransitionError
from workflow_engine.execution.retry_timeout import RetryConfig, RetryHandler, TimeoutManager

# Graph
from workflow_engine.graph.builder import GraphBuilder

# Nodes
from workflow_engine.nodes import NodeServices, NodeContext, NodeOutput
from workflow_engine.nodes.registry import NodeTypeRegistry, NodeType

# Errors
from workflow_engine.errors import (
    WorkflowEngineError, NodeExecutionError,
    SandboxTimeoutError, PIIBlockedError,
    WorkflowValidationError,
)

# Chat
from workflow_engine.chat.orchestrator import ChatOrchestrator, ChatResponse

# Auth
from workflow_engine.auth.jwt_service import JWTService
```

---

## 7. SDK Dependencies (`pyproject.toml`)

```toml
[project]
name = "workflow-engine"
version = "1.0.0"
requires-python = ">=3.12"

dependencies = [
    # Core
    "pydantic>=2.7,<3",
    "pydantic-settings>=2.3,<3",
    "httpx>=0.27,<1",

    # Databases
    "motor>=3.4,<4",               # Async MongoDB
    "redis[asyncio]>=5.0,<6",
    "asyncpg>=0.29,<1",            # Async PostgreSQL
    "pgvector>=0.3,<1",

    # Storage
    "aioboto3>=12.0,<13",          # Async S3

    # LLM Providers
    "anthropic>=0.28,<1",
    "openai>=1.30,<2",
    "google-genai>=1.0,<2",        # Google Gemini (new unified SDK)
    "boto3>=1.34,<2",              # Amazon Bedrock

    # Sandbox
    "RestrictedPython>=7.0,<8",

    # Privacy
    "presidio-analyzer>=2.2,<3",
    "presidio-anonymizer>=2.2,<3",

    # Auth
    "PyJWT>=2.8,<3",
    "bcrypt>=4.1,<5",
    "pyotp>=2.9,<3",               # TOTP/MFA
    "authlib>=1.3,<2",             # OAuth2

    # MCP
    "mcp>=1.0",

    # Templating, Validation & Data Query
    "jinja2>=3.1,<4",
    "jsonschema>=4.22,<5",
    "jmespath>=1.0,<2",            # ControlFlowNode LOOP/BRANCH

    # Scheduling
    "croniter>=2.0,<3",
    "pytz>=2024.1",

    # Token counting
    "tiktoken>=0.7,<1",

    # Observability
    "opentelemetry-sdk>=1.24,<2",
    "opentelemetry-instrumentation-httpx>=0.45b0",
    "prometheus-client>=0.20,<1",
    "python-json-logger>=3.0,<4",
]

# FORBIDDEN: fastapi, celery, click, starlette, uvicorn, boto3-based AWS services
# SDK must remain framework-agnostic
```
