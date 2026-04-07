# Development Roadmap
## v1.0 MVP → v2.0 Full Platform (Option D)

---

## Version Summary

| Version | Scope | Target |
|---|---|---|
| **v1.0** | MVP — Core + Transform (Option B) | Ship fast, validate, charge real users |
| **v1.1** | Extended node set + MCP + Human-in-loop | Complete node system |
| **v1.2** | Full hybrid tenancy + multi-region | Production-grade infrastructure |
| **v2.0** | Option D complete — HIPAA + Tier 3 + APAC | Full platform as documented |

---

## v1.0 — MVP (Option B: Core + Transform)

### Scope

**Included:**
- Workflow builder UI (visual canvas, form + code mode)
- Node types: TriggerNode, AINode, APINode, LogicNode, TransformNode (Tier 1 + Tier 2)
- Execution monitoring (WebSocket real-time status)
- Version history + rollback
- Shared tenancy only (SHARED infrastructure for all)
- Auth: Email + Password + Google OAuth
- Billing: All 5 components, FREE + STARTER + PRO plans
- Integrations: Slack, Email, GitHub, PostgreSQL, S3
- Observability: CloudWatch logs + basic metrics
- Region: us-east-1 only
- Compliance: GDPR basics (data residency, right to erasure)

**Deferred to v1.1:**
- MCPNode
- HumanNode
- Microsoft Teams, Discord, Salesforce, MongoDB, MySQL, Redis, OneDrive, Google Sheets connectors
- GitHub OAuth, Microsoft OAuth, SSO
- ENTERPRISE plan + dedicated infrastructure
- SOC 2 Type II certification (evidence collection starts in v1.0)

### SDK Build Order (Weeks 1–10)

```
WEEK 1:  Phase 0 — Pre-development (schemas, docker-compose, CI, monorepo scaffold)
WEEK 2:  Phase 1 — engine.config + engine.models (all 12 model files)
WEEK 3:  Phase 2a — engine.dag (parser, topo_sort, parallel, plan)
WEEK 4:  Phase 2b — engine.nodes (base, registry, stubs for 5 node types)
         Phase 2c — engine.validation (all 7 checkers + pipeline)
WEEK 5:  Phase 3a — engine.state (transitions, persistence, machine)
         Phase 3b — engine.context (redis_store, s3_store, resolver, manager)
WEEK 6:  Phase 3c — engine.executor (retry, timeout, dispatcher, node_executor, orchestrator)
WEEK 7:  Phase 4a — engine.sandbox (limits, restricted, container/gVisor, manager)
         Phase 4b — engine.providers (base, registry, router, rate_limiter, token_counter)
WEEK 8:  Phase 4c — engine.providers (gemini, anthropic, openai, bedrock, tool_calling)
         Phase 4d — engine.integrations (rest_adapter, webhook_handler, oauth_manager)
                    engine.integrations.connectors (slack, email, github, postgresql, s3)
WEEK 9:  Phase 4e — engine.cache, engine.versioning, engine.privacy, engine.events
         Phase 4f — engine.auth, engine.billing, engine.health, engine.scheduler
                    engine.notifications
WEEK 10: Phase 5 — Node execute() implementations (Trigger, AI, API, Logic, Transform)
```

### Delivery Layer Build Order (Weeks 11–14)

```
WEEK 11: workflow-worker (orchestrate_run, cleanup_run, scheduler_fire_cron)
         workflow-api (main, dependencies, middleware, auth routes, health routes)
WEEK 12: workflow-api (workflow routes, execution routes, version routes, node routes)
         workflow-api (WebSocket hub, SSE log stream)
WEEK 13: workflow-ui (auth module, layout, dashboard)
         workflow-ui (workflow builder canvas — canvas + palette + config panel)
WEEK 14: workflow-ui (execution monitoring, version history)
         End-to-end integration testing
         Smoke test suite
```

### Definition of Done — v1.0

> **Status as of 2026-04-02:** Backend fully tested (60/60 endpoints pass, 24 bugs found and fixed). Frontend pending.

- [x] User can sign up, create a workflow, trigger it, and see real-time execution — **verified end-to-end**
- [x] AI node calls Vertex AI (Gemini) successfully — MockLLMProvider in dev, real provider in staging
- [x] TransformNode Python sandbox executes and returns output — **verified**
- [x] Audit log writes wired to key events (auth, workflow, execution, schedule)
- [x] Schedule-triggered runs dispatch with correct `input_data` from schedule model
- [x] Redis-backed rate limiter (SlowAPI, 60 req/min per tenant)
- [x] Chat WebSocket streaming via Redis PubSub
- [x] Webhooks (inbound + outbound) — PostgreSQL-backed
- [x] Email verification + password reset via SMTP
- [ ] Billing records written per node execution (`node_exec_records` table pending)
- [ ] JWT logout invalidation (no-op in v1 — JTI blocklist deferred to v1.1)
- [ ] GDPR erasure pipeline tested
- [ ] CloudWatch dashboards showing execution metrics
- [ ] All SDK unit tests passing (>90% coverage)
- [ ] Integration tests green with testcontainers
- [ ] Deployment pipeline: PR → staging → production
- [ ] Smoke test suite passes on staging
- [ ] **workflow-ui** — canvas + node config + execution monitor (next sprint)

