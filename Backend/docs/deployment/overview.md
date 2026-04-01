# Deployment — Overview
## CI/CD · Environments · Docker · Helm · Database Migrations

---

## 1. Environment Hierarchy

```
local         Developer laptop — docker-compose, no K8s
development   AWS EKS — auto-deployed on push to develop branch
staging       AWS EKS — mirrors production, auto-deployed on push to main
production    AWS EKS — manual promotion from staging (requires approval)
```

---

## 2. CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml — runs on every PR and push

name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint-and-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: SDK lint
        run: cd packages/workflow-engine && ruff check . && ruff format --check .
      - name: SDK typecheck
        run: cd packages/workflow-engine && mypy src/workflow_engine --strict
      - name: Layer boundary check
        run: cd packages/workflow-engine && importlinter
      - name: Frontend lint
        run: cd packages/workflow-ui && npm run lint

  test:
    runs-on: ubuntu-latest
    services:
      mongodb:
        image: mongo:7
        ports: ["27017:27017"]
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - name: SDK unit tests
        run: cd packages/workflow-engine && pytest tests/unit -v --cov=src
      - name: SDK integration tests
        run: cd packages/workflow-engine && pytest tests/integration -v
      - name: API tests
        run: cd packages/workflow-api && pytest tests -v
      - name: Frontend tests
        run: cd packages/workflow-ui && npm test

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Python dependency audit
        run: pip-audit -r packages/workflow-engine/requirements.txt
      - name: NPM audit
        run: cd packages/workflow-ui && npm audit --audit-level=high
      - name: Container scan
        uses: aquasecurity/trivy-action@master

  build-and-push:
    needs: [lint-and-typecheck, test, security-scan]
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/develop'
    steps:
      - name: Build API image
        run: docker build -t $ECR_REGISTRY/workflow-api:$GITHUB_SHA .
      - name: Build Worker image
        run: docker build -t $ECR_REGISTRY/workflow-worker:$GITHUB_SHA .
      - name: Push to ECR
        run: docker push $ECR_REGISTRY/workflow-api:$GITHUB_SHA

  deploy-staging:
    needs: [build-and-push]
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to staging EKS
        run: |
          helm upgrade --install workflow-platform ./helm \
            --namespace workflow-platform \
            --set image.tag=$GITHUB_SHA \
            --set environment=staging \
            --values ./helm/values-staging.yaml
      - name: Run smoke tests
        run: ./scripts/smoke-test.sh staging

  deploy-production:
    needs: [deploy-staging]
    environment:
      name: production
      url: https://app.workflowplatform.com
    steps:
      - name: Deploy to production EKS
        run: |
          helm upgrade --install workflow-platform ./helm \
            --namespace workflow-platform \
            --set image.tag=$GITHUB_SHA \
            --set environment=production \
            --values ./helm/values-production.yaml
```

---

## 3. Docker Strategy

### Multi-Stage Builds

```dockerfile
# packages/workflow-api/Dockerfile

# Stage 1: Build dependencies
FROM python:3.12-slim AS builder
WORKDIR /build
COPY packages/workflow-engine ./workflow-engine
COPY packages/workflow-api ./workflow-api
RUN pip install --no-deps --prefix=/install ./workflow-engine ./workflow-api

# Stage 2: Runtime image (minimal)
FROM python:3.12-slim AS runtime
COPY --from=builder /install /usr/local
RUN useradd --system --uid 1000 appuser
USER appuser
WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "workflow_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Image Tagging Strategy
```
ECR repository: {account_id}.dkr.ecr.{region}.amazonaws.com/workflow-{service}

Tags:
  :latest       → latest main branch build (staging)
  :{git_sha}    → immutable — every build
  :v1.2.3       → release tag
  :stable       → last known-good production image
```

---

## 4. Helm Chart Structure

