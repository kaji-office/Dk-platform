# ─────────────────────────────────────────────────────────────────────────────
# AI Workflow Builder — Developer Commands
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help dev dev-down dev-logs install install-dev migrate \
        test test-unit test-integration test-e2e test-cov \
        lint format typecheck layer-check check \
        run-api run-worker run-scheduler run-ui \
        clean keys

# Default target
help:
	@echo ""
	@echo "  AI Workflow Builder — Available Commands"
	@echo ""
	@echo "  Setup:"
	@echo "    make install        Install all packages in editable mode"
	@echo "    make install-dev    Install with dev dependencies"
	@echo "    make keys           Generate JWT RS256 key pair"
	@echo "    make dev            Start local infrastructure (Docker)"
	@echo "    make dev-down       Stop local infrastructure"
	@echo "    make migrate        Run PostgreSQL Alembic migrations"
	@echo ""
	@echo "  Development:"
	@echo "    make run-api        Start FastAPI dev server (port 8000)"
	@echo "    make run-worker     Start Celery worker"
	@echo "    make run-scheduler  Start Celery beat scheduler"
	@echo "    make run-ui         Start Next.js dev server (port 3000)"
	@echo ""
	@echo "  Testing:"
	@echo "    make test           Run all tests"
	@echo "    make test-unit      Run SDK unit tests (no Docker needed)"
	@echo "    make test-integration Run integration tests (Docker required)"
	@echo "    make test-cov       Run tests with coverage report"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint           Run ruff linter"
	@echo "    make format         Run ruff formatter"
	@echo "    make typecheck      Run mypy type checker"
	@echo "    make layer-check    Enforce SDK layer boundaries"
	@echo "    make check          Run all quality checks (CI equivalent)"
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────

install:
	pip install -e packages/workflow-engine
	pip install -e packages/workflow-api
	pip install -e packages/workflow-worker
	pip install -e packages/workflow-cli

install-dev:
	pip install -e "packages/workflow-engine[dev]"
	pip install -e "packages/workflow-api[dev]"
	pip install -e "packages/workflow-worker[dev]"
	pip install -e "packages/workflow-cli[dev]"
	pre-commit install

keys:
	@mkdir -p keys
	openssl genrsa -out keys/private.pem 2048
	openssl rsa -in keys/private.pem -pubout -out keys/public.pem
	@echo "JWT key pair generated in ./keys/"
	@echo "Add to .env: JWT_PRIVATE_KEY_PATH=./keys/private.pem"

dev:
	@cp -n .env.example .env 2>/dev/null || true
	docker compose -f docker-compose.dev.yml up -d
	@echo ""
	@echo "  Services started:"
	@echo "    MongoDB:       localhost:27017"
	@echo "    PostgreSQL:    localhost:5432"
	@echo "    Redis:         localhost:6379"
	@echo "    S3 (LocalStack): localhost:4566"
	@echo "    Flower:        http://localhost:5555  (admin/devpassword)"
	@echo "    Mongo Express: http://localhost:8081  (admin/devpassword)"
	@echo ""
	@echo "  Run 'make migrate' to apply database migrations."

dev-down:
	docker compose -f docker-compose.dev.yml down

dev-logs:
	docker compose -f docker-compose.dev.yml logs -f

migrate:
	cd packages/workflow-api && alembic upgrade head
	cd packages/workflow-engine && python -m workflow_engine.infra.mongodb_indexes

# ─────────────────────────────────────────────────────────────────────────────
# Running services
# ─────────────────────────────────────────────────────────────────────────────

run-api:
	uvicorn workflow_api.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	celery -A workflow_worker.celery_app worker \
		--loglevel=info \
		--queues=default,ai-heavy,critical,scheduled \
		--concurrency=4

run-scheduler:
	celery -A workflow_worker.celery_app beat \
		--loglevel=info \
		--scheduler celery.beat:PersistentScheduler

run-ui:
	cd packages/workflow-ui && npm run dev

# ─────────────────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────────────────

test-unit:
	pytest packages/workflow-engine/tests/unit -v

test-integration:
	pytest packages/workflow-engine/tests/integration -v \
		--timeout=120

test-api:
	pytest packages/workflow-api/tests -v

test-cov:
	pytest packages/workflow-engine/tests \
		--cov=packages/workflow-engine/src/workflow_engine \
		--cov-report=html:coverage_html \
		--cov-report=term-missing \
		--cov-fail-under=85
	@echo "Coverage report: ./coverage_html/index.html"

test:
	$(MAKE) test-unit
	$(MAKE) test-integration
	$(MAKE) test-api

# ─────────────────────────────────────────────────────────────────────────────
# Code quality
# ─────────────────────────────────────────────────────────────────────────────

lint:
	ruff check packages/

format:
	ruff format packages/
	ruff check --fix packages/

typecheck:
	mypy packages/workflow-engine/src/workflow_engine --strict

layer-check:
	cd packages/workflow-engine && lint-imports

check: lint typecheck layer-check
	@echo "All checks passed."

# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf coverage_html .coverage
	@echo "Cleaned."
