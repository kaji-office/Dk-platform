# Node Framework — Overview
## Built-in Node Type System

---

## 1. Core Principle

**Nodes are built exclusively by the platform development team.** They are part of the `workflow-engine` SDK. Users configure nodes through the UI — they never author, upload, or deploy node types.

User logic enters the platform through exactly one controlled entry point: the `CodeExecutionNode` sandbox. All other nodes use declarative configuration, not user-provided code. The `CustomNode` type allows the platform SDK team to define additional logic primitives for specific product verticals.

---

## 2. Node Taxonomy

There are **17 node types** across 4 categories plus a trigger group.

| Category | Nodes |
|----------|-------|
| AI & Reasoning | `PROMPT`, `AGENT`, `SEMANTIC_SEARCH` |
| Execution & Data | `CODE_EXECUTION`, `API_REQUEST`, `TEMPLATING`, `WEB_SEARCH`, `MCP` |
| Workflow Management | `SET_STATE`, `CUSTOM`, `NOTE`, `OUTPUT` |
| Logic & Orchestration | `CONTROL_FLOW`, `SUBWORKFLOW` |
| Triggers | `MANUAL_TRIGGER`, `SCHEDULED_TRIGGER`, `INTEGRATION_TRIGGER` |

> **`MCP` feature flag:** Disabled by default (`MCP_NODE_ENABLED=false` in `.env`). Enabled per tenant by the platform team. Available on PRO and ENTERPRISE plans.

---

## 3. Node Type Registry

The `NodeTypeRegistry` is a singleton initialized at application startup. It maps `NodeType` enum values to their implementing class instances.

```python
# workflow_engine/nodes/registry.py

class NodeTypeRegistry:
    def __init__(self):
        self._nodes: dict[NodeType, BaseNodeType] = {}
        self._register_built_ins()

    def _register_built_ins(self) -> None:
        # AI & Reasoning
        self.register(NodeType.PROMPT,               PromptNodeType())
        self.register(NodeType.AGENT,                AgentNodeType())
        self.register(NodeType.SEMANTIC_SEARCH,      SemanticSearchNodeType())

        # Execution & Data
        self.register(NodeType.CODE_EXECUTION,       CodeExecutionNodeType())
        self.register(NodeType.API_REQUEST,          APIRequestNodeType())
        self.register(NodeType.TEMPLATING,           TemplatingNodeType())
        self.register(NodeType.WEB_SEARCH,           WebSearchNodeType())
        self.register(NodeType.MCP,                  MCPNodeType())          # feature-flagged

        # Workflow Management
        self.register(NodeType.SET_STATE,            SetStateNodeType())
        self.register(NodeType.CUSTOM,               CustomNodeType())
        self.register(NodeType.NOTE,                 NoteNodeType())
        self.register(NodeType.OUTPUT,               OutputNodeType())

        # Logic & Orchestration
        self.register(NodeType.CONTROL_FLOW,         ControlFlowNodeType())
        self.register(NodeType.SUBWORKFLOW,          SubworkflowNodeType())

        # Triggers
        self.register(NodeType.MANUAL_TRIGGER,       ManualTriggerNodeType())
        self.register(NodeType.SCHEDULED_TRIGGER,    ScheduledTriggerNodeType())
        self.register(NodeType.INTEGRATION_TRIGGER,  IntegrationTriggerNodeType())

    def register(self, node_type: NodeType, handler: BaseNodeType) -> None:
        self._nodes[node_type] = handler

    def get(self, node_type: NodeType) -> BaseNodeType:
        if node_type not in self._nodes:
            raise NotFoundError(f"Node type {node_type} not registered")
        return self._nodes[node_type]

    def list_all(self) -> list[NodeTypeSummary]:
        return [node.to_summary() for node in self._nodes.values()]

    def get_config_schema(self, node_type: NodeType) -> dict:
        return self.get(node_type).config_schema
```

