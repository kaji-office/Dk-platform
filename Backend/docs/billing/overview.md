# Billing — Overview
## Composite Pay-Per-Use Model

---

## 1. Billing Model Summary

The platform uses a 5-component composite billing model. Each component measures a different dimension of resource consumption.

```
Total Cost per Execution =
  Component 1: Base Execution Charge
+ Component 2: Node Execution Charges (sum of all nodes)
+ Component 3: LLM Token Charges (AI nodes only)
+ Component 4: Compute Second Charges (Tier 2/3 nodes only)
+ Component 5: Storage Charges (large outputs only)
```

---

## 2. Component Details

### Component 1 — Base Execution Charge
**$0.005 per workflow execution** (regardless of outcome — SUCCESS or FAILED)

Covers: DAG parsing, state management, orchestration overhead, Celery task dispatch.

---

### Component 2 — Node Execution Charges

| Node Type | Isolation Tier | Cost per Execution |
|---|---|---|
| TriggerNode | Tier 0 | $0.000 (free — starts the workflow) |
| LogicNode | Tier 0 | $0.001 |
| HumanNode | Tier 0 | $0.001 |
| APINode | Tier 1 | $0.002 |
| TransformNode (template) | Tier 1 | $0.002 |
| TransformNode (Python) | Tier 2 | $0.005 |
| AINode | Tier 1 | $0.002 + token charges |
| MCPNode | Tier 2 | $0.005 |

---

### Component 3 — LLM Token Charges

| Model | Input (per 1K tokens) | Output (per 1K tokens) |
|---|---|---|
| gemini-flash | $0.000075 | $0.000300 |
| gemini-pro | $0.001250 | $0.005000 |
| claude-haiku | $0.000250 | $0.001250 |
| claude-sonnet | $0.003000 | $0.015000 |
| claude-opus | $0.015000 | $0.075000 |
| gpt-4o-mini | $0.000150 | $0.000600 |
| gpt-4o | $0.002500 | $0.010000 |
| bedrock-claude-haiku | $0.000250 | $0.001250 |
| bedrock-titan | $0.000200 | $0.000650 |

Platform adds a configurable margin on top (default: 20%).

---

### Component 4 — Compute Second Charges

Only charged for Tier 2 (gVisor) and Tier 3 (Firecracker) node executions.

| Tier | Cost per Second | Minimum Charge | Maximum |
|---|---|---|---|
| Tier 2 (gVisor) | $0.000060/s | 100ms | 30s |
| Tier 3 (Firecracker) | $0.000180/s | 200ms | 120s |

Time is wall-clock execution time from container/VM start to output collection. Rounded up to nearest 100ms.

---

### Component 5 — Storage Charges

Only charged when node output exceeds 64KB (spills to S3).

| Metric | Rate |
|---|---|
| Storage | $0.020 per GB-day |
| Transfer (out) | $0.010 per GB |

---

## 3. Plan Tiers & Quotas

```
FREE
  Monthly executions:   500
  Concurrent runs:      2
  Max nodes/workflow:   10
  Tier 3 access:        No
  Retention:            30 days (fixed)
  PII policy:           SCAN_MASK (fixed)
  Overage:              Executions blocked after quota

STARTER
  Monthly executions:   10,000
  Concurrent runs:      5
  Max nodes/workflow:   25
  Tier 3 access:        No
  Retention:            30 or 90 days (tenant choice)
  Billing:              Pay-per-use above quota

PRO
  Monthly executions:   100,000
  Concurrent runs:      20
  Max nodes/workflow:   50
  Tier 3 access:        No
  Retention:            30 / 90 / 365 days (tenant choice)
  Billing:              Pay-per-use above quota

ENTERPRISE
  Monthly executions:   Unlimited
  Concurrent runs:      Negotiated
  Max nodes/workflow:   Unlimited
  Tier 3 access:        Yes (Firecracker MicroVM)
  Retention:            Custom + legal hold
  Infrastructure:       Dedicated (own MongoDB, Redis, K8s namespace)
  Billing:              Custom contract + platform margin negotiated
```

---

## 4. Usage Tracking

Every node execution writes a `UsageRecord` to PostgreSQL:

