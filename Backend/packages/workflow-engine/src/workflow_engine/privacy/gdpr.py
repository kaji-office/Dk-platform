"""
GDPR Right to Erasure and Data Export workflows.

Implements D-4 acceptance criteria:
- delete_user_data: purges PII across MongoDB + PostgreSQL + S3
- export_user_data: GDPR data portability export
"""
from typing import Any
import logging

from workflow_engine.storage.postgres.tenant_repo import PostgresTenantRepository
from workflow_engine.storage.postgres.user_repo import PostgresUserRepository
from workflow_engine.storage.mongo.execution_repo import MongoExecutionRepository
from workflow_engine.storage.mongo.workflow_repo import MongoWorkflowRepository

logger = logging.getLogger("dk.privacy.gdpr")


class GDPRHandler:
    """Provides methods for wiping and exporting customer data upon request."""

    def __init__(
        self,
        tenant_repo: PostgresTenantRepository,
        user_repo: PostgresUserRepository,
        execution_repo: MongoExecutionRepository,
        workflow_repo: MongoWorkflowRepository,
        s3_storage: Any = None,  # Optional[S3StorageService]
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._execution_repo = execution_repo
        self._workflow_repo = workflow_repo
        self._s3_storage = s3_storage

    async def delete_user_data(self, user_id: str, tenant_id: str) -> dict[str, Any]:
        """
        GDPR 'Right to Erasure' — wipes all PII for a specific user across all stores.

        Purges:
        1. MongoDB: execution logs and workflow definitions linked to user
        2. PostgreSQL: user record (cascades to billing, API keys, etc.)
        3. S3: any uploaded artifacts under tenant_id/user_id/ path
        """
        try:
            results: dict[str, Any] = {"user_id": user_id, "tenant_id": tenant_id}

            # 1. MongoDB - wipe execution and workflow records for this user
            exec_result = await self._execution_repo._collection.delete_many(
                {"tenant_id": tenant_id, "triggered_by": user_id}
            )
            wf_result = await self._workflow_repo._collection.delete_many(
                {"tenant_id": tenant_id, "created_by": user_id}
            )
            results["mongo"] = {
                "executions_deleted": exec_result.deleted_count,
                "workflows_deleted": wf_result.deleted_count,
            }

            # 2. S3 - delete all files under tenant/user prefix
            if self._s3_storage:
                s3_prefix = f"{tenant_id}/{user_id}/"
                await self._s3_storage.delete_prefix(s3_prefix)
                results["s3"] = {"prefix_deleted": s3_prefix}
            else:
                results["s3"] = {"skipped": "no S3 storage configured"}

            # 3. PostgreSQL - remove user record (triggers FK cascades)
            await self._user_repo.delete(user_id)
            results["postgres"] = {"user_deleted": True}

            logger.warning(
                f"GDPR data deletion completed for user={user_id} tenant={tenant_id}"
            )
            return {"status": "success", **results}

        except Exception as e:
            logger.error(f"GDPR deletion failed for user={user_id}: {e}")
            raise

    async def export_user_data(self, user_id: str, tenant_id: str) -> dict[str, Any]:
        """
        GDPR 'Right of Access' — exports all data held for a specific user.

        Returns structured dict with all data across stores for portability.
        """
        try:
            export: dict[str, Any] = {"user_id": user_id, "tenant_id": tenant_id}

            # MongoDB: collect execution and workflow records
            executions = []
            async for doc in self._execution_repo._collection.find(
                {"tenant_id": tenant_id, "triggered_by": user_id},
                {"_id": 0}
            ):
                executions.append(doc)

            workflows = []
            async for doc in self._workflow_repo._collection.find(
                {"tenant_id": tenant_id, "created_by": user_id},
                {"_id": 0}
            ):
                workflows.append(doc)

            export["executions"] = executions
            export["workflows"] = workflows

            # PostgreSQL: fetch user profile
            user = await self._user_repo.get_by_id(user_id)
            export["user_profile"] = user.model_dump() if user else None

            logger.info(f"GDPR data export completed for user={user_id}")
            return {"status": "success", **export}

        except Exception as e:
            logger.error(f"GDPR export failed for user={user_id}: {e}")
            raise

    async def erase_tenant_data(self, tenant_id: str) -> dict[str, Any]:
        """
        Execute Right to Erasure for an entire Tenant.
        Wipes all workflows, execution logs, and S3 artifacts.
        """
        try:
            await self._workflow_repo._collection.delete_many({"tenant_id": tenant_id})
            await self._execution_repo._collection.delete_many({"tenant_id": tenant_id})

            if self._s3_storage:
                await self._s3_storage.delete_prefix(f"{tenant_id}/")

            logger.warning(f"GDPR Erasure completed for tenant {tenant_id}")
            return {"status": "success", "tenant_id": tenant_id, "erased": True}
        except Exception as e:
            logger.error(f"Failed to erase data for tenant {tenant_id}: {e}")
            raise