---

## 4. BaseNodeType Contract

Every node type implements this interface:

```python
# workflow_engine/nodes/base.py

class NodeServices:
    """Injected into every node execute() call. Nodes access platform
    capabilities through this object — never directly importing modules."""
    providers: ProviderRegistry      # LLM providers (Anthropic / OpenAI / Google / Bedrock)
    sandbox: SandboxManager          # code execution tiers (Tier 1–3)
    integrations: IntegrationRegistry
    mcp: MCPClientRegistry           # MCP server connections + tool discovery/invocation
    cache: CacheManager              # Redis + semantic cache (pgvector)
    storage: StoragePort             # S3 context offload
    context: ContextManager          # workflow run-scoped state (SetState / GetState)
    events: EventBus
    search: SearchService            # semantic search + web search
    config: EngineConfig

class NodeOutput:
    outputs: dict[str, Any]    # keyed by output port name
    metadata: dict[str, Any]   # tokens, latency, cost, etc.
    logs: list[str]             # node-level execution log lines

class BaseNodeType(ABC):
    node_type: NodeType
    display_name: str
    description: str
    category: str               # AI | Data | Logic | Trigger | Utility
    icon: str                   # icon identifier for UI
    isolation_tier: int         # 0 = in-process | 1 = RestrictedPython | 2 = gVisor | 3 = Firecracker
    config_schema: dict         # JSON Schema — drives DynamicConfigForm in UI
    input_ports: list[PortDefinition]
    output_ports: list[PortDefinition]
    plan_tier_required: PlanTier
    is_executable: bool = True  # NOTE node sets this to False

    @abstractmethod
    async def execute(
        self,
        node_config: NodeConfig,
        resolved_inputs: dict[str, Any],
        execution_context: ExecutionContext,
        services: NodeServices,
    ) -> NodeOutput:
        """
        Execute the node. Rules:
        - MUST be idempotent (safe to retry)
        - MUST NOT access databases directly — use services
        - MUST NOT import framework code (FastAPI, Celery, Click)
        - MUST respect execution_context.timeout_remaining
        - MUST publish NodeStarted and NodeCompleted/NodeFailed via services.events
        """
        ...

    @abstractmethod
    def validate_config(self, config: dict) -> list[str]:
        """Return list of error strings. Empty list = valid config."""
        ...
```

---

## 5. Node Type Reference

### Master Summary Table

| Node | Category | Isolation | Plan | Input Ports | Output Ports |
|------|----------|-----------|------|-------------|--------------|
| `PROMPT` | AI | Tier 0 | FREE | `variables` | `response`, `token_usage` |
| `AGENT` | AI | Tier 0 | STARTER | `input`, `tools` | `response`, `tool_calls`, `token_usage` |
| `SEMANTIC_SEARCH` | AI | Tier 0 | STARTER | `query` | `chunks`, `scores` |
| `CODE_EXECUTION` | Data | Tier 2 | STARTER | `input` | `output`, `logs` |
| `API_REQUEST` | Data | Tier 1 | FREE | `params`, `body`, `headers` | `body`, `status_code`, `headers` |
| `TEMPLATING` | Data | Tier 0 | FREE | `variables` | `result` |
| `WEB_SEARCH` | Data | Tier 1 | PRO | `query` | `results`, `snippets` |
| `MCP` | Data | Tier 2 | PRO ¹ | `tool_input` | `result`, `tool_metadata` |
| `SET_STATE` | Utility | Tier 0 | FREE | `value` | `state` |
| `CUSTOM` | Utility | Tier 1 | PRO | defined by SDK author | defined by SDK author |
| `NOTE` | Utility | — (no-op) | FREE | none | none |
| `OUTPUT` | Utility | Tier 0 | FREE | `value` | none |
| `CONTROL_FLOW` | Logic | Tier 0 | FREE | `input` | `true`, `false`, `items`, `merged` |
| `SUBWORKFLOW` | Logic | Tier 0 | STARTER | `input` | `output` |
| `MANUAL_TRIGGER` | Trigger | Tier 0 | FREE | none | `payload` |
| `SCHEDULED_TRIGGER` | Trigger | Tier 0 | FREE | none | `payload` |
| `INTEGRATION_TRIGGER` | Trigger | Tier 0 | STARTER | none | `payload` |

