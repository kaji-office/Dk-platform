# Execution Engine — Overview
## Tiered Isolation + Run Lifecycle

---

## 1. Execution Architecture

The execution engine is split into two concerns:
- **Orchestration** — `RunOrchestrator` drives the DAG, manages state, routes nodes. Runs on shared worker infrastructure.
- **Node Execution** — Each node runs in an isolation tier appropriate to its type. Containers and VMs are ephemeral — created per execution, destroyed immediately after.

```
workflow-worker (Celery task)
         │
         ▼
RunOrchestrator.run(run_id, definition, engine_config)
         │
         ├─ DAGParser.parse(definition)  → ExecutionPlan
         ├─ StateMachine.transition_run(RUNNING)
         ├─ EventBus.publish(RunStarted)
         │
         └─ For each ExecutionStep in plan:
               │
               ├─ SEQUENTIAL step:
               │   NodeExecutor.execute(node, inputs, context, services)
               │           │
               │           └─ SandboxManager.route(node_type)
               │                   → Tier 0/1/2/3 execution
               │
               └─ PARALLEL step:
                   Celery group(execute_single_node.s(...) for each node)
                   chord → fan-in node execution on completion
```

---

## 2. Isolation Tiers

### Tier 0 — Direct In-Process Execution

```
Nodes: TriggerNode, LogicNode, HumanNode
Overhead: ~0ms
Security: N/A — these nodes run only platform code, never user logic
```

No sandbox, no container. The node's `execute()` method is called directly on the worker process. These nodes contain zero user-provided code — all logic is written and controlled by the platform team.

---

### Tier 1 — RestrictedPython (In-Process Sandbox)

```
Nodes: AINode (prompt rendering), APINode (template rendering), TransformNode (template mode)
Overhead: ~5–15ms
Security: AST-level restriction — no system access, no imports, no I/O
```

**Implementation:**
```python
# engine/sandbox/restricted.py

from RestrictedPython import compile_restricted, safe_globals, safe_builtins

class RestrictedPythonSandbox:
    BLOCKED_BUILTINS = {"open", "exec", "eval", "__import__", "compile", "globals", "locals"}
    MAX_ITERATIONS = 10_000

    def execute(self, code: str, input_data: dict, timeout_seconds: int = 2) -> dict:
        safe_env = {
            "__builtins__": {k: v for k, v in safe_builtins.items()
                            if k not in self.BLOCKED_BUILTINS},
            "input": input_data,
            "output": {},
            "_getiter_": self._iteration_guard(self.MAX_ITERATIONS),
            "_getattr_": getattr,
        }
        try:
            compiled = compile_restricted(code, filename="<transform>", mode="exec")
            with asyncio.timeout(timeout_seconds):
                exec(compiled, safe_env)
            return safe_env["output"]
        except TimeoutError:
            raise SandboxTimeoutError(f"Code exceeded {timeout_seconds}s timeout")
        except Exception as e:
            raise NodeExecutionError(f"Code execution failed: {e}")
```

---

### Tier 2 — gVisor Container (User-Space Kernel)

```
Nodes: TransformNode (Python mode), MCPNode
Overhead: ~80–150ms (mitigated by warm pool)
Security: gVisor intercepts all syscalls — no host kernel access possible
```

**Container specification:**
```yaml
# Applied to every Tier 2 execution container
runtime: runsc          # gVisor runtime
resources:
  limits:
    memory: "512Mi"
    cpu: "500m"
  requests:
    memory: "128Mi"
    cpu: "100m"
securityContext:
  runAsNonRoot: true
  runAsUser: 65534        # nobody
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
networkPolicy:
  egress:
    - to: []              # all outbound blocked by default
      ports: []           # unless explicitly whitelisted in node config
volumeMounts:
  - name: tmp
    mountPath: /tmp       # only writable location
    sizeLimit: "50Mi"
```

**Execution flow:**
```python
# engine/sandbox/container.py

class GVisorSandbox:
    def __init__(self, warm_pool: ContainerWarmPool):
        self.warm_pool = warm_pool

    async def execute(self, code: str, input_data: dict, limits: SandboxLimits) -> dict:
        container = await self.warm_pool.acquire()
        try:
            await container.inject_input({"code": code, "input": input_data})
            result = await container.run(timeout=limits.timeout_seconds)
            return result["output"]
        except ContainerTimeoutError:
            raise SandboxTimeoutError(f"Execution exceeded {limits.timeout_seconds}s")
        finally:
            await self.warm_pool.release_and_replenish(container)
```

**Warm Pool:**
- Maintains N pre-warmed gVisor containers (configurable, default: 10 per worker pod)
- Container is acquired at execution start, released and immediately replaced after
- Eliminates 150ms startup overhead for high-frequency workflows
- Containers are rotated every 50 executions to prevent state accumulation

---

### Tier 3 — Firecracker MicroVM

```
Nodes: Reserved for future ENTERPRISE-only high-risk scenarios
Overhead: ~125–200ms (mitigated by VM warm pool)
Security: Full VM isolation — separate kernel, separate memory space
Available: ENTERPRISE and DEDICATED plans only
```

**Firecracker configuration:**
```json
{
  "boot-source": {
    "kernel_image_path": "/var/lib/firecracker/kernel/vmlinux",
    "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
  },
  "drives": [
    {
      "drive_id": "rootfs",
      "path_on_host": "/var/lib/firecracker/rootfs/ubuntu-22.04.ext4",
      "is_root_device": true,
      "is_read_only": true
    }
  ],
  "machine-config": {
    "vcpu_count": 1,
    "mem_size_mib": 512,
    "track_dirty_pages": false
  },
  "network-interfaces": [
    {
      "iface_id": "eth0",
      "guest_mac": "AA:FC:00:00:00:01",
      "host_dev_name": "tap0"
    }
  ]
}
```