```python
# engine/billing/models.py

class UsageRecord(BaseModel):
    id:               str           # UUID
    tenant_id:        str
    user_id:          str           # who triggered the execution
    run_id:           str
    node_id:          str
    node_type:        NodeType
    isolation_tier:   int           # 0 | 1 | 2 | 3
    started_at:       datetime
    ended_at:         datetime
    compute_seconds:  float         # Tier 2/3 only, else 0.0
    input_tokens:     int           # AI nodes only, else 0
    output_tokens:    int           # AI nodes only, else 0
    model:            str | None    # AI nodes only
    output_bytes:     int           # all nodes
    s3_spilled:       bool          # context store routing decision
    status:           NodeStatus    # SUCCESS | FAILED
    cost_usd:         float         # computed at write time by CostCalculator
```

Records are written **synchronously** at node completion (not batched) to ensure quota enforcement is accurate. Aggregated hourly into `tenant_usage_summary` for fast dashboard queries.

---

## 5. Quota Enforcement

Quota is checked **before** execution dispatch — fail fast, never over-execute then deny.

```python
# engine/billing/quota_checker.py

class QuotaChecker:
    async def check(self, tenant: Tenant) -> None:
        """
        Raises QuotaExceededError if tenant has hit any limit.
        Called by API before dispatching to Celery.
        """
        summary = await self.get_usage_summary(tenant.id, period="current_month")

        if summary.execution_count >= tenant.monthly_exec_quota:
            raise QuotaExceededError(
                f"Monthly execution quota reached ({tenant.monthly_exec_quota}). "
                f"Upgrade plan or wait for quota reset.",
                http_status_code=429,
            )

        active_runs = await self.count_active_runs(tenant.id)
        if active_runs >= tenant.max_concurrent_runs:
            raise QuotaExceededError(
                f"Concurrent run limit reached ({tenant.max_concurrent_runs}).",
                http_status_code=429,
            )
```

---

## 6. Billing Calculation Example

```
Workflow: Customer onboarding (sends email + creates CRM record)

Node 1: TriggerNode (webhook)
  Component 2: $0.000

Node 2: TransformNode (Python — extract fields from payload)
  Component 2: $0.005  (Tier 2)
  Component 4: 0.8s × $0.000060 = $0.000048

Node 3: AINode (claude-haiku — generate welcome email)
  Component 2: $0.002
  Component 3: 1,200 input tokens × $0.00025/1K = $0.000300
               300 output tokens  × $0.00125/1K = $0.000375

Node 4: APINode (SendGrid — send email)
  Component 2: $0.002

Node 5: APINode (Salesforce — create contact)
  Component 2: $0.002

Node 6: LogicNode (if success — branch)
  Component 2: $0.001

─────────────────────────────────────────────
Component 1 (base):         $0.005000
Component 2 (nodes):        $0.012000
Component 3 (tokens):       $0.000675
Component 4 (compute):      $0.000048
Component 5 (storage):      $0.000000  (all outputs <64KB)
─────────────────────────────────────────────
Total per execution:         $0.017723
Total for 1,000 exec/day:   ~$17.72/day
Total for 30,000 exec/month: ~$531.69/month
```

---

## 7. Invoice Structure

Monthly invoices broken down per component:

```
INVOICE — January 2025
Tenant: Acme Corp (PRO plan)

Base Executions:       42,381 runs × $0.005          =  $211.91
Node Executions:       Various nodes                  =  $384.22
  └─ AI nodes:         18,940 × $0.002                =   $37.88
  └─ Transform (Py):    8,210 × $0.005                =   $41.05
  └─ API nodes:        31,002 × $0.002                =   $62.00
  └─ Logic nodes:      24,000 × $0.001                =   $24.00
  └─ (others)                                         =   ...
LLM Tokens:            gemini-flash: 48M tokens       =   $21.60
                       claude-haiku: 12M tokens        =   $15.75
Compute Seconds:       2,400 sandbox-seconds          =    $0.14
Storage:               0.8 GB-day                     =    $0.02
─────────────────────────────────────────────────────────────────
Subtotal:                                              =  $617.27
Platform margin (20%):                                 =  $123.45
─────────────────────────────────────────────────────────────────
Total:                                                 =  $740.72
```