> ¹ `MCP` node requires `MCP_NODE_ENABLED=true` (feature flag). Disabled by default. Available on PRO plan and above. Enterprise tenants can connect private MCP servers.

---

## 6. AI & Reasoning Nodes

### 6.1 PromptNode

Sends a prompt template to an LLM and returns the text response. No tool calling — for pure generation and extraction tasks.

**Typical use case:** Summarizing a document, classifying intent, extracting structured fields from free text.

**Execution pipeline:**
```
1. Render system + user prompt templates (Jinja2 with resolved_inputs)
2. Check semantic cache (pgvector cosine similarity ≥ 0.95)
   hit  → return cached response (no LLM call, zero token cost)
   miss → continue
3. Acquire rate-limit token (Redis RPM counter per tenant)
4. Route to configured provider (Anthropic / OpenAI / Vertex AI / Bedrock)
5. LLM generate() call — streaming internally, buffered output
6. Store response embedding in semantic cache
7. Record token usage → engine.billing.UsageTracker
8. Return NodeOutput { response, token_usage: { input, output, cost_usd } }
```

**Config schema:**
```json
{
  "provider": { "enum": ["anthropic", "openai", "google", "bedrock"] },
  "model": { "type": "string", "example": "claude-sonnet-4-6" },
  "system_prompt": { "type": "string" },
  "user_prompt_template": { "type": "string", "description": "Jinja2 template" },
  "temperature": { "type": "number", "minimum": 0, "maximum": 2, "default": 0.7 },
  "max_tokens": { "type": "integer", "default": 1024 },
  "use_semantic_cache": { "type": "boolean", "default": true },
  "output_format": { "enum": ["text", "json"], "default": "text" }
}
```

**Supported models:** `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`, `gpt-4o`, `gpt-4o-mini`, `gemini-2.0-flash`, `gemini-2.0-pro`, `bedrock-claude-sonnet`

---

### 6.2 AgentNode

A higher-level node that handles the full **function-calling loop** automatically:
`LLM decides to use a tool → Tool executes → Result returned to LLM → Repeat until done`

**Typical use case:** A chatbot that can query a database, call a calculator, and then reply. Any scenario requiring multiple tool calls before producing a final answer.

**Execution pipeline:**
```
1. Receive input + list of available tool definitions
2. Send initial message + tool schemas to LLM
3. Loop (max_iterations):
   a. LLM returns text OR tool_call
   b. If text → done, return response
   c. If tool_call → dispatch to NodeServices.integrations
   d. Append tool result to message history
   e. Send updated history back to LLM
4. If max_iterations reached → return partial result with warning
5. Record total token usage across all loop iterations
```

**Config schema:**
```json
{
  "provider": { "enum": ["anthropic", "openai", "google"] },
  "model": { "type": "string" },
  "system_prompt": { "type": "string" },
  "tools": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "description": { "type": "string" },
        "input_schema": { "type": "object" }
      }
    }
  },
  "max_iterations": { "type": "integer", "default": 10, "maximum": 25 },
  "temperature": { "type": "number", "default": 0.3 }
}
```

---

### 6.3 SemanticSearchNode (RAG)

Connects to the platform's vector store. Takes a query, searches indexed document chunks by cosine similarity, and returns the most relevant passages as context.

**Typical use case:** Answering user questions from a private PDF manual, company knowledge base, or any uploaded document set.