---

## 3. Execution Lifecycle (Full 24-Step Flow)

```
Step  Component         Action                                     SDK Module
────  ─────────         ──────                                     ──────────
 1    UI/CLI            POST /api/v2/workflows {definition JSON}   —
 2    API               Validate JWT / API key                     engine.auth
 3    API               Resolve tenant → EngineConfig              TenantRegistry
 4    API               engine.validation.validate(definition)     validation
 5    API               engine.versioning.create_version()         versioning
 6    API               MongoDB: upsert workflows collection       —
 7    UI/CLI            POST /api/v2/executions {workflow_id}      —
 8    API               engine.billing.quota_checker.check()       billing
 9    API               Redis INCR semaphore (concurrency check)   —
10    API               engine.versioning.pin_for_execution()      versioning
11    API               engine.privacy.scan_dict(input)            privacy
12    API               MongoDB insert ExecutionRun (QUEUED)       models
13    API               Celery: orchestrate_run.delay(run_id)      —
14    Worker            engine.dag.DAGParser().parse(definition)   dag
15    Worker            engine.state.transition_run(RUNNING)       state
16    Worker            engine.events.EventBus.publish(RunStarted) events → Redis → WS → UI
17    Worker (loop)     engine.context.resolve_inputs(node_id)     context
18    Worker (loop)     SandboxManager.route(node_type) → tier     sandbox
19    Worker (AI)       engine.cache.check_semantic(prompt)        cache
20    Worker (AI)       engine.providers.rate_limiter.acquire()    providers
21    Worker (AI)       engine.providers.router.generate()         providers → LLM API
22    Worker (tool)     engine.integrations.tool_executor.execute() integrations
23    Worker            engine.context.store_output(node_id, out)  context → Redis/S3
24    Worker            engine.state.transition_run(SUCCESS/FAILED) state + events → UI
25    Worker            engine.billing.usage_tracker.record()      billing
26    Worker            cleanup_run.delay() → release semaphore    —
```

---

## 4. Parallel Execution

When the `DAGParser` detects parallel branches (nodes with no dependency on each other), the `RunOrchestrator` dispatches them as a Celery group/chord:

```python
# engine/executor/orchestrator.py

async def _execute_parallel_step(
    self,
    step: ExecutionStep,
    run_id: str,
    definition: WorkflowDefinition,
) -> None:
    # Dispatch all parallel nodes as a Celery group
    parallel_group = group(
        execute_single_node.s(
            run_id=run_id,
            node_id=node_id,
            definition_dict=definition.model_dump(),
            trace_ctx=get_current_trace_context(),
        )
        for node_id in step.node_ids
    )

    # chord: run fan-in node after all parallel nodes complete
    if step.fan_in_node_id:
        chord(parallel_group)(
            execute_single_node.s(
                run_id=run_id,
                node_id=step.fan_in_node_id,
                definition_dict=definition.model_dump(),
                trace_ctx=get_current_trace_context(),
            )
        )
    else:
        parallel_group.apply_async()
```

---

## 5. Retry and Timeout

### Retry Policy
```python
# engine/executor/retry.py

@dataclass
class RetryConfig:
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    multiplier: float = 2.0
    max_delay_seconds: float = 60.0
    jitter: bool = True

class RetryHandler:
    def compute_backoff(self, attempt: int, config: RetryConfig) -> float:
        delay = min(
            config.initial_delay_seconds * (config.multiplier ** (attempt - 1)),
            config.max_delay_seconds,
        )
        if config.jitter:
            delay *= random.uniform(0.8, 1.2)
        return delay
```

### Timeout Management
```python
# engine/executor/timeout.py

class TimeoutManager:
    async def wrap(
        self,
        coro: Coroutine,
        timeout_seconds: float,
        node_id: str,
    ) -> Any:
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            raise NodeExecutionError(
                f"Node {node_id} exceeded timeout of {timeout_seconds}s",
                node_id=node_id,
            )
```

**Default timeouts by node type:**
| Node Type | Default Timeout | Maximum |
|---|---|---|
| TriggerNode | 5s | 10s |
| LogicNode | 10s | 30s |
| AINode | 60s | 300s |
| APINode | 30s | 120s |
| TransformNode (Tier 1) | 5s | 30s |
| TransformNode (Tier 2) | 30s | 120s |
| MCPNode | 30s | 120s |
| HumanNode | 86400s (24h) | 604800s (7 days) |

---

## 6. State Machine

```
Run States:
  QUEUED → RUNNING → SUCCESS
                   → FAILED
                   → CANCELLED
         → WAITING_HUMAN (HumanNode paused)

Node States:
  PENDING → RUNNING → SUCCESS
                    → FAILED
                    → RETRYING → RUNNING (retry loop)
           → SKIPPED (conditional branch not taken)
           → SUSPENDED (HumanNode waiting)
```

All state transitions are enforced by `StateMachine.transition_run()` and `transition_node()`. Invalid transitions raise `StateTransitionError`. Transitions are written to MongoDB with optimistic locking (version field).

---

## 7. Dead Letter Queue

Tasks that fail after all retry attempts are written to the DLQ:

```
Redis key: dlq:{task_id}
Value: {
    task_name:   "orchestrate_run",
    task_kwargs: { run_id, definition_dict },
    error:       "NodeExecutionError: ...",
    traceback:   "...",
    failed_at:   "2024-01-15T10:30:00Z",
    attempt:     3
}
TTL: 7 days
```

Admin UI shows DLQ entries with manual re-trigger capability.
