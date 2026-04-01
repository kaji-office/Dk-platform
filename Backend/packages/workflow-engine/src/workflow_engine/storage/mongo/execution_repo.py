"""
MongoDB Implementation for ExecutionRepository.

Stores ExecutionRun documents with complex nested `node_states`.
Includes specialized `$set` atomic updates for individual node statuses.
"""
from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from workflow_engine.models import ExecutionRun
from workflow_engine.ports import ExecutionRepository


class MongoExecutionRepository(ExecutionRepository):
    """
    MongoDB backed ExecutionRun repository.
    
    Args:
        db: The connected AsyncIOMotorDatabase instance.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db["execution_runs"]

    async def get(self, tenant_id: str, run_id: str) -> ExecutionRun | None:
        """Fetch a specific execution run."""
        doc = await self._collection.find_one({"tenant_id": tenant_id, "run_id": run_id})
        if not doc:
            return None
            
        doc.pop("_id", None)
        return ExecutionRun.model_validate(doc)

    async def create(self, tenant_id: str, execution: ExecutionRun) -> ExecutionRun:
        """Insert a new pending or queued execution run."""
        data = execution.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        
        try:
            await self._collection.insert_one(data)
        except DuplicateKeyError as exc:
            raise ValueError(f"Run ID '{execution.run_id}' conflict.") from exc
            
        return execution

    async def update_state(self, tenant_id: str, run_id: str, execution: ExecutionRun) -> ExecutionRun:
        """
        Replace the entire execution document.
        In production, a finer-grained `$set` operator method could be used,
        but `ExecutionEngine` state machine design passes the entire modified Run.
        """
        data = execution.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        
        await self._collection.replace_one(
            {"tenant_id": tenant_id, "run_id": run_id},
            data,
            upsert=False
        )
        return execution

    async def list(
        self, tenant_id: str, workflow_id: str | None = None, skip: int = 0, limit: int = 100
    ) -> list[ExecutionRun]:
        """List past runs, optionally filtered by workflow ID."""
        filter_doc: dict[str, Any] = {"tenant_id": tenant_id}
        if workflow_id:
            filter_doc["workflow_id"] = workflow_id

        cursor = self._collection.find(filter_doc)\
            .sort("started_at", -1)\
            .skip(skip)\
            .limit(limit)

        runs = []
        async for doc in cursor:
            doc.pop("_id", None)
            runs.append(ExecutionRun.model_validate(doc))

        return runs

    async def get_node_states(self, tenant_id: str, run_id: str) -> list[dict[str, Any]]:
        """Return the node_states list from a specific run document."""
        doc = await self._collection.find_one(
            {"tenant_id": tenant_id, "run_id": run_id},
            {"node_states": 1, "_id": 0},
        )
        if not doc:
            return []
        return doc.get("node_states", [])

    async def list_runs_by_tenant(
        self, tenant_id: str, skip: int = 0, limit: int = 50
    ) -> list[ExecutionRun]:
        """List all runs for a tenant, newest first."""
        cursor = self._collection.find({"tenant_id": tenant_id})\
            .sort("started_at", -1)\
            .skip(skip)\
            .limit(limit)

        runs = []
        async for doc in cursor:
            doc.pop("_id", None)
            runs.append(ExecutionRun.model_validate(doc))
        return runs
