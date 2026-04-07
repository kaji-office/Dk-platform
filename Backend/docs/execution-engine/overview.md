# Execution Engine — Overview
## Tiered Isolation + Run Lifecycle

**Last updated:** 2026-04-07 — aligned with implemented codebase (`workflow-engine v1.0.0`)

---

## 1. Execution Architecture

The execution engine is split into two concerns:
- **Orchestration** — `RunOrchestrator` drives the DAG, manages state, publishes events. Lives in `workflow_engine.execution.orchestrator`.
- **Node Execution** — Each node's `execute()` method runs under a timeout and optional retry. `CodeExecutionNode` uses the RestrictedPython sandbox (Tier 1).

```
workflow-worker (Celery: execute_workflow task)
         │
         ▼
build_orchestrator(sdk, tenant_config) → RunOrchestrator
         │
         ▼
orchestrator.run(
    workflow_def,        # WorkflowDefinition
    run_id,              # str
    tenant_id,           # str
    trigger_input,       # dict
)
         │
         ├─ GraphBuilder.topological_layers(workflow_def)  → list[list[str]]
         ├─ StateMachine.transition_run(RUNNING)
         │
         └─ for layer in topo_layers:
               asyncio.gather(
                   *[_process_node(node_id) for node_id in layer],
                   return_exceptions=True,
               )
               bulk_update_node_states(...)   ← 1 MongoDB $set per layer
```

Parallel nodes in the same topological layer run concurrently via `asyncio.gather()` — **not** Celery group/chord. This runs entirely within a single Celery task / worker process.

---

## 2. Isolation Tiers

### Tier 0 — Direct In-Process Execution

```
Nodes: ManualTriggerNode, ScheduledTriggerNode, IntegrationTriggerNode,
       ControlFlowNode, NoteNode, OutputNode, SetStateNode, TemplatingNode
Overhead: ~0ms
Security: N/A — these nodes run only platform code, never user-supplied logic
```

No sandbox. The node's `execute()` method is called directly on the worker. These nodes contain zero user-provided code.

---

### Tier 1 — RestrictedPython (In-Process Sandbox)

```
Nodes: CodeExecutionNode
Overhead: ~5–15ms
Security: AST-level restriction — blocked imports (os, sys, subprocess, socket, shutil,
          importlib, ctypes), RestrictedPython safe_globals, timeout via asyncio.wait_for
```

**Implementation (CodeExecutionNode):**
```python
# nodes/implementations/code_execution.py

# 1. Static AST scan blocks dangerous imports before execution
_BLOCKED_MODULES = frozenset({"os", "sys", "subprocess", "socket", "shutil", "importlib", "ctypes"})

# 2. Compile with RestrictedPython
byte_code = compile_restricted(code, filename="<CodeExecutionNode>", mode="exec")

# 3. Execute in restricted environment
local_vars = {
    "input": context.input_data,   # node's resolved inputs
    "output": None,                # user sets this
    "_getitem_": lambda obj, key: obj[key],
    "_getiter_": iter,
    "_getattr_": getattr,
}
exec(byte_code, restricted_globals, local_vars)

# 4. Return output
return NodeOutput(outputs={"output": local_vars.get("output")})
```

Timeout is enforced by `TimeoutManager.wrap()` which raises `SandboxTimeoutError` (not `NodeExecutionError`) on expiry.

---

### Tier 2 — gVisor Container *(planned, not yet implemented)*

```
Nodes: Reserved for future TransformNode (Python mode), MCPNode
Overhead: ~80–150ms (mitigated by warm pool)
Security: gVisor intercepts all syscalls — no host kernel access possible
Status: sandbox/__init__.py is a placeholder; CodeExecutionNode uses Tier 1 for all user code today
```

---

### Tier 3 — Firecracker MicroVM *(planned, not yet implemented)*

```
Nodes: Reserved for ENTERPRISE-only high-risk scenarios
Overhead: ~125–200ms
Security: Full VM isolation — separate kernel, separate memory space
Available: ENTERPRISE and DEDICATED plans only
Status: Not implemented in v1.0
```

---

## 3. Execution Lifecycle (End-to-End Flow)

