# Security — Overview
## Authentication · RBAC · GDPR · SOC 2 · Network · PII

---

## 1. Authentication Architecture

### Supported Methods

| Method | Available On | Implementation |
|---|---|---|
| Email + Password | All plans | bcrypt hash (cost=12), email verification required |
| Google OAuth2 | All plans | Google Identity Platform |
| GitHub OAuth2 | All plans | GitHub Apps |
| Microsoft OAuth2 | All plans | Azure AD OAuth2 |
| SAML 2.0 SSO | ENTERPRISE, DEDICATED | Okta, Azure AD, Google Workspace |
| OIDC SSO | ENTERPRISE, DEDICATED | Any OIDC-compatible IdP |
| MFA (TOTP) | Optional (all), Enforced (ENTERPRISE) | RFC 6238 — Google Authenticator compatible |

### Token Architecture

```
Sign-up / Login → POST /auth/login
         │
         ▼
engine.auth.token.TokenGenerator.generate_pair(user_id, tenant_id)
         │
         ├── Access Token (JWT RS256)
         │   Payload: { sub, tenant_id, email, role, plan, isolation_tier, exp (+15min), jti }
         │   Stored:  React memory state (NEVER localStorage, NEVER cookie)
         │   Used on: every API request — Authorization: Bearer {token}
         │
         └── Refresh Token (opaque, SHA-256 stored in PostgreSQL)
             Stored:  HttpOnly, Secure, SameSite=Strict cookie (7 day TTL)
             Used on: POST /auth/refresh only
             Rotation: single-use — each refresh issues a new refresh token

Auto-refresh:
  Axios interceptor detects 401 → POST /auth/refresh → new access token in memory
  If refresh fails (expired/revoked) → redirect to /login
```

### API Key Authentication

```
Key generation: engine.auth.api_key.APIKeyManager.generate()
  → Generates: wfk_{random_32_bytes_base64url}
  → Stores:   SHA-256(key) in PostgreSQL api_keys table
  → Returns:  full key to user ONCE (never stored in plaintext)

Key validation on request:
  X-API-Key: wfk_{...}
  → SHA-256(key) → PostgreSQL lookup → resolve user_id + tenant_id + scopes
  → Build same request context as JWT auth (same Depends() chain)

Scopes:
  workflows:read   workflows:write   executions:read   executions:write
  logs:read        nodes:read        admin (Owner only)
```

---

## 2. RBAC Model

### Roles

```
OWNER (one per tenant)
  ├── All EDITOR permissions
  ├── Manage team: invite/remove members, change roles
  ├── Manage billing: plan upgrade, payment method, view invoices
  ├── Configure SSO (ENTERPRISE only)
  ├── View + manage all API keys (team-wide)
  ├── Configure integrations: OAuth connections, webhooks
  ├── Configure PII policy
  └── Request GDPR data erasure

EDITOR
  ├── Create, view, edit, delete workflows
  ├── Trigger and cancel executions
  ├── View all executions and logs
  ├── Manage own API keys (create, view, revoke own keys only)
  ├── Configure integration connections (own)
  └── Use all built-in node types

VIEWER (read-only)
  ├── View workflows (cannot edit)
  ├── View executions and logs
  └── View dashboard and metrics
```

### Enforcement

Role enforcement happens at two layers:

**Layer 1 — API middleware**
```python
# workflow-api/auth/middleware.py
def require_role(*roles: str):
    async def dependency(tenant: Tenant = Depends(get_current_tenant)):
        if tenant.current_user_role not in roles:
            raise ForbiddenError(f"Required role: {roles}")
    return Depends(dependency)

# Usage in routes:
@router.delete("/workflows/{id}", dependencies=[require_role("owner", "editor")])
@router.get("/settings/billing", dependencies=[require_role("owner")])
```

**Layer 2 — SDK validation**
```python
# engine/validation/pipeline.py
# PlanAccessChecker also verifies role has access to this node type
# ForbiddenError propagates up to API global exception handler → HTTP 403
```

---

## 3. GDPR Compliance

### Data Residency Enforcement

```
Tenant signs up → chooses home_region (us-east-1 | eu-west-1 | ap-southeast-1)
home_region stored in PostgreSQL tenants table

Every request:
  TenantContextMiddleware reads tenant.home_region
  If current_region != home_region → HTTP 307 redirect to correct region endpoint

Every database write:
  MongoDB Atlas cluster in home_region
  S3 bucket in home_region
  Redis in home_region
  PostgreSQL RDS in home_region
```

### Right to Erasure (GDPR Article 17)