**Execution pipeline:**
```
1. Embed query using configured embedding model (text-embedding-3-small / voyage-3)
2. Query pgvector index with cosine similarity (top_k results, threshold filter)
3. Optionally re-rank results using a cross-encoder
4. Return chunks with scores
```

**Config schema:**
```json
{
  "index_id": { "type": "string", "description": "Document index to search" },
  "embedding_model": { "enum": ["text-embedding-3-small", "voyage-3"], "default": "text-embedding-3-small" },
  "top_k": { "type": "integer", "default": 5, "maximum": 20 },
  "similarity_threshold": { "type": "number", "default": 0.7 },
  "rerank": { "type": "boolean", "default": false }
}
```

**Ports:**
- Input: `query` (string)
- Output: `chunks` (array of strings), `scores` (array of numbers), `metadata` (array of objects)

---

## 7. Execution & Data Nodes

### 7.1 CodeExecutionNode

Runs custom Python code in a secure sandboxed environment. This is the **only node where users provide executable logic**. The platform enforces strict import restrictions.

**Typical use case:** Complex data transformation, business logic that is too advanced for templating, risk score calculation, currency conversion.

**Sandbox tiers applied:**
- Default: **Tier 2 (gVisor)** — network disabled, filesystem restricted
- ENTERPRISE tenants may configure **Tier 3 (Firecracker)** for full isolation

**Execution pipeline:**
```
1. Static analysis of user code (AST scan — reject forbidden imports)
2. Provision gVisor container (pre-warmed pool)
3. Inject `input` variable (dict from resolved_inputs)
4. Execute user code with CPU + memory limits
5. Capture `output` variable + stdout logs
6. Destroy container
7. Return NodeOutput { output, logs }
```

**Available in sandbox:** `json`, `math`, `re`, `datetime`, `decimal`, `collections`, `itertools`, `functools`

**Forbidden in sandbox:** `os`, `sys`, `subprocess`, `socket`, `open`, `eval`, `exec`, `__import__`, `requests`, `httpx`

**Config schema:**
```json
{
  "language": { "enum": ["python"], "default": "python" },
  "code": { "type": "string", "description": "Python code. Use `input` dict for inputs, populate `output` dict." },
  "timeout_seconds": { "type": "integer", "default": 30, "maximum": 300 },
  "memory_mb": { "type": "integer", "default": 256, "maximum": 1024 }
}
```

---

### 7.2 APIRequestNode

Makes HTTP requests (GET, POST, PUT, PATCH, DELETE) to any external API. Supports REST and GraphQL. Handles auth injection, body templating, and response parsing.

**Typical use case:** Fetching weather data, sending a Slack message, posting a lead to Salesforce, calling any third-party REST API.

**Execution pipeline:**
```
1. Select connector (built-in) or raw HTTP mode
2. Render URL template (Jinja2 with resolved_inputs)
3. Render body / query params (Jinja2)
4. Inject authentication (OAuth token / API key / Basic / HMAC)
5. Execute httpx async request (with timeout + retry)
6. Parse response (JSON / text / binary)
7. Return NodeOutput { body, status_code, headers }
```

**Config schema:**
```json
{
  "method": { "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"] },
  "url": { "type": "string", "description": "Jinja2 template allowed" },
  "headers": { "type": "object" },
  "query_params": { "type": "object" },
  "body_template": { "type": "string", "description": "JSON Jinja2 template" },
  "auth_type": { "enum": ["none", "api_key", "oauth", "basic", "hmac"] },
  "credential_id": { "type": "string", "description": "Reference to stored OAuth token" },
  "timeout_seconds": { "type": "integer", "default": 30 },
  "retry_on_5xx": { "type": "boolean", "default": true }
}
```

---

### 7.3 TemplatingNode

Transforms and formats data using Jinja2 templates. Combines multiple node outputs into a single string or structured JSON. No code execution — pure declarative transformation.

**Typical use case:** Formatting a final answer block + reasoning block into a professional email body. Building a prompt string from multiple dynamic variables.

