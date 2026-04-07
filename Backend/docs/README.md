# AI Workflow Builder Platform — Documentation
## Complete Technical Reference

---

## Documentation Structure

```
docs/
├── architecture/          System design, layer model, tenancy, ADRs
├── workflow-engine/       SDK — the core product
├── node-framework/        Built-in node types, registry, execution contract
├── backend-services/      API, Worker, Scheduler, CLI
├── frontend/              Next.js UI, canvas, state management
├── execution-engine/      Isolation tiers, sandbox, run lifecycle
├── infrastructure/        AWS, EKS, databases, regions, secrets
├── security/              Auth, RBAC, GDPR, SOC 2, PII, network
├── billing/               Composite billing model, quotas, usage tracking
├── integrations/          Connectors, notifications, CloudWatch
├── deployment/            CI/CD, Docker, Helm, migrations, environments
└── roadmap/               v1.0 MVP → v2.0 full platform
```

---

## Quick Navigation

| I want to understand... | Go to |
|---|---|
| How the system is structured | `/architecture/overview.md` |
| All architecture decisions and why | `/architecture/decision-log.md` |
| How shared vs dedicated tenancy works | `/architecture/tenancy-model.md` |
| The SDK and all its modules | `/workflow-engine/overview.md` |
| All 7 node types | `/node-framework/overview.md` |
| How execution isolation works | `/execution-engine/overview.md` |
| The FastAPI backend routes | `/backend-services/overview.md` |
| The frontend UI architecture | `/frontend/overview.md` |
| The AWS infrastructure | `/infrastructure/overview.md` |
| Auth, RBAC, GDPR, SOC 2 | `/security/overview.md` |
| How billing is calculated | `/billing/overview.md` |
| All external connectors | `/integrations/overview.md` |
| CI/CD and deployment | `/deployment/overview.md` |
| What to build and in what order | `/roadmap/overview.md` |

---

## Key Decisions at a Glance

| Decision | Choice |
|---|---|
| Tenancy | Hybrid: SHARED (FREE/STARTER/PRO) + DEDICATED (ENTERPRISE) |
| Execution isolation | 4-tier: Tier 0 (direct) → Tier 3 (Firecracker MicroVM) |
| Billing | Composite: base + node + LLM tokens + compute seconds + storage |
| Node authorship | Platform team only — users configure, never create nodes |
| User logic entry | TransformNode Python sandbox (Tier 2 — gVisor) |
| Auth | Email/Password + Google/GitHub/Microsoft OAuth + SAML/OIDC SSO |
| Team structure | Flat: Owner + Editor + Viewer |
| Cloud | AWS (EKS, RDS, MongoDB Atlas, ElastiCache, S3, CloudWatch) |
| Compliance | GDPR + SOC 2 Type II (v1.0), HIPAA (v2.0) |
| Regions | us-east-1 → eu-west-1 → ap-southeast-1 |
| MVP scope | Option B: Trigger + AI + API + Logic + Transform nodes |
| Full scope | Option D: all nodes + hybrid tenancy + all regions + HIPAA |

---

## Technology Stack Summary

```
Backend SDK:   Python 3.12 · Pydantic v2 · httpx · motor · redis[asyncio] · asyncpg
API:           FastAPI · Uvicorn · Celery · Redis
Frontend:      Next.js 14 · TypeScript · React Flow · Zustand · TanStack Query
               Monaco Editor · Tailwind CSS · shadcn/ui
Database:      MongoDB Atlas · RDS PostgreSQL 16 + pgvector · ElastiCache Redis 7
Storage:       S3
Infra:         EKS · ECR · Route53 · ACM · AWS Secrets Manager
Observability: CloudWatch · X-Ray
LLM Providers: Gemini Flash/Pro · Claude Haiku/Sonnet/Opus · GPT-4o · Bedrock
Sandbox:       RestrictedPython (Tier 1) · gVisor (Tier 2) · Firecracker (Tier 3)
Compliance:    GDPR · SOC 2 Type II · HIPAA (v2.0)
```

---

## Documentation Generated From

Requirements gathered through 10 interactive Q&A sessions covering:
1. Tenancy model (hybrid B+C)
2. Execution isolation (4-tier, pay-per-use)
3. Billing model (composite 5-component)
4. User personas (progressive complexity)
5. Node system (platform team only)
6. MVP scope (Option B, full Option D docs)
7. Authentication & team structure (A3+B4)
8. Infrastructure & deployment (AWS, SaaS-only, C1→C3)
9. Compliance & data (GDPR+SOC2, tenant-configurable PII)
10. Integrations (defined connector set, CloudWatch)
