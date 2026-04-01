# Architecture Decision Records (ADR)
## AI Workflow Builder Platform

All key architectural decisions made during requirement gathering, with rationale and implications.

---

## ADR-001: Hybrid Tenancy Model (Shared + Dedicated)

**Status:** Accepted
**Date:** 2026-03-30

**Decision:** Support both shared multi-tenant (Option B) and dedicated per-tenant (Option C) infrastructure. Infrastructure isolation is determined by the tenant's plan tier.

**Tenancy Assignment:**
| Plan Tier | Infrastructure | Database | Redis | K8s Namespace |
|---|---|---|---|---|
| FREE | Shared | Shared MongoDB Atlas | Shared ElastiCache | `shared` namespace |
| STARTER | Shared | Shared MongoDB Atlas | Shared ElastiCache | `shared` namespace |
| PRO | Shared | Shared MongoDB Atlas | Shared ElastiCache | `shared` namespace |
| ENTERPRISE | Dedicated | Dedicated MongoDB Atlas cluster | Dedicated ElastiCache | `tenant-{id}` namespace |
| DEDICATED | Dedicated | Dedicated MongoDB Atlas cluster | Dedicated ElastiCache | `tenant-{id}` namespace |

**Routing Layer:** A `TenantRegistry` service resolves the correct infrastructure stack for every request before any database operation.

**Consequences:**
- Requires a `TenantRouter` middleware in the API that resolves DB connection per request
- SDK must never hardcode a connection string — always injected via `EngineConfig`
- Infrastructure provisioning automation needed for ENTERPRISE onboarding
- Migration path required: shared → dedicated without workflow/execution data loss

---

## ADR-002: 4-Tier Execution Isolation

**Status:** Accepted
**Date:** 2026-03-30

**Decision:** Implement a 4-tier isolation model. Node type determines isolation tier automatically. Users cannot override isolation tier.

| Tier | Runtime | Used By | Overhead |
|---|---|---|---|
| 0 | Direct Python (in-process) | TriggerNode, LogicNode, HumanNode | ~0ms |
| 1 | RestrictedPython (in-process AST sandbox) | AINode, APINode, TransformNode (simple) | ~5–15ms |
| 2 | gVisor Container (user-space kernel) | TransformNode (Python), MCPNode | ~80–150ms |
| 3 | Firecracker MicroVM | Reserved for future high-risk nodes | ~125–200ms |

**Consequences:**
- Tier 2 requires warm container pool to mitigate startup latency
- Tier 3 restricted to ENTERPRISE plan only
- Billing tracks isolation tier per node execution

---

## ADR-003: Composite 5-Component Billing

**Status:** Accepted
**Date:** 2026-03-30

**Decision:** Billing uses 5 components: base execution + node type charge + LLM tokens + compute seconds + storage.

**Rationale:** Single-unit billing (per execution or per token) fails to fairly represent actual resource cost. A 20-node workflow with Python sandboxes and LLM calls costs significantly more than a 2-node webhook trigger.

**Consequences:**
- `engine.billing` module must record `UsageRecord` per node execution
- QuotaChecker runs BEFORE execution dispatch — fail fast, don't over-charge
- Invoice line items are aggregated from `UsageRecord` → `UsageSummary` (hourly)
- FREE plan enforces hard monthly limits; PRO enforces soft limits with overage billing

---

## ADR-004: Platform Team Owns All Node Types

**Status:** Accepted
**Date:** 2026-03-30

**Decision:** Users never create, upload, or deploy node types. All nodes are authored by the platform development team as part of the `workflow-engine` SDK. Users configure nodes through the UI.

**Rationale:** Node authorship is a security boundary. Allowing user-defined node types would require a full marketplace, package validation, and execution trust model that is out of scope for v1.0–v2.0.

**User logic entry point:** `TransformNode` with Python sandbox (Tier 2) is the designated place for user-provided code. All other nodes use configuration, not code authorship.

**Consequences:**
- No custom node upload UI, marketplace, or deployment pipeline
- Node versioning tied to SDK release cycle
- New node types require SDK release + deployment

---

## ADR-005: Progressive Complexity UI Model

**Status:** Accepted
**Date:** 2026-03-30

**Decision:** Every node config panel supports two modes — Form Mode (default) and Code Mode (JSON). Users can switch between modes at any time. The platform also provides AI-assisted code generation within the config panel.

**Consequences:**
- Monaco Editor is a first-class component, not an advanced feature
- Node config schemas must drive both form generation and JSON validation
- AI assist uses a platform-internal LLM call billed at standard token rates to the tenant