**Execution pipeline:**
```
1. Compile Jinja2 template (cached per template hash)
2. Render with resolved_inputs as template context
3. Optionally parse output as JSON
4. Return NodeOutput { result }
```

**Config schema:**
```json
{
  "template": { "type": "string", "description": "Jinja2 template string" },
  "output_format": { "enum": ["text", "json"], "default": "text" }
}
```

**Example template:**
```jinja2
Hello {{ variables.user_name }},

Here is your weekly report:
{{ variables.summary }}

Generated on: {{ variables.date }}
```

---

### 7.4 WebSearchNode

Queries the live web using SerpAPI. Returns structured search results with titles, URLs, and snippets. Unlike SemanticSearchNode (which searches your private data), this searches the public internet.

**Typical use case:** Fetching the latest news on a topic, verifying a current event, gathering live market data.

**Execution pipeline:**
```
1. Check Redis cache (TTL 1h) for identical query
   hit  → return cached results
   miss → continue
2. Call SerpAPI (google / bing engine)
3. Parse and normalize results
4. Cache response
5. Return NodeOutput { results, snippets }
```

**Config schema:**
```json
{
  "engine": { "enum": ["google", "bing"], "default": "google" },
  "num_results": { "type": "integer", "default": 5, "maximum": 10 },
  "region": { "type": "string", "default": "us" },
  "safe_search": { "type": "boolean", "default": true },
  "cache_ttl_seconds": { "type": "integer", "default": 3600 }
}
```

**Ports:**
- Input: `query` (string)
- Output: `results` (array of `{title, url, snippet}`), `snippets` (array of strings — flattened for direct LLM injection)

---

### 7.5 MCPNode _(feature-flagged: `MCP_NODE_ENABLED`)_

Invokes a specific tool on an **MCP (Model Context Protocol) server**. This is a **direct, deterministic tool call** — you configure exactly which tool runs and with what parameters. No LLM is involved.

> **MCP vs AgentNode:** The `AgentNode` lets an LLM decide which tool to call (and loops until done). `MCPNode` is for when you already know which tool you need — deterministic, cheaper, faster.

**Typical use case:** Read a file from an MCP filesystem server. Query an internal database tool. Run a code analysis tool. Call any MCP-compatible service without writing custom API integration code.

**Transport support:** `http_sse` (remote servers over HTTP + Server-Sent Events), `stdio` (local process, dev/ENTERPRISE only), `managed` (platform-hosted MCP servers).

**Platform-managed MCP servers (available on PRO+):**

| Server | Tools available |
|--------|----------------|
| `filesystem` | `read_file`, `write_file`, `list_directory`, `search_files` |
| `memory` | `store`, `retrieve`, `search_memory` |
| `github` | `create_issue`, `search_code`, `get_pull_request` |
| `postgres` | `query`, `execute`, `list_tables`, `describe_table` |
| `browser` | `navigate`, `take_screenshot`, `extract_text` |

**Custom MCP servers:** Users provide a server URL + credential. The node discovers available tools at runtime and presents them in the UI tool picker.

**Execution pipeline:**
```
1. Check feature flag (MCP_NODE_ENABLED) — raise if disabled for tenant
2. Resolve MCP server connection (managed pool or per-request connect)
3. services.mcp.get_client(server_id) → MCPClient
4. (First call only) client.list_tools() → cache tool schemas in Redis (TTL 5m)
5. Validate tool_name exists in discovered tools
6. Render tool parameters (Jinja2 with resolved_inputs)
7. Validate rendered params against tool's input_schema
8. Check MCP response cache (Redis, configurable TTL)
   hit  → return cached result
   miss → continue
9. client.call_tool(tool_name, params) — with timeout enforcement
10. Store response in cache (if cache_ttl_seconds > 0)
11. Return NodeOutput { result, tool_name, server_id, tool_metadata }
```

