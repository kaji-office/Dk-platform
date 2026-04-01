"""
MongoDB Collection Bootstrap + Index Definitions
=================================================
Run on every deployment startup (idempotent — create_index is safe to re-run).

Usage:
    python -m infra.database.mongodb.indexes
    # or via Makefile: make migrate
"""

import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel


MONGODB_URL = os.environ["MONGODB_URL"]


# ─────────────────────────────────────────────────────────────────────────────
# Collection + Index Definitions
# ─────────────────────────────────────────────────────────────────────────────

COLLECTION_INDEXES: dict[str, list[IndexModel]] = {

    # ── workflows ────────────────────────────────────────────────────────────
    "workflows": [
        IndexModel(
            [("tenant_id", ASCENDING), ("workflow_id", ASCENDING)],
            unique=True,
            name="idx_tenant_workflow_unique",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("updated_at", DESCENDING)],
            name="idx_tenant_updated",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("metadata.name", ASCENDING)],
            name="idx_tenant_name",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("metadata.is_active", ASCENDING)],
            name="idx_tenant_active",
        ),
    ],

    # ── workflow_versions ─────────────────────────────────────────────────────
    "workflow_versions": [
        IndexModel(
            [("tenant_id", ASCENDING), ("workflow_id", ASCENDING), ("version_no", DESCENDING)],
            unique=True,
            name="idx_tenant_workflow_version_unique",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("workflow_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_tenant_workflow_versions_list",
        ),
        IndexModel(
            [("sdk_version", ASCENDING)],
            name="idx_sdk_version",
        ),
    ],

    # ── execution_runs ────────────────────────────────────────────────────────
    "execution_runs": [
        IndexModel(
            [("run_id", ASCENDING)],
            unique=True,
            name="idx_run_id_unique",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("status", ASCENDING), ("started_at", DESCENDING)],
            name="idx_tenant_status_date",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("workflow_id", ASCENDING), ("started_at", DESCENDING)],
            name="idx_tenant_workflow_runs",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("started_at", DESCENDING)],
            name="idx_tenant_runs_date",
        ),
        # TTL index — auto-delete runs past retention window
        # NOTE: retention_expires_at must be set on insert based on tenant.retention_days
        IndexModel(
            [("retention_expires_at", ASCENDING)],
            expireAfterSeconds=0,
            name="idx_retention_ttl",
            sparse=True,
        ),
    ],

    # ── node_executions ───────────────────────────────────────────────────────
    "node_executions": [
        IndexModel(
            [("run_id", ASCENDING), ("node_id", ASCENDING)],
            unique=True,
            name="idx_run_node_unique",
        ),
        IndexModel(
            [("run_id", ASCENDING)],
            name="idx_run_id",
        ),
        IndexModel(
            [("run_id", ASCENDING), ("status", ASCENDING)],
            name="idx_run_node_status",
        ),
        # TTL index matches parent execution_run
        IndexModel(
            [("retention_expires_at", ASCENDING)],
            expireAfterSeconds=0,
            name="idx_node_retention_ttl",
            sparse=True,
        ),
    ],

    # ── audit_log (append-only — no deletes, only pseudonymization for GDPR) ──
    "audit_log": [
        IndexModel(
            [("tenant_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_tenant_audit_date",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("event_type", ASCENDING), ("created_at", DESCENDING)],
            name="idx_tenant_audit_type_date",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("resource_id", ASCENDING)],
            name="idx_tenant_audit_resource",
        ),
        IndexModel(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_user_audit_date",
        ),
        # SOC 2 requires 1-year minimum retention — TTL set to 400 days
        IndexModel(
            [("created_at", ASCENDING)],
            expireAfterSeconds=34_560_000,  # 400 days
            name="idx_audit_log_ttl",
        ),
    ],

    # ── schedules ─────────────────────────────────────────────────────────────
    "schedules": [
        IndexModel(
            [("tenant_id", ASCENDING), ("workflow_id", ASCENDING)],
            name="idx_tenant_workflow_schedule",
        ),
        IndexModel(
            [("next_fire_at", ASCENDING), ("is_active", ASCENDING)],
            name="idx_next_fire_active",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("is_active", ASCENDING)],
            name="idx_tenant_active_schedules",
        ),
    ],

    # ── chat_sessions ─────────────────────────────────────────────────────────
    "chat_sessions": [
        IndexModel(
            [("tenant_id", ASCENDING), ("session_id", ASCENDING)],
            unique=True,
            name="idx_tenant_session_unique",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("updated_at", DESCENDING)],
            name="idx_tenant_sessions_updated",
        ),
        IndexModel(
            [("tenant_id", ASCENDING), ("user_id", ASCENDING), ("updated_at", DESCENDING)],
            name="idx_tenant_user_sessions",
        ),
        # TTL index — auto-delete sessions after 30 days of inactivity
        IndexModel(
            [("updated_at", ASCENDING)],
            expireAfterSeconds=2_592_000,  # 30 days
            name="idx_chat_sessions_ttl",
        ),
    ],

}


