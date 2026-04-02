-- ─────────────────────────────────────────────────────────────────────────────
-- AI Workflow Builder — PostgreSQL Webhooks Schema
-- Migration: 002_webhooks
-- Depends on: 001_initial_schema (tenants table must exist)
-- ─────────────────────────────────────────────────────────────────────────────

-- ─────────────────────────────────────────────────────────────────────────────
-- WEBHOOKS (outbound + inbound registration per tenant)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE webhooks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    workflow_id     TEXT NOT NULL,                          -- Target workflow to trigger on inbound
    name            TEXT NOT NULL,
    events          TEXT[] NOT NULL DEFAULT '{"execution.completed"}',
    webhook_secret  TEXT,                                   -- Plaintext secret; protect at rest via pgcrypto in prod
    endpoint_url    TEXT,                                   -- Outbound delivery URL (future use)
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_webhooks_tenant_id    ON webhooks (tenant_id)   WHERE active = TRUE;
CREATE INDEX idx_webhooks_workflow_id  ON webhooks (workflow_id) WHERE active = TRUE;

CREATE TRIGGER update_webhooks_updated_at
    BEFORE UPDATE ON webhooks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────────
-- WEBHOOK DELIVERIES (audit log for inbound events + outbound attempts)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE webhook_deliveries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    webhook_id      UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL,
    workflow_id     TEXT NOT NULL,
    event_type      TEXT NOT NULL DEFAULT 'inbound',        -- 'inbound' | 'execution.completed' etc.
    payload         JSONB NOT NULL DEFAULT '{}',
    response_status INTEGER,                                -- HTTP status of outbound delivery; NULL for inbound
    delivered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_webhook_deliveries_webhook_id  ON webhook_deliveries (webhook_id);
CREATE INDEX idx_webhook_deliveries_tenant_date ON webhook_deliveries (tenant_id, delivered_at DESC);