```python
# engine/privacy/gdpr.py

class GDPRHandler:
    async def delete_user_data(self, user_id: str, tenant_id: str) -> DeletionReport:
        """
        Cascade deletion across all stores.
        Returns audit report of what was deleted.
        Irreversible — requires Owner confirmation.
        """
        deleted = []

        # 1. PostgreSQL: user record + api keys + oauth tokens
        await self.pg.execute("DELETE FROM users WHERE id = $1", user_id)
        await self.pg.execute("DELETE FROM api_keys WHERE user_id = $1", user_id)
        await self.pg.execute("DELETE FROM oauth_tokens WHERE user_id = $1", user_id)
        deleted.append("postgresql:user_records")

        # 2. MongoDB: execution runs created by this user
        await self.mongo.execution_runs.update_many(
            {"created_by": user_id},
            {"$set": {"created_by": "[deleted]", "input": "[redacted_gdpr]"}}
        )
        deleted.append("mongodb:execution_runs")

        # 3. MongoDB: audit log pseudonymization (cannot delete — SOC 2 retention)
        await self.mongo.audit_log.update_many(
            {"user_id": user_id},
            {"$set": {"user_id": f"[deleted:{hash(user_id)[:8]}]"}}
        )
        deleted.append("mongodb:audit_log_pseudonymized")

        # 4. Redis: active sessions
        await self.redis.delete(f"session:{user_id}:*")
        deleted.append("redis:sessions")

        # 5. S3: user-uploaded files
        await self.s3.delete_prefix(f"{tenant_id}/uploads/{user_id}/")
        deleted.append("s3:user_uploads")

        return DeletionReport(user_id=user_id, deleted=deleted, completed_at=datetime.utcnow())
```

### Data Processing Agreement
Generated automatically on ENTERPRISE signup. Stored in PostgreSQL with acceptance timestamp and IP address.

---

## 4. SOC 2 Type II Controls

### CC6 — Logical Access Controls
- All API endpoints require authentication (no public routes except `/health`, `/auth/*`)
- JWT expiry enforced (15 min access token)
- MFA enforced for ENTERPRISE tenants
- API keys are scoped — minimum necessary permissions
- Quarterly access review process documented

### CC7 — System Operations
- CloudWatch alarms for: error rate >1%, API latency p99 >2s, queue depth >500
- Incident response runbook in `/docs/deployment/incident-response.md`
- Automated dependency vulnerability scanning (weekly `pip-audit` + `npm audit`)
- All changes via PR with required review (no direct commits to main)

### CC8 — Change Management
- Infrastructure changes via Terraform with PR review
- SDK releases require version bump + CHANGELOG entry
- Database migrations require review + rollback plan

### CC9 — Risk Mitigation
- Encryption at rest: AES-256 (AWS KMS) for all databases and S3
- Encryption in transit: TLS 1.3 minimum (enforced at ALB + RDS + ElastiCache)
- WAF rules on ALB: SQL injection, XSS, rate limiting at edge

---

## 5. Network Security

```
VPC Layout (per region):
  CIDR: 10.0.0.0/16

  Public Subnets (3 AZs): 10.0.1.0/24, 10.0.2.0/24, 10.0.3.0/24
    → ALB only — no application workloads

  Private Subnets (3 AZs): 10.0.10.0/24, 10.0.11.0/24, 10.0.12.0/24
    → EKS nodes, RDS, ElastiCache

  Database Subnets (3 AZs): 10.0.20.0/24, 10.0.21.0/24, 10.0.22.0/24
    → RDS, ElastiCache — no EKS access directly (security group controlled)

Security Groups:
  alb-sg:      inbound 443 from 0.0.0.0/0 | outbound to eks-api-sg
  eks-api-sg:  inbound from alb-sg | outbound to eks-worker-sg, db-sg
  eks-worker-sg: inbound from eks-api-sg | outbound to db-sg, internet (for LLM APIs)
  db-sg:       inbound from eks-api-sg + eks-worker-sg only | no outbound
  sandbox-sg:  inbound from eks-worker-sg only | no outbound (blocked at K8s NetworkPolicy)
```

### WAF Rules (AWS WAF on ALB)
- Rate limit: 1000 req/5min per IP (prevents scraping/DDoS)
- SQL injection protection
- XSS protection
- Block known malicious IPs (AWS managed threat intelligence)
- Geographic blocking: configurable per compliance requirement

---

## 6. PII Handling

### Detection Engine
Microsoft Presidio with English language model. Detects: email, phone, SSN, credit card, passport, date of birth, name, address, IP address, URL, medical record number.

### Policy Enforcement

```python
# engine/privacy/detector.py

class PIIDetector:
    async def scan_dict(self, data: dict, policy: PIIPolicy) -> PIIScanResult:
        text = json.dumps(data)
        findings = self.analyzer.analyze(text=text, language="en")

        if not findings:
            return PIIScanResult(has_pii=False, findings=[])

        match policy:
            case PIIPolicy.SCAN_WARN:
                return PIIScanResult(has_pii=True, findings=findings, action="warned")

            case PIIPolicy.SCAN_MASK:
                masked = self.masker.anonymize(text=text, analyzer_results=findings)
                return PIIScanResult(has_pii=True, findings=findings,
                                     masked_data=json.loads(masked.text), action="masked")

            case PIIPolicy.SCAN_BLOCK:
                raise PIIDetectedError(
                    f"PII detected ({len(findings)} entities). Execution blocked by policy.",
                    findings=[f.entity_type for f in findings]
                )
```

### What Gets Scanned
- Workflow execution inputs (scanned before storing `ExecutionRun`)
- Node outputs before storing to context (Redis/S3)
- Audit log entries before writing to MongoDB

Prompt content sent to LLM providers is **not** scanned in real-time (latency cost too high). Tenants are advised to use `SCAN_BLOCK` policy if sending data to AI nodes.