---

## ADR-006: AWS as Primary Cloud Provider

**Status:** Accepted
**Date:** 2026-03-30

**Decision:** AWS is the sole cloud provider for v1.0–v2.0.

**Service Mapping:**
| Purpose | AWS Service |
|---|---|
| Container orchestration | EKS |
| PostgreSQL | RDS PostgreSQL 16 (Multi-AZ) |
| MongoDB | MongoDB Atlas on AWS |
| Cache / Queue | ElastiCache Redis 7 |
| Object Storage | S3 |
| Container Registry | ECR |
| DNS | Route53 |
| TLS | ACM |
| Secrets | AWS Secrets Manager |
| Observability | CloudWatch + X-Ray |
| Additional LLM | Amazon Bedrock |

**Consequences:**
- All prior docs referencing GCS must be updated to S3
- Vertex AI references replaced with Bedrock as additional provider
- IAM roles used for service-to-service auth (no static credentials between AWS services)

---

## ADR-007: Authentication Strategy A3 + B4

**Status:** Accepted
**Date:** 2026-03-30

**Decision:** Email/password + Social OAuth (Google, GitHub, Microsoft) + SAML/OIDC SSO for enterprise. Simple flat team structure (Owner + Editor + Viewer).

**JWT Claims:**
```json
{
  "sub": "user_id",
  "tenant_id": "tenant_uuid",
  "email": "user@example.com",
  "role": "editor",
  "plan": "PRO",
  "isolation_tier": "SHARED",
  "exp": 1735000000,
  "iat": 1734990000,
  "jti": "unique_token_id"
}
```

**RBAC Matrix:**
| Action | Owner | Editor | Viewer |
|---|---|---|---|
| Create/edit/delete workflow | ✓ | ✓ | ✗ |
| Trigger execution | ✓ | ✓ | ✗ |
| View executions + logs | ✓ | ✓ | ✓ |
| View workflows | ✓ | ✓ | ✓ |
| Manage team members | ✓ | ✗ | ✗ |
| Manage billing + plan | ✓ | ✗ | ✗ |
| Configure SSO | ✓ | ✗ | ✗ |
| Manage API keys | ✓ | ✓ (own keys) | ✗ |
| Configure integrations | ✓ | ✓ | ✗ |

**SSO:** Available on ENTERPRISE and DEDICATED plans only.

---

## ADR-008: GDPR + SOC 2 Type II Compliance (v1.0)

**Status:** Accepted
**Date:** 2026-03-30

**Decision:** v1.0 ships GDPR-compliant and SOC 2 Type II-ready. HIPAA added in v2.0.

**GDPR Requirements in v1.0:**
- Data residency: tenants choose region at signup, data never leaves chosen region
- Right to erasure: `GDPRHandler.delete_user_data()` cascades across all stores
- Data Processing Agreements: generated and stored per tenant
- Audit trail: append-only, immutable, tamper-evident

**SOC 2 Requirements in v1.0:**
- Encryption at rest (AES-256 via AWS KMS) and in transit (TLS 1.3)
- Access logs for all API calls (CloudWatch)
- MFA enforcement for ENTERPRISE tenants
- Incident response runbook documented
- Quarterly access review process

---

## ADR-009: Tenant-Configurable PII Policy

**Status:** Accepted
**Date:** 2026-03-30

**Decision:** PII handling is configurable per tenant. Default policy is `SCAN_MASK`.

| Policy | Behaviour |
|---|---|
| `SCAN_WARN` | Detect PII → log warning → allow execution to proceed |
| `SCAN_MASK` | Detect PII → redact before storing in execution logs → proceed |
| `SCAN_BLOCK` | Detect PII in sensitive node types → halt execution → return error |

**Default:** `SCAN_MASK` for all new tenants.
**ENTERPRISE:** Can configure policy per workflow, not just per tenant.

---

## ADR-010: Region Expansion Strategy

**Status:** Accepted
**Date:** 2026-03-30

**Phases:**
| Version | Region | Purpose |
|---|---|---|
| v1.0 | `us-east-1` | Launch region — all tenants |
| v1.2 | `eu-west-1` | GDPR data residency for EU tenants |
| v2.0 | `ap-southeast-1` | APAC coverage |

**Data residency enforcement:** Tenant's `home_region` field in PostgreSQL determines which regional deployment handles their requests. Route53 geo-routing + API-level enforcement ensures data never leaves the chosen region.
