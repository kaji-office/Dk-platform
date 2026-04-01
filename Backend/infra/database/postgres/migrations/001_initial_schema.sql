-- ─────────────────────────────────────────────────────────────────────────────
-- AI Workflow Builder — PostgreSQL Initial Schema
-- Migration: 001_initial_schema
-- Applied by: Alembic (make migrate) on first deployment
-- ─────────────────────────────────────────────────────────────────────────────

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";         -- pgvector for semantic cache

-- ─────────────────────────────────────────────────────────────────────────────
-- ENUM types
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TYPE plan_tier AS ENUM ('FREE', 'STARTER', 'PRO', 'ENTERPRISE', 'DEDICATED');
CREATE TYPE isolation_model AS ENUM ('SHARED', 'DEDICATED');
CREATE TYPE user_role AS ENUM ('OWNER', 'EDITOR', 'VIEWER');
CREATE TYPE pii_policy AS ENUM ('SCAN_WARN', 'SCAN_MASK', 'SCAN_BLOCK');

-- ─────────────────────────────────────────────────────────────────────────────
-- TENANTS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE tenants (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                    TEXT NOT NULL,
    slug                    TEXT NOT NULL UNIQUE,          -- URL-safe identifier
    plan_tier               plan_tier NOT NULL DEFAULT 'FREE',
    isolation_model         isolation_model NOT NULL DEFAULT 'SHARED',
    home_region             TEXT NOT NULL DEFAULT 'us-east-1',

    -- Quotas (NULL = unlimited for ENTERPRISE)
    monthly_exec_quota      INTEGER,
    max_concurrent_runs     INTEGER NOT NULL DEFAULT 2,
    max_nodes_per_workflow  INTEGER NOT NULL DEFAULT 10,

    -- Compliance
    pii_policy              pii_policy NOT NULL DEFAULT 'SCAN_MASK',
    retention_days          INTEGER NOT NULL DEFAULT 30,
    gdpr_dpa_accepted_at    TIMESTAMPTZ,
    gdpr_dpa_accepted_ip    INET,

    -- Dedicated infra (ENTERPRISE only — NULLs for SHARED)
    dedicated_mongodb_secret_arn  TEXT,
    dedicated_redis_secret_arn    TEXT,
    dedicated_s3_bucket           TEXT,
    dedicated_k8s_namespace       TEXT,

    -- Billing
    billing_email           TEXT,
    stripe_customer_id      TEXT,

    -- Metadata
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenants_slug ON tenants (slug);
CREATE INDEX idx_tenants_plan_tier ON tenants (plan_tier);
CREATE INDEX idx_tenants_home_region ON tenants (home_region);

-- ─────────────────────────────────────────────────────────────────────────────
-- USERS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email                   TEXT NOT NULL,
    password_hash           TEXT,                         -- NULL for OAuth-only users
    role                    user_role NOT NULL DEFAULT 'EDITOR',
    is_verified             BOOLEAN NOT NULL DEFAULT FALSE,
    verification_token      TEXT,
    verification_expires_at TIMESTAMPTZ,

    -- MFA
    mfa_enabled             BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret              TEXT,                          -- Encrypted TOTP secret
    mfa_backup_codes        TEXT[],                        -- Hashed backup codes

    -- OAuth
    google_id               TEXT,
    github_id               TEXT,
    microsoft_id            TEXT,

    -- SSO
    sso_provider            TEXT,                          -- SAML/OIDC provider name
    sso_subject             TEXT,                          -- Provider's user identifier

    -- Metadata
    last_login_at           TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_users_email_tenant ON users (email, tenant_id);
CREATE UNIQUE INDEX idx_users_google_id ON users (google_id) WHERE google_id IS NOT NULL;
CREATE UNIQUE INDEX idx_users_github_id ON users (github_id) WHERE github_id IS NOT NULL;
CREATE UNIQUE INDEX idx_users_microsoft_id ON users (microsoft_id) WHERE microsoft_id IS NOT NULL;
CREATE INDEX idx_users_tenant_id ON users (tenant_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- API KEYS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    key_prefix      TEXT NOT NULL,                         -- First 8 chars for display (wfk_xxxx...)
    key_hash        TEXT NOT NULL UNIQUE,                  -- SHA-256 of full key
    scopes          TEXT[] NOT NULL DEFAULT '{}',          -- ['workflows:read', 'executions:write']
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_hash ON api_keys (key_hash) WHERE is_active = TRUE;
CREATE INDEX idx_api_keys_user_id ON api_keys (user_id);
CREATE INDEX idx_api_keys_tenant_id ON api_keys (tenant_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- REFRESH TOKENS (rotation-based)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,                  -- SHA-256 of opaque token
    expires_at      TIMESTAMPTZ NOT NULL,
    is_revoked      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens (token_hash) WHERE is_revoked = FALSE;
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens (user_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- OAUTH TOKENS (connector credentials per tenant)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE oauth_tokens (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    connector_id        TEXT NOT NULL,                     -- 'slack' | 'github' | 'salesforce' etc.
    provider_user_id    TEXT,
    access_token        TEXT NOT NULL,                     -- Encrypted (AES-256 via pgcrypto)
    refresh_token       TEXT,                              -- Encrypted
    token_type          TEXT NOT NULL DEFAULT 'Bearer',
    scopes              TEXT[],
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_oauth_tokens_tenant_connector ON oauth_tokens (tenant_id, connector_id, user_id);
CREATE INDEX idx_oauth_tokens_expires ON oauth_tokens (expires_at) WHERE refresh_token IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- LLM COST RECORDS (billing — per AI node execution)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE llm_cost_records (
    id              UUID NOT NULL DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    run_id          TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(12, 8) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Quarterly partitions (use pg_partman in production to auto-create future quarters)
-- NOTE: Add a new quarter partition BEFORE each period starts or inserts will fail.
CREATE TABLE llm_cost_records_2024_q1 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE llm_cost_records_2024_q2 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE llm_cost_records_2024_q3 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE llm_cost_records_2024_q4 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2024-10-01') TO ('2025-01-01');
CREATE TABLE llm_cost_records_2025_q1 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE llm_cost_records_2025_q2 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE llm_cost_records_2025_q3 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE llm_cost_records_2025_q4 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE llm_cost_records_2026_q1 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
CREATE TABLE llm_cost_records_2026_q2 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');
CREATE TABLE llm_cost_records_2026_q3 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');
CREATE TABLE llm_cost_records_2026_q4 PARTITION OF llm_cost_records
    FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');

CREATE INDEX idx_llm_costs_tenant_date ON llm_cost_records (tenant_id, created_at DESC);
CREATE INDEX idx_llm_costs_run_id ON llm_cost_records (run_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- NODE EXECUTION RECORDS (billing — per node execution)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE node_exec_records (
    id                  UUID NOT NULL DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    run_id              TEXT NOT NULL,
    node_id             TEXT NOT NULL,
    node_type           TEXT NOT NULL,
    isolation_tier      SMALLINT NOT NULL DEFAULT 0,
    compute_seconds     NUMERIC(8, 3) NOT NULL DEFAULT 0,
    output_bytes        INTEGER NOT NULL DEFAULT 0,
    s3_spilled          BOOLEAN NOT NULL DEFAULT FALSE,
    status              TEXT NOT NULL,
    node_cost_usd       NUMERIC(12, 8) NOT NULL DEFAULT 0,
    compute_cost_usd    NUMERIC(12, 8) NOT NULL DEFAULT 0,
    storage_cost_usd    NUMERIC(12, 8) NOT NULL DEFAULT 0,
    started_at          TIMESTAMPTZ NOT NULL,
    ended_at            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE node_exec_records_2025_q1 PARTITION OF node_exec_records
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE node_exec_records_2025_q2 PARTITION OF node_exec_records
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE node_exec_records_2025_q3 PARTITION OF node_exec_records
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE node_exec_records_2025_q4 PARTITION OF node_exec_records
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE node_exec_records_2026_q1 PARTITION OF node_exec_records
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
CREATE TABLE node_exec_records_2026_q2 PARTITION OF node_exec_records
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');
CREATE TABLE node_exec_records_2026_q3 PARTITION OF node_exec_records
    FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');
CREATE TABLE node_exec_records_2026_q4 PARTITION OF node_exec_records
    FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');

CREATE INDEX idx_node_exec_tenant_date ON node_exec_records (tenant_id, created_at DESC);
CREATE INDEX idx_node_exec_run_id ON node_exec_records (run_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- TENANT USAGE SUMMARY (hourly aggregation for fast billing queries)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE tenant_usage_summary (
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    period_start        TIMESTAMPTZ NOT NULL,              -- Truncated to hour
    period_end          TIMESTAMPTZ NOT NULL,
    execution_count     INTEGER NOT NULL DEFAULT 0,
    node_exec_count     INTEGER NOT NULL DEFAULT 0,
    total_input_tokens  BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    total_compute_secs  NUMERIC(12, 3) NOT NULL DEFAULT 0,
    total_cost_usd      NUMERIC(14, 6) NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, period_start)
);

CREATE INDEX idx_usage_summary_tenant_period ON tenant_usage_summary (tenant_id, period_start DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- SEMANTIC CACHE (pgvector — LLM response deduplication)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE semantic_cache (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    model           TEXT NOT NULL,
    prompt_hash     TEXT NOT NULL,                         -- SHA-256 for exact match
    embedding       vector(1536),                          -- For similarity search
    response        TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    hit_count       INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_hit_at     TIMESTAMPTZ
);

CREATE INDEX idx_semantic_cache_hash ON semantic_cache (tenant_id, model, prompt_hash);
CREATE INDEX idx_semantic_cache_embedding ON semantic_cache
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ─────────────────────────────────────────────────────────────────────────────
-- PASSWORD RESET TOKENS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE password_reset_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pwd_reset_hash ON password_reset_tokens (token_hash) WHERE used_at IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- AUTO-UPDATE updated_at trigger
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_oauth_tokens_updated_at
    BEFORE UPDATE ON oauth_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
