-- ─────────────────────────────────────────────────────────────────────────────
-- AI Workflow Builder — PostgreSQL
-- Migration: 004_pii_disabled
-- Depends on: 001_initial_schema (pii_policy ENUM must exist)
--
-- Adds DISABLED to the pii_policy ENUM so the application-level PIIPolicy enum
-- (workflow_engine/models/tenant.py) stays in sync with the database type.
-- DISABLED means no PII scanning is performed — useful for dev/internal tenants.
--
-- NOTE: ALTER TYPE ... ADD VALUE cannot run inside a transaction block in
-- PostgreSQL < 12. In PG 12+ it is safe inside a transaction.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TYPE pii_policy ADD VALUE IF NOT EXISTS 'DISABLED' BEFORE 'SCAN_WARN';