```
helm/
├── Chart.yaml
├── values.yaml               # Defaults (overridden per environment)
├── values-staging.yaml       # Staging overrides
├── values-production.yaml    # Production overrides
└── templates/
    ├── _helpers.tpl
    ├── namespace.yaml
    ├── configmap.yaml         # Non-secret config (log level, feature flags)
    ├── serviceaccount.yaml    # IRSA annotations for AWS access
    ├── workflow-api/
    │   ├── deployment.yaml
    │   ├── service.yaml
    │   ├── hpa.yaml           # Horizontal Pod Autoscaler
    │   └── ingress.yaml       # ALB ingress
    ├── workflow-worker/
    │   ├── deployment.yaml
    │   └── hpa.yaml           # Scale on SQS queue depth metric
    ├── workflow-scheduler/
    │   └── deployment.yaml    # replicas: 1, strategy: Recreate
    ├── workflow-sandbox/
    │   ├── runtimeclass.yaml  # gVisor RuntimeClass
    │   └── networkpolicy.yaml
    └── shared/
        ├── pdb.yaml           # PodDisruptionBudget
        └── monitoring.yaml    # CloudWatch agent config
```

### Key Helm Values
```yaml
# values-production.yaml
image:
  pullPolicy: IfNotPresent

api:
  replicas: { min: 2, max: 10 }
  resources:
    requests: { cpu: "500m", memory: "512Mi" }
    limits:   { cpu: "2",    memory: "2Gi" }
  hpa:
    targetCPUUtilizationPercentage: 70

worker:
  replicas: { min: 2, max: 20 }
  resources:
    requests: { cpu: "1",    memory: "1Gi" }
    limits:   { cpu: "4",    memory: "4Gi" }
  hpa:
    custom_metric: celery_queue_depth
    target_value: 50

scheduler:
  replicas: 1
  strategy: Recreate
```

---

## 5. Database Migrations

### PostgreSQL (Alembic)

```
packages/workflow-api/
└── migrations/
    ├── env.py
    ├── alembic.ini
    └── versions/
        ├── 0001_initial_schema.py
        ├── 0002_add_api_keys.py
        └── 0003_add_tenant_isolation_model.py
```

Migrations run as a K8s Job before every deployment:
```yaml
# helm/templates/workflow-api/migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate-{{ .Release.Revision }}
  annotations:
    "helm.sh/hook": pre-upgrade,pre-install
    "helm.sh/hook-delete-policy": hook-succeeded
spec:
  template:
    spec:
      containers:
        - name: migrate
          image: "{{ .Values.image.repository }}/workflow-api:{{ .Values.image.tag }}"
          command: ["alembic", "upgrade", "head"]
      restartPolicy: Never
```

### MongoDB (No schema migrations — document-oriented)
Index changes are applied via a startup script that calls `create_index()` with `background=True`. Idempotent — safe to run on every deployment.

---

## 6. Local Development Environment

```yaml
# docker-compose.dev.yml

services:
  mongodb:
    image: mongo:7
    ports: ["27017:27017"]
    volumes: ["mongo_data:/data/db"]

  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: workflow_platform
      POSTGRES_PASSWORD: devpassword
    volumes: ["pg_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --requirepass devpassword

  localstack:
    image: localstack/localstack
    ports: ["4566:4566"]
    environment:
      SERVICES: s3
      AWS_DEFAULT_REGION: us-east-1
    volumes: ["localstack_data:/var/lib/localstack"]

  flower:
    image: mher/flower
    ports: ["5555:5555"]
    environment:
      CELERY_BROKER_URL: redis://:devpassword@redis:6379/0
    depends_on: [redis]
```

```bash
# Start local environment
make dev

# Run SDK tests (no docker required)
make test-unit

# Run integration tests (requires docker-compose up)
make test-integration

# Apply database migrations
make migrate

# Run API locally
make run-api

# Run worker locally
make run-worker
```

---

## 7. Release Versioning

```
workflow-engine:  Semantic versioning (MAJOR.MINOR.PATCH)
                  MAJOR: breaking SDK API changes
                  MINOR: new modules or capabilities
                  PATCH: bug fixes, performance improvements

Services:         Tagged with SDK version they ship with
                  workflow-api:v1.2.0 ships workflow-engine==1.2.0

Release process:
  1. Update version in packages/workflow-engine/pyproject.toml
  2. Update CHANGELOG.md
  3. Create git tag: git tag v1.2.0
  4. GitHub Actions builds + publishes to private PyPI
  5. All service packages update their workflow-engine dependency pin
  6. Deploy to staging, run smoke tests
  7. Manual approval → deploy to production
```
