# Tenancy Model
## Hybrid Shared + Dedicated Infrastructure

---

## 1. Overview

The platform supports two infrastructure models that coexist within the same codebase:

- **SHARED** — Multiple tenants on the same database, Redis, and K8s namespace. Used by FREE, STARTER, and PRO plan tenants.
- **DEDICATED** — Each tenant has their own isolated MongoDB cluster, Redis instance, and K8s namespace. Used by ENTERPRISE and DEDICATED plan tenants.

The routing decision is made once at request time by the `TenantRouter` and propagated into `EngineConfig` for that request's entire lifecycle.

---

## 2. Tenant Registry

Every request begins with a tenant lookup. The `TenantRegistry` is a PostgreSQL-backed service with a Redis cache layer:

```
Incoming Request
      │
      ▼
TenantContextMiddleware
      │
      ├─ Extract tenant_id from JWT or API key
      │
      ▼
TenantRegistry.resolve(tenant_id)
      │
      ├─ L1 Cache: Redis TTL 5min → tenant config dict
      │   hit  → return immediately
      │   miss ↓
      │
      └─ L2 Store: PostgreSQL tenants table
          → returns TenantConfig {
               tenant_id,
               plan_tier,
               isolation_model,    ← SHARED | DEDICATED
               mongodb_url,        ← shared cluster URL or dedicated URL
               redis_url,          ← shared cluster or dedicated
               s3_bucket,          ← shared bucket (tenant prefix) or dedicated
               home_region,        ← us-east-1 | eu-west-1 | ap-southeast-1
               pii_policy,         ← DISABLED | SCAN_WARN | SCAN_MASK | SCAN_BLOCK (default: SCAN_WARN)
               retention_days,     ← 30 | 90 | 365 | custom
               max_concurrent_runs,
               monthly_exec_quota
            }
```

---

## 3. Shared Tenancy (FREE / STARTER / PRO)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SHARED INFRASTRUCTURE                                                   │
│                                                                         │
│  MongoDB Atlas (shared cluster)                                         │
│  ├── Database: workflow_platform                                        │
│  └── All collections include tenant_id field + compound index           │
│      e.g., { tenant_id: "t1", workflow_id: "w1", ... }                 │
│                                                                         │
│  ElastiCache Redis (shared cluster)                                     │
│  └── All keys namespaced by tenant_id:                                  │
│      ctx:{tenant_id}:{run_id}:{node_id}                                 │
│      rate:{tenant_id}:{model}                                           │
│      semaphore:{tenant_id}                                              │
│                                                                         │
│  S3 (shared bucket)                                                     │
│  └── All objects under prefix: s3://workflow-platform/{tenant_id}/     │
│                                                                         │
│  EKS (shared namespace)                                                 │
│  └── Namespace: shared                                                  │
│      Workers: shared Celery pool (tenant_id in task context)            │
│      Execution isolation: gVisor containers (per execution, not tenant) │
└─────────────────────────────────────────────────────────────────────────┘
```

**Data isolation on shared infrastructure is enforced by:**
1. Every MongoDB query includes `{ "tenant_id": current_tenant_id }` filter
2. `TenantScopedCollection` wrapper class — raises `ForbiddenError` if query lacks tenant filter
3. Redis key namespace prefix enforced by `RedisContextStore`
4. S3 object prefix enforced by `S3ContextStore`
5. Celery task context always carries `tenant_id` — workers reject tasks with mismatched tenant

---

## 4. Dedicated Tenancy (ENTERPRISE / DEDICATED)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DEDICATED INFRASTRUCTURE (per ENTERPRISE tenant)                        │
│                                                                         │
│  MongoDB Atlas (dedicated cluster)                                      │
│  └── Provisioned via MongoDB Atlas Admin API on tenant onboarding       │
│      Connection string stored in AWS Secrets Manager                    │
│      Automated backups: daily, 30-day retention                         │
│                                                                         │
│  ElastiCache Redis (dedicated instance)                                 │
│  └── Provisioned via AWS CDK / Terraform on tenant onboarding           │
│      No key namespace prefix required (entire instance is tenant-owned) │
│                                                                         │
│  S3 (dedicated bucket)                                                  │
│  └── Bucket: workflow-{tenant_slug}-{region}                           │
│      Bucket policy: accessible only by tenant's EKS service account    │
│                                                                         │
│  EKS (dedicated namespace)                                              │
│  └── Namespace: tenant-{tenant_id}                                     │
│      Dedicated Celery workers (min replicas configured by contract)     │
│      Network policy: namespace-level egress isolation                   │
│      Execution isolation: Firecracker MicroVMs (Tier 3 available)       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Tenant Onboarding Flow

### Shared Tenant (FREE → PRO)
```
User signs up
      │
      ▼