```
Step  Layer      Component                   Action
────  ─────      ─────────                   ──────
 1    UI/CLI     POST /api/v1/workflows/{id}/trigger { input_data }
 2    API        auth middleware              Validate JWT — extract user_id + tenant_id
 3    API        execution_service.trigger() Create ExecutionRun (status=QUEUED) in MongoDB
 4    API        execute_workflow.delay()     Celery task enqueued to Redis
 5    API        →                           Return 202 { run_id, status: "queued" }

 6    Worker     execute_workflow (Celery)    Fetch run + workflow from MongoDB
 7    Worker     get_tenant_config()          Load TenantConfig (pii_policy, plan_tier, quotas)
 8    Worker     build_orchestrator()         Construct RunOrchestrator(repo, services, config)
 9    Worker     orchestrator.run()           Begin DAG traversal

10   Orchestrator GraphBuilder.topological_layers()  Build per-layer node groups
11   Orchestrator StateMachine.transition_run(RUNNING)
12   Orchestrator Redis PubSub publish         { type: "node_state", node_id, status: "RUNNING" }

13   Orchestrator [loop per layer]
14   Orchestrator asyncio.gather(nodes in layer)  Parallel node execution within single worker
15   Orchestrator [per node] ContextManager.resolve_inputs()  Walk edges → build input dict
16   Orchestrator [per node] PIIScanner.scan_dict(inputs, config)  Block/mask/warn per policy
17   Orchestrator [per node] StateMachine.transition_node(RUNNING)
18   Orchestrator [per node] TimeoutManager.wrap(execute(), timeout, node_id)
19   Orchestrator [per node] RetryHandler.execute_with_retry(attempt_fn, RetryConfig)
20   Orchestrator [per node] node_impl.execute(config, context, services)  → NodeOutput
21   Orchestrator [per node] PIIScanner.scan_dict(output)   Scan outputs too
22   Orchestrator [per layer] bulk_update_node_states(states_dict)  1 MongoDB $set per layer

23   Orchestrator [on complete] StateMachine.transition_run(SUCCESS)
24   Orchestrator Redis PubSub publish  { type: "run_complete", status: "SUCCESS" }
25   Worker       Celery task completes
```

**Human-in-the-loop pause (step 20 variant):**
```
node returns metadata.status == "WAITING_HUMAN"
    → StateMachine.transition_run(WAITING_HUMAN)
    → Redis publish { type: "run_waiting_human", node_id }
    → Celery task ends (run is paused)

Resume via: POST /api/v1/executions/human-input { run_id, node_id, response }
    → execute_workflow.delay(..., resume_node=node_id, human_response={...})
    → orchestrator.resume(tenant_id, run_id, node_id, workflow_def, human_response)
    → builds sub-workflow of all descendants and recurses into .run()
```

---

## 4. Per-Node Execution Detail

```python
# orchestrator.py — simplified _process_node()

async def _process_node(node_id: str):
    run_state = await self.repo.get(tenant_id, run_id)
    if run_state.status == RunStatus.CANCELLED:
        return False                      # abort silently

    node_def = workflow_def.nodes[node_id]
    node_impl = NodeTypeRegistry.get(NodeType(node_def.type))()

    if not node_impl.is_executable:       # NoteNode → skip
        return False

    inputs = await ctx_manager.resolve_inputs(tenant_id, node_id, workflow_def, outputs)
    PIIScanner.scan_dict(inputs, self.config)   # raises PIIBlockedError on SCAN_BLOCK

    await StateMachine.transition_node(repo, tenant_id, run_id, node_id, RunStatus.RUNNING)

    timeout = int(node_def.config.get("timeout_seconds", 30))
    retries = int(node_def.config.get("max_retries", 1))

    async def _attempt():
        return await TimeoutManager.wrap(_execute_loop(), timeout, node_id)

    rc = RetryConfig(
        max_attempts=retries,
        non_retryable=(SandboxTimeoutError, PIIBlockedError, NodeExecutionError),
    )
    result = await RetryHandler.execute_with_retry(_attempt, rc)

    # Buffer successful state — flushed as bulk_update at end of layer
    layer_success_buffer[node_id] = NodeExecutionState(status=RunStatus.SUCCESS, ...)
```

---

## 5. Input Resolution (ContextManager)

Edge resolution rules:
- `source_port = "payload"` (named port) → extracts `source_outputs["payload"]`
- `source_port = "default"` → passes the entire source output dict
- `target_port = "mykey"` (named) → `inputs["mykey"] = value`
- `target_port = "default"` → `inputs.update(value)` (spread dict into top-level)

