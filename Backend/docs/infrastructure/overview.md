# Infrastructure — Overview
## AWS Architecture · EKS · Databases · Storage · Regions

---

> **Local Development:** All infrastructure (MongoDB, PostgreSQL, Redis) runs as **native Ubuntu services** on the developer machine — no Docker required. LocalStack provides S3. See `docs/quickstart.md` Path C for setup. The AWS/EKS architecture below is the production deployment target.

---

## 1. AWS Service Map

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL TRAFFIC                                                             │
│  Browser / CLI / Webhooks                                                    │
└──────────────────────────┬───────────────────────────────────────────────────┘
                           │ HTTPS
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Route53 (DNS)  →  ACM (TLS)  →  ALB (Application Load Balancer)            │
│                                   ├── /api/*     → workflow-api EKS pods    │
│                                   ├── /ws/*      → workflow-api EKS pods    │
│                                   └── /*         → workflow-ui (CloudFront) │
└──────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  EKS CLUSTER (VPC — private subnets)                                         │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  workflow-api   │  │ workflow-worker  │  │  workflow-scheduler (x1)    │  │
│  │  (2–10 pods)    │  │  (2–20 pods)    │  │  Celery Beat, single replica│  │
│  │  HPA: CPU>70%   │  │  HPA: queue>50  │  └─────────────────────────────┘  │
│  └────────┬────────┘  └────────┬────────┘                                   │
│           │                    │                                             │
│  ┌────────▼────────────────────▼──────────────────────────────────────────┐  │
│  │  Sandbox Execution (ephemeral pods per execution)                      │  │
│  │  Tier 2: gVisor containers (runsc runtime class)                       │  │
│  │  Tier 3: Firecracker MicroVM pods (ENTERPRISE only)                    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  DATA LAYER (all in private subnets — no public access)                      │
│                                                                              │
│  ElastiCache Redis 7         MongoDB Atlas (AWS-peered)                      │
│  (cluster mode, 3 shards)    (shared cluster + dedicated per enterprise)     │
│                                                                              │
│  RDS PostgreSQL 16           S3                                              │
│  (Multi-AZ, encrypted)       (workflow-platform-{region} + per-tenant)      │
└──────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  OBSERVABILITY                                                                │
│  CloudWatch Logs  CloudWatch Metrics  CloudWatch Alarms  X-Ray Traces        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. EKS Cluster Design

### Node Groups

```yaml
# Cluster: workflow-platform-{region}

nodeGroups:
  - name: api-workers
    instanceType: t3.medium       # 2 vCPU, 4GB RAM
    minSize: 2
    maxSize: 10
    labels:
      workload: api
    taints: []

  - name: celery-workers
    instanceType: c5.xlarge       # 4 vCPU, 8GB RAM (compute-optimized for LLM tasks)
    minSize: 2
    maxSize: 20
    labels:
      workload: worker
    taints:
      - key: workload
        value: worker
        effect: NoSchedule

  - name: sandbox-workers
    instanceType: c5.2xlarge      # 8 vCPU, 16GB RAM (gVisor overhead + parallel sandboxes)
    minSize: 1
    maxSize: 10
    labels:
      workload: sandbox
    taints:
      - key: workload
        value: sandbox
        effect: NoSchedule
    runtimeClass: gvisor           # gVisor runtime installed on this node group

  - name: scheduler
    instanceType: t3.small
    minSize: 1
    maxSize: 1                     # Exactly one scheduler
    labels:
      workload: scheduler
```

### Namespaces
```
default          → platform admin tools
workflow-api     → API pods
workflow-worker  → Worker pods
workflow-sandbox → Ephemeral sandbox execution pods
monitoring       → CloudWatch agent, X-Ray daemon
shared           → Shared tenant workloads
tenant-{id}      → Dedicated tenant namespaces (ENTERPRISE)
```

### Network Policies
```yaml
# Sandbox namespace: strict egress isolation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sandbox-egress-block
  namespace: workflow-sandbox
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress: []    # Default deny all outbound
                # Individual pods get egress rules only if node config whitelists endpoints
```

---

## 3. Database Architecture

### PostgreSQL (RDS)
```
Instance:     db.r6g.large (2 vCPU, 16GB RAM)
Version:      PostgreSQL 16
Mode:         Multi-AZ (primary + standby in different AZs)
Storage:      gp3, 100GB initial, auto-scaling to 1TB
Encryption:   AWS KMS (AES-256)
Backups:      Daily automated, 35-day retention, point-in-time recovery
Extensions:   pgvector (semantic cache), pg_partman (partition management)

Schema ownership:
  users              — id, email, password_hash, tenant_id, role, mfa settings
  tenants            — id, name, slug, plan_tier, isolation_model, home_region
  api_keys           — id, key_hash, user_id, tenant_id, scopes, expires_at
  subscriptions      — id, tenant_id, plan_tier, billing_email, quota config
  oauth_tokens       — id, user_id, provider, encrypted tokens, expires_at
  llm_cost_records   — id, tenant_id, run_id, node_id, model, tokens, cost_usd
  node_exec_records  — id, tenant_id, run_id, node_id, tier, compute_seconds
  semantic_cache     — id, tenant_id, model, prompt_hash, embedding (vector), response
  tenant_usage_summary — tenant_id, date, execution_count, token_count, cost_usd
```

### MongoDB Atlas
```
Shared Cluster:
  M30 tier (dedicated cluster, shared across FREE/STARTER/PRO tenants)
  Region: same AWS region as EKS cluster
  VPC Peering: Atlas VPC ↔ Platform VPC

Dedicated Cluster (per ENTERPRISE tenant):
  M10 minimum, configurable
  Provisioned via Atlas Admin API on tenant onboarding

Collections (all shared — tenant_id field + compound indexes):
  workflows          {tenant_id, workflow_id, name, definition, metadata}
  workflow_versions  {tenant_id, workflow_id, version_no, sdk_version, snapshot}
  execution_runs     {tenant_id, run_id, workflow_id, status, node_states, started_at}
  node_executions    {run_id, node_id, status, input_hash, output_ref, logs, timing}
  audit_log          {tenant_id, event_type, user_id, resource_id, payload, created_at}
  schedules          {tenant_id, workflow_id, cron_expr, timezone, next_fire_at}

Critical Indexes:
  workflows:         { tenant_id: 1, workflow_id: 1 } unique
  execution_runs:    { tenant_id: 1, status: 1, started_at: -1 }
  node_executions:   { run_id: 1, node_id: 1 } unique
  audit_log:         { tenant_id: 1, created_at: -1 }
  schedules:         { next_fire_at: 1, is_active: 1 }
```

### ElastiCache Redis
```
Configuration:  Cluster mode enabled, 3 shards, 1 replica per shard
Instance:       cache.r6g.large per shard (2 vCPU, 13GB RAM)
Version:        Redis 7
Encryption:     In-transit (TLS) + at-rest (AWS KMS)
Auth:           AUTH token required

Key Namespace:
  ctx:{tenant_id}:{run_id}:{node_id}   Node outputs ≤64KB (TTL: 24h)
  ws:run:{run_id}                      Pub/sub channel for WS fan-out
  rate:{tenant_id}:{model}             RPM counter (TTL: 60s window)
  semaphore:{tenant_id}                Concurrent run counter
  session:{session_id}                 User session (TTL: 7 days)
  human:{run_id}:{node_id}             HumanNode correlation ID (TTL: 7 days)
  dlq:{task_id}                        Dead letter queue entries (TTL: 7 days)
  tenant:{tenant_id}                   TenantConfig cache (TTL: 5 min)
  cache:mcp:{tool_id}:{params_hash}    MCP response cache (TTL: configurable)
```

### S3 Storage
```
Bucket (shared): workflow-platform-{region}
  Prefix per tenant: {tenant_id}/
  Objects:
    {tenant_id}/ctx/{run_id}/{node_id}   Node outputs >64KB
    {tenant_id}/exports/{workflow_id}    Workflow bundle exports (ZIP)
    {tenant_id}/uploads/{file_id}        User file uploads

Bucket (dedicated): workflow-{tenant_slug}-{region}
  Used by ENTERPRISE tenants
  Bucket policy: accessible only by tenant's K8s service account (IRSA)

Lifecycle policies:
  ctx/ objects:     expire after retention_days (per tenant config)
  exports/:         expire after 30 days
  uploads/:         expire after 90 days (or sooner per GDPR request)
```

---

## 4. Secrets Management

All secrets stored in AWS Secrets Manager. Never in environment variables, Kubernetes ConfigMaps, or code.

```
Secret path convention:
  /workflow-platform/{env}/{component}/{secret_name}

Examples:
  /workflow-platform/prod/api/jwt_private_key
  /workflow-platform/prod/api/jwt_public_key
  /workflow-platform/prod/database/postgres_url
  /workflow-platform/prod/database/mongodb_url_shared
  /workflow-platform/prod/redis/auth_token
  /workflow-platform/prod/providers/anthropic_api_key
  /workflow-platform/prod/providers/openai_api_key
  /workflow-platform/prod/notifications/sendgrid_api_key
  /workflow-platform/prod/tenant/{tenant_id}/mongodb_url    ← ENTERPRISE tenants

Access:
  EKS pods use IRSA (IAM Roles for Service Accounts) to access Secrets Manager
  No static AWS credentials in pods
  Secret rotation: automatic for database passwords (AWS managed)
```

---

## 5. Region Strategy

### v1.0 — us-east-1 (Launch)
Single region. All tenants assigned `home_region: us-east-1`. Simple operations.

### v1.2 — eu-west-1 (GDPR)
Second region added. EU tenants can choose `home_region: eu-west-1` at signup. Data never leaves eu-west-1 for EU tenants.

```
Route53 Geo-Routing:
  EU IP addresses → eu-west-1 ALB
  Other → us-east-1 ALB

API enforcement:
  TenantContextMiddleware reads tenant.home_region
  If request.region != tenant.home_region → 307 redirect to correct region
```

### v2.0 — ap-southeast-1 (APAC)
Third region. APAC tenants assigned Singapore region.

### Cross-Region: Platform Services
```
PostgreSQL:   Each region has its own RDS instance (no cross-region replication for user data)
MongoDB Atlas:Each region has its own cluster(s)
Redis:        Per-region ElastiCache (no cross-region)
S3:           Tenant data in home_region bucket only
              Replicated only for backup purposes (not tenant-accessible from other region)
```