**Config schema:**
```json
{
  "server_type": {
    "enum": ["managed", "http_sse", "stdio"],
    "default": "managed",
    "description": "managed = platform-hosted server; http_sse = remote URL; stdio = local process (ENTERPRISE only)"
  },
  "server_id": {
    "type": "string",
    "description": "For managed: server slug (e.g. 'filesystem', 'postgres'). For http_sse/stdio: user-defined connection ID."
  },
  "server_url": {
    "type": "string",
    "description": "Required for http_sse. MCP server base URL."
  },
  "server_command": {
    "type": "string",
    "description": "Required for stdio (ENTERPRISE only). Shell command to start MCP server process."
  },
  "credential_id": {
    "type": "string",
    "nullable": true,
    "description": "Stored credential for authenticated MCP servers."
  },
  "tool_name": {
    "type": "string",
    "description": "Exact tool name to invoke. Populated from tool picker in UI."
  },
  "tool_params_template": {
    "type": "object",
    "description": "Key-value map where each value is a Jinja2 template. Rendered against resolved_inputs.",
    "example": {
      "path": "{{ input.file_path }}",
      "query": "{{ input.search_term }}"
    }
  },
  "cache_ttl_seconds": {
    "type": "integer",
    "default": 0,
    "description": "0 = no caching. Useful for idempotent read tools."
  },
  "timeout_seconds": {
    "type": "integer",
    "default": 30,
    "maximum": 120
  }
}
```

**Ports:**
- Input: `tool_input` (object — additional runtime parameters merged with `tool_params_template`)
- Output: `result` (any — raw MCP tool response), `tool_metadata` (object — `{tool_name, server_id, duration_ms, cache_hit}`)

**MCPClientRegistry — how it works inside NodeServices:**
```python
# workflow_engine/integrations/mcp/registry.py

class MCPClientRegistry:
    """Manages MCP server connections per tenant.
    Pooled for managed servers; on-demand for custom http_sse servers."""

    async def get_client(self, server_id: str, config: EngineConfig) -> MCPClient:
        """Returns a connected MCPClient. Managed clients reuse pooled connections."""
        ...

    async def list_tools(self, server_id: str) -> list[MCPToolSchema]:
        """Discovers available tools. Results cached in Redis for 5 minutes."""
        ...

class MCPClient:
    """Thin async wrapper around the mcp SDK Client.
    Supports http_sse and stdio transports."""

    async def list_tools(self) -> list[MCPToolSchema]: ...
    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult: ...
```

**AgentNode + MCP integration:**

The `AgentNode` can use MCP tools as part of its tool set. When `tool_source: "mcp"` is configured, the agent automatically fetches the tool schemas from the MCP server and passes them to the LLM:

```json
{
  "tools": [
    { "source": "mcp", "server_id": "postgres", "tool_names": ["query", "list_tables"] },
    { "source": "mcp", "server_id": "filesystem", "tool_names": ["read_file"] }
  ]
}
```

This means MCP-powered agents require **no additional node wiring** — the tool loop is handled inside `AgentNode` automatically.

---

## 8. Workflow Management & Documentation Nodes

### 8.1 SetStateNode

Stores one or more values in the workflow's **run-scoped state store** (Redis). Values set here are accessible by any downstream node via `{{ state.key_name }}` in templates.

**Typical use case:** Storing a `user_id` at the start of a multi-step flow and reading it 10 nodes later without drawing connector lines across the entire canvas.

**Config schema:**
```json
{
  "assignments": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "key": { "type": "string" },
        "value_template": { "type": "string", "description": "Jinja2 expression" }
      }
    }
  }
}
```

**Ports:**
- Input: `value` (any)
- Output: `state` (object — snapshot of full state after assignment)

---

### 8.2 CustomNode