---

## v1.1 — Extended Node Set

**Timeline:** 6 weeks after v1.0 launch

### What Ships

- **MCPNode** — MCP client, tool discovery, execution, caching
- **HumanNode** — pause/resume, notification, form config, timeout
- **Remaining connectors:**
  - Communication: Discord, Microsoft Teams
  - Data & Storage: Google Sheets, OneDrive
  - Databases: MySQL, MongoDB, Redis
  - CRM: Salesforce
- **GitHub OAuth** + **Microsoft OAuth** sign-in
- **Workflow templates** gallery (starter templates for common patterns)
- **CLI** (`wf validate`, `wf deploy`, `wf run`, `wf logs`)
- **Improved observability:** X-Ray distributed traces visible in UI

### SDK Changes
- `MCPNodeType.execute()` complete
- `HumanNodeType.execute()` complete (correlation ID pattern)
- `engine.templates` module
- All remaining connector implementations

---

## v1.2 — Full Hybrid Tenancy + Multi-Region

**Timeline:** 10 weeks after v1.1

### What Ships

- **ENTERPRISE plan** + dedicated infrastructure provisioning
- **Dedicated K8s namespace per ENTERPRISE tenant**
- **Dedicated MongoDB Atlas cluster** provisioned via Atlas Admin API
- **Dedicated ElastiCache** per ENTERPRISE tenant
- **eu-west-1 region** — EU data residency for GDPR tenants
- **SAML/OIDC SSO** for ENTERPRISE
- **MFA enforcement** for ENTERPRISE tenants
- **Admin panel** — tenant management, quota management, GDPR erasure requests
- **SOC 2 Type II audit** started (evidence collection from v1.0)
- **Terraform infrastructure-as-code** for all AWS resources

### Architecture Additions
- `TenantRegistry` with Redis cache layer
- `InfrastructureProvisioner` service for ENTERPRISE onboarding
- Route53 geo-routing for region-based request routing
- TenantContextMiddleware: enforce `home_region` on every request

---

## v2.0 — Option D Complete

**Timeline:** 16 weeks after v1.2

### What Ships

- **Firecracker MicroVM (Tier 3)** — full VM isolation for ENTERPRISE
- **VM warm pool** management
- **HIPAA compliance** — PHI handling, BAAs, audit hardening
- **ap-southeast-1 region** — APAC coverage
- **Per-workflow PII policy** for ENTERPRISE (currently per-tenant)
- **Legal hold** for audit logs (ENTERPRISE)
- **Advanced billing** — custom contract pricing for ENTERPRISE, invoice customization
- **Workflow marketplace / template publishing** — tenants share templates
- **Semantic cache** (pgvector) — cross-request LLM response deduplication
- **Advanced analytics** — cost per workflow, node performance heatmaps
- **SDK published** to private PyPI registry — versioned independently

### SDK State at v2.0
All 19 modules complete and production-hardened. SDK publishable as a standalone package.

---

## Critical Path

```
Phase 0 decisions + infrastructure
          │
          ▼
engine.models (foundation)
          │
          ▼
engine.dag + engine.validation
          │
          ▼
engine.state + engine.context + engine.executor
          │
          ▼
engine.providers + engine.sandbox + engine.integrations
          │
          ▼
Node execute() implementations (5 nodes for v1.0)
          │
          ▼
workflow-worker (Celery tasks)
          │
          ▼
workflow-api (routes + WebSocket)
          │
          ▼
workflow-ui (builder + monitoring)
          │
          ▼
v1.0 LAUNCH
```

Everything else (CLI, templates, ENTERPRISE infra, additional connectors, HIPAA, Tier 3) is off the critical path and can be developed in parallel or post-launch.

---

## Parallel Work Streams

```
WEEKS       STREAM 1 (SDK Core)           STREAM 2 (Infra)              STREAM 3 (Frontend)
──────────  ──────────────────────────    ──────────────────────────    ────────────────────
1           Phase 0: all decisions        docker-compose.dev.yml        Figma designs
            monorepo scaffold             DB schemas + DDL
2–4         engine.models                 CI pipeline                   Component library
            engine.dag + validation       Alembic migrations            React Flow node shells
5–6         engine.state                  EKS cluster setup             Auth UI (mock API)
            engine.context                CloudWatch config             Dashboard (mock data)
            engine.executor
7–9         engine.providers              Helm chart draft              Builder canvas (mock)
            engine.sandbox                Secrets Manager setup         Node config forms
            engine.integrations           S3 + ECR setup                WebSocket hook
            engine.billing + auth
10          Node execute() methods        Staging deployment            Real API integration
11–12       workflow-worker               Load testing setup            Execution monitoring
            workflow-api                  Production deployment          Version history
13–14       Integration tests             Smoke tests                   E2E tests (Playwright)
            workflow-cli                  Monitoring dashboards         Settings pages
```