# ─────────────────────────────────────────────────────────────────────────────
# Document Schemas (validation — MongoDB JSON Schema)
# ─────────────────────────────────────────────────────────────────────────────

COLLECTION_SCHEMAS: dict[str, dict] = {

    "workflows": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["tenant_id", "workflow_id", "definition", "metadata"],
            "properties": {
                "tenant_id":   {"bsonType": "string"},
                "workflow_id": {"bsonType": "string"},
                "definition":  {"bsonType": "object"},
                "metadata": {
                    "bsonType": "object",
                    "required": ["name"],
                    "properties": {
                        "name":       {"bsonType": "string"},
                        "is_active":  {"bsonType": "bool"},
                        "created_at": {"bsonType": "date"},
                        "updated_at": {"bsonType": "date"},
                        "created_by": {"bsonType": "string"},
                        "updated_by": {"bsonType": "string"},
                    },
                },
            },
        },
    },

    "execution_runs": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["tenant_id", "run_id", "workflow_id", "status", "started_at"],
            "properties": {
                "tenant_id":   {"bsonType": "string"},
                "run_id":      {"bsonType": "string"},
                "workflow_id": {"bsonType": "string"},
                "status": {
                    "bsonType": "string",
                    "enum": ["QUEUED", "RUNNING", "SUCCESS", "FAILED",
                             "CANCELLED", "WAITING_HUMAN"],
                },
                "started_at":          {"bsonType": "date"},
                "node_states":         {"bsonType": "object"},
                "retention_expires_at":{"bsonType": "date"},
            },
        },
    },

    "chat_sessions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["tenant_id", "session_id", "user_id", "phase", "messages", "created_at"],
            "properties": {
                "tenant_id":  {"bsonType": "string"},
                "session_id": {"bsonType": "string"},
                "user_id":    {"bsonType": "string"},
                "phase": {
                    "bsonType": "string",
                    "enum": ["GATHERING", "CLARIFYING", "FINALIZING", "COMPLETE"],
                },
                "messages":          {"bsonType": "array"},
                "clarification_round": {"bsonType": "int"},
                "created_at":        {"bsonType": "date"},
                "updated_at":        {"bsonType": "date"},
            },
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap runner
# ─────────────────────────────────────────────────────────────────────────────

async def bootstrap_mongodb(mongodb_url: str = MONGODB_URL) -> None:
    """
    Idempotent — safe to run on every deployment.
    Creates collections if they don't exist, applies indexes.
    """
    client = AsyncIOMotorClient(mongodb_url)
    db = client.workflow_platform

    existing = await db.list_collection_names()

    for collection_name, indexes in COLLECTION_INDEXES.items():
        # Create collection if it doesn't exist (with schema validation)
        if collection_name not in existing:
            schema = COLLECTION_SCHEMAS.get(collection_name)
            if schema:
                await db.create_collection(collection_name, validator=schema)
                print(f"  Created collection: {collection_name} (with schema validation)")
            else:
                await db.create_collection(collection_name)
                print(f"  Created collection: {collection_name}")

        # Apply indexes (create_index is idempotent)
        collection = db[collection_name]
        result = await collection.create_indexes(indexes)
        print(f"  Indexes on {collection_name}: {result}")

    client.close()
    print("MongoDB bootstrap complete.")


if __name__ == "__main__":
    asyncio.run(bootstrap_mongodb())