Allows the **platform SDK team** to define reusable logic primitives that appear as first-class visual nodes for non-technical users. A `CustomNode` implementation is a Python class in the SDK — not user-uploaded code.

**Typical use case:** An engineering team builds a "Company Compliance Check" node once. Product managers and data scientists then drag it onto any canvas without knowing its internals.

**Implementation:** SDK team subclasses `BaseNodeType` and registers with `NodeType.CUSTOM` plus a `custom_slug`. The UI discovers available custom nodes via `GET /v1/nodes/custom`.

**Config schema:** Defined by the custom node author — surfaced in `DynamicConfigForm` automatically.

---

### 8.3 NoteNode

A purely **visual/documentation node**. It does not execute, emit events, or consume quota. It provides context or warnings for humans reading the workflow graph.

**`is_executable = False`** — the execution engine skips this node entirely during a run.

**Config schema:**
```json
{
  "content": { "type": "string", "description": "Markdown supported" },
  "color": { "enum": ["default", "yellow", "red", "green", "blue"], "default": "yellow" }
}
```

**Ports:** none (not connected to execution graph)

---

### 8.4 OutputNode

Explicitly defines what the **final response** of the workflow is when called via API. A workflow can have multiple output nodes for different execution paths (success path, error path, etc.).

**Typical use case:** A workflow that generates a blog post sends the final text to the Output node so the API caller receives it as the response body.

**Config schema:**
```json
{
  "output_key": { "type": "string", "description": "Key in the API response JSON", "example": "summary" },
  "schema": { "type": "object", "description": "JSON Schema describing expected output shape" }
}
```

**Ports:**
- Input: `value` (any — the value to return)
- Output: none (terminal node)

---

## 9. Logic & Orchestration Nodes

### 9.1 ControlFlowNode

The "traffic police" of the workflow. Handles branching, merging, and looping. One node type with multiple sub-modes configured via `flow_type`.

**Sub-modes:**

| flow_type | Behaviour |
|-----------|-----------|
| `BRANCH` | Evaluates a condition expression → routes to `true` or `false` output port |
| `SWITCH` | Multi-way routing based on a value → up to 10 named output ports |
| `LOOP` | Iterates over an array input — spawns parallel sub-executions per item (fan-out) |
| `MERGE` | Waits for all parallel branches to complete, aggregates outputs into array (fan-in) |

**Condition expression syntax (BRANCH / SWITCH):**
```
{{ input.status == "active" and input.score > 0.8 }}
{{ input.language in ["es", "pt"] }}
{{ state.retry_count | int < 3 }}
```

**Config schema:**
```json
{
  "flow_type": { "enum": ["BRANCH", "SWITCH", "LOOP", "MERGE"] },
  "condition": { "type": "string", "description": "Jinja2 boolean expression — BRANCH only" },
  "switch_key": { "type": "string", "description": "Jinja2 expression returning switch value — SWITCH only" },
  "cases": { "type": "array", "items": { "type": "string" }, "description": "Named cases — SWITCH only" },
  "default_branch": { "type": "string", "description": "Fallback port name" },
  "iterate_over": { "type": "string", "description": "JMESPath expression selecting array to loop — LOOP only" },
  "max_iterations": { "type": "integer", "default": 100, "maximum": 1000 }
}
```

**Ports:**
- `BRANCH`: Input `input` → Output `true`, `false`
- `SWITCH`: Input `input` → Output per case name
- `LOOP`: Input `items` → Output `item` (one per iteration), `index`
- `MERGE`: Input `branch_N` (N branches) → Output `results` (array)

---

### 9.2 SubworkflowNode

Nests an entire workflow inside another as a single node. Promotes reusability — build a complex sub-process once and reference it from many parent workflows.

**Typical use case:** Building a "Language Detector + Translator" workflow once, then dropping it into any parent workflow that needs multilingual support.