```python
# context_manager.py

for edge in [e for e in definition.edges if e.target_node == node_id]:
    source_data = run_state_outputs.get(edge.source_node, {})
    if edge.source_port and edge.source_port != "default":
        value = source_data.get(edge.source_port)
    else:
        value = source_data                         # pass all outputs

    if edge.target_port and edge.target_port != "default":
        inputs[edge.target_port] = value
    else:
        if isinstance(value, dict):
            inputs.update(value)                    # spread into top-level
        else:
            inputs["default"] = value
```

Large outputs (>64KB) are offloaded to S3 and replaced with `{"__blob": "s3://path"}` inline.

---

## 6. Retry and Timeout

### RetryConfig defaults

```python
RetryConfig(
    max_attempts=1,                 # per node_def.config["max_retries"]
    initial_delay_seconds=1.0,
    multiplier=2.0,
    max_delay_seconds=60.0,
    jitter=True,
    non_retryable=(SandboxTimeoutError, PIIBlockedError, NodeExecutionError),
)
```

`SandboxTimeoutError`, `PIIBlockedError`, and `NodeExecutionError` are **never retried** — they fail the node immediately.

### TimeoutManager

```python
# retry_timeout.py

class TimeoutManager:
    @classmethod
    async def wrap(cls, coro, timeout_seconds, node_id):
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            raise SandboxTimeoutError(          # ← NOT NodeExecutionError
                message=f"Node {node_id} exceeded timeout of {timeout_seconds}s"
            )
```

Default timeout per node: `node_def.config.get("timeout_seconds", 30)`.

---

## 7. State Machine

Valid run status transitions (enforced by `StateMachine`):

```
QUEUED        → RUNNING, CANCELLED
RUNNING       → SUCCESS, FAILED, CANCELLED, WAITING_HUMAN
WAITING_HUMAN → RUNNING, CANCELLED
SUCCESS       → (terminal — no further transitions)
FAILED        → (terminal)
CANCELLED     → (terminal)
```

Invalid transitions raise `StateTransitionError`. Node states use the same `RunStatus` enum (QUEUED/RUNNING/SUCCESS/FAILED/CANCELLED/WAITING_HUMAN). There is no RETRYING, SKIPPED, or SUSPENDED state in the current implementation.

---

## 8. Redis PubSub Events

The orchestrator publishes events to `run:{run_id}:events` for WebSocket fan-out:

```python
# Event types published by orchestrator.py
{ "type": "node_state",        "node_id": "...", "status": "RUNNING",  "ts": "..." }
{ "type": "node_state",        "node_id": "...", "status": "SUCCESS",  "ts": "..." }
{ "type": "node_state",        "node_id": "...", "status": "FAILED",   "ts": "..." }
{ "type": "run_complete",      "status": "SUCCESS",                     "ts": "..." }
{ "type": "run_complete",      "status": "FAILED",                      "ts": "..." }
{ "type": "run_waiting_human", "node_id": "...",                        "ts": "..." }
```

Redis publish errors are silently swallowed — a Redis outage does not fail the execution.

---

## 9. Dead Letter Queue

Failed Celery tasks (after all retries exhausted) call `handle_dlq`:

```python
# workflow-worker/tasks.py

@app.task(name="workflow_worker.tasks.dead_letter_queue")
def handle_dlq(failed_task_name: str, args: list, kwargs: dict):
    sdk = run_async(get_engine())
    audit = sdk.get("audit")
    if audit:
        run_async(audit.write(
            tenant_id=...,
            event_type="task.failed",
            detail={"task": failed_task_name, "args": args, "kwargs": kwargs},
        ))
```

DLQ entries are written to the audit log (MongoDB). There is no separate Redis TTL-based DLQ store in v1.0.

---

## 10. Stale Run Reaper

A Celery beat task (`reap_stale_runs`) runs on schedule and marks any `RUNNING` execution that started more than 15 minutes ago as `FAILED`:

```python
# Runs every N seconds via Celery Beat
threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
stale_runs = await execution_repo.list_stale_running(before=threshold)
for run in stale_runs:
    await StateMachine.transition_run(repo, run.tenant_id, run.run_id, RunStatus.FAILED)
```