POST /auth/signup
      │
      ▼
Create user record (PostgreSQL)
Create tenant record (PostgreSQL) { isolation_model: SHARED }
Write TenantConfig to TenantRegistry
      │
      ▼
Ready immediately — uses shared infrastructure
```

### Dedicated Tenant (ENTERPRISE)
```
Sales team activates ENTERPRISE contract
      │
      ▼
Admin triggers: POST /admin/tenants/{id}/provision-dedicated
      │
      ▼
InfrastructureProvisioner.provision(tenant_id)
  ├── Create MongoDB Atlas dedicated cluster (Atlas Admin API)
  ├── Create ElastiCache Redis instance (AWS SDK)
  ├── Create S3 dedicated bucket (AWS SDK)
  ├── Create EKS namespace + NetworkPolicy (K8s API)
  ├── Store connection strings in AWS Secrets Manager
  └── Update TenantConfig { isolation_model: DEDICATED, mongodb_url: ... }
      │
      ▼ (~5–10 min provisioning)
      │
      ▼
Migrate existing data from shared → dedicated (if upgrading from PRO)
      │
      ▼
Update TenantRegistry cache
      │
      ▼
Notify tenant: dedicated infrastructure ready
```

---

## 6. EngineConfig Injection

The SDK itself has no knowledge of tenancy. `EngineConfig` uses nested sub-configs and is initialised **once at process startup** from environment variables. Per-execution tenant context is resolved separately as `TenantConfig`.

### EngineConfig structure (config.py)

```python
class EngineConfig(BaseSettings):
    storage:   StorageConfig        # mongodb_url, postgres_url, redis_url, s3_bucket, aws_region
    tenant:    TenantContextConfig  # tenant_id, pii_policy (per-request context only)
    providers: LLMProvidersConfig   # google_api_key, anthropic_api_key, openai_api_key, bedrock_region
    sandbox:   SandboxConfig        # sandbox_timeout_seconds, sandbox_max_memory_mb, …
    context_inline_threshold_kb: int = 64
    # …other platform-level settings
```

### Startup (API / Worker)

```python
# Both workflow-api and workflow-worker initialise sub-configs from env vars at startup
storage_config = StorageConfig()      # reads MONGODB_URL, POSTGRES_URL, REDIS_URL, S3_BUCKET
llm_config     = LLMProvidersConfig() # reads GOOGLE_API_KEY, ANTHROPIC_API_KEY, …
repos          = await RepositoryFactory.create_all(storage_config)
```

### Per-execution tenant resolution (Worker)

```python
# workflow-worker/dependencies.py
async def get_tenant_config(sdk: dict, tenant_id: str) -> TenantConfig:
    """
    Fetches TenantConfig from PostgreSQL (cached in Redis for 5 min).
    Returns FREE-tier defaults if tenant not found.
    """
    # Redis cache key: tenant_config:{tenant_id}
    # Falls back to DB → TenantConfig(tenant_id, plan_tier, isolation_model, pii_policy, quotas)

orchestrator = build_orchestrator(sdk, tenant_config)
# RunOrchestrator receives TenantConfig directly — no EngineConfig per-execution
```

### TenantConfig fields

```python
class TenantConfig(BaseModel):
    tenant_id:       str           # required
    plan_tier:       PlanTier      # FREE | STARTER | PRO | ENTERPRISE
    isolation_model: IsolationModel # SHARED | DEDICATED
    pii_policy:      PIIPolicy     # DISABLED | SCAN_WARN | SCAN_MASK | SCAN_BLOCK (default: SCAN_WARN)
    quotas:          dict[str, int] # plan-tier execution limits
```

---

## 7. Execution-Level Isolation (All Tenants)

Regardless of tenancy type, **every workflow execution runs in an isolated environment**. This is the internal execution isolation that exists within both shared and dedicated infrastructure.

```
SHARED TENANT execution:
  Worker picks up Celery task
        │
        ▼
  RunOrchestrator.run()
        │
        ├─ TriggerNode / LogicNode → Tier 0 (direct, in-process)
        ├─ AINode / APINode        → Tier 1 (RestrictedPython)
        ├─ TransformNode (Python)  → Tier 2 (gVisor container)
        │   └── Dedicated ephemeral container, destroyed after execution
        │       cgroup limits: 512MB RAM, 0.5 vCPU, 30s timeout
        │       Network: blocked except whitelisted endpoints
        └─ MCPNode                 → Tier 2 (gVisor container)

DEDICATED TENANT execution:
  Same as above, but:
        ├─ Workers run in dedicated K8s namespace
        ├─ TransformNode (Python)  → Tier 2 OR Tier 3 (Firecracker MicroVM)
        └─ All containers/VMs run within dedicated namespace network policy
```