**Execution pipeline:**
```
1. Resolve target workflow_id + version_no (latest or pinned)
2. Validate input matches sub-workflow's trigger schema
3. Trigger sub-workflow execution (synchronous — blocks parent node)
4. Wait for sub-workflow completion (SUCCESS or FAILED)
5. Map sub-workflow output to this node's output port
```

**Config schema:**
```json
{
  "workflow_id": { "type": "string" },
  "version_no": { "type": "integer", "nullable": true, "description": "Null = always use latest" },
  "input_mapping": { "type": "object", "description": "Maps parent node outputs to sub-workflow input keys" },
  "timeout_seconds": { "type": "integer", "default": 300 }
}
```

**Ports:**
- Input: `input` (object — passed to sub-workflow trigger)
- Output: `output` (object — sub-workflow Output node value)

---

## 10. Trigger Nodes

Every workflow **must** have exactly one trigger node as its root (entry point). Trigger nodes have no input ports.

### 10.1 ManualTriggerNode

Started by a human clicking the **Run** button in the UI or by calling `POST /v1/workflows/{id}/trigger` directly.

**Use case:** One-off runs, testing a workflow during development, on-demand execution by a team member.

**Config schema:**
```json
{
  "input_schema": {
    "type": "object",
    "description": "JSON Schema for the form shown in the UI when clicking Run"
  }
}
```

**Output port:** `payload` (object — the values the user filled in)

---

### 10.2 ScheduledTriggerNode

Runs automatically on a cron schedule with timezone support.

**Use case:** "Run this workflow every Monday at 9:00 AM to generate the weekly report."

**Config schema:**
```json
{
  "cron_expression": { "type": "string", "example": "0 9 * * MON" },
  "timezone": { "type": "string", "default": "UTC", "example": "America/New_York" },
  "trigger_payload": { "type": "object", "description": "Static payload injected at every fire" }
}
```

**Output port:** `payload` (object — `trigger_payload` + `{ fired_at: ISO8601 }`)

---

### 10.3 IntegrationTriggerNode

Triggered by an event in a third-party application. The platform registers a webhook listener with the external service; when the event fires, it starts the workflow.

**Use case:** "Start the workflow when a new row is added to a Google Sheet." "Start when a GitHub PR is opened." "Start when a new Salesforce lead is created."

**Supported integrations:**

| Integration | Events |
|-------------|--------|
| Slack | `message.posted`, `reaction.added`, `app_mention` |
| GitHub | `push`, `pull_request.opened`, `issue.created` |
| Google Sheets | `row.added`, `row.updated` |
| Salesforce | `lead.created`, `opportunity.stage_changed` |
| Webhook (generic) | Any HTTP POST — HMAC-SHA256 verified |

**Config schema:**
```json
{
  "integration": { "type": "string", "example": "github" },
  "event": { "type": "string", "example": "pull_request.opened" },
  "credential_id": { "type": "string", "description": "Stored OAuth token for the integration" },
  "filter": { "type": "object", "description": "Optional payload filter — only fire if conditions match" }
}
```

**Output port:** `payload` (object — normalized event payload from the third-party app)

---

## 11. Port Type Compatibility Matrix

Edges between nodes must connect compatible port types. The `PortCompatibilityChecker` enforces this at save time:

```
Source Port Type    Compatible Target Port Types
────────────────    ────────────────────────────
string              string, any
number              number, string, any
boolean             boolean, string, any
object              object, any
array               array, any
any                 string, number, boolean, object, array, any
```

---

## 12. Node Versioning

Nodes are versioned with the SDK. When a workflow is saved/published, the current SDK version is recorded in `WorkflowVersion`. Executions always use the pinned SDK version — preventing silent behaviour changes from SDK upgrades breaking production workflows.

```
WorkflowVersion {
    version_no:     3,
    sdk_version:    "1.0.0",   ← pinned at publish time
    definition:     { ... },   ← frozen snapshot
    created_at:     datetime,
    created_by:     user_id
}
```
