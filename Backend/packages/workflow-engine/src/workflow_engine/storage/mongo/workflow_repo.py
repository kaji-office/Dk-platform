"""
MongoDB Implementation for WorkflowRepository.

Stores WorkflowDefinition documents.
Enforces tenant isolation by injecting `{"tenant_id": tenant_id}` into every query.
Index strategy: Unique compound index on (tenant_id, id).
"""
from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from workflow_engine.errors import WorkflowNotFoundError
from workflow_engine.models import WorkflowDefinition
from workflow_engine.ports import WorkflowRepository


class MongoWorkflowRepository(WorkflowRepository):
    """
    MongoDB backed Workflow definition repository.
    
    Args:
        db: The connected AsyncIOMotorDatabase instance.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db["workflow_definitions"]

    async def get(self, tenant_id: str, workflow_id: str) -> WorkflowDefinition | None:
        """Fetch a workflow by ID, ensuring it belongs to the tenant."""
        doc = await self._collection.find_one({"tenant_id": tenant_id, "id": workflow_id})
        if not doc:
            return None
            
        doc.pop("_id", None)
        # Reconstruct Pydantic model
        return WorkflowDefinition.model_validate(doc)

    async def create(self, tenant_id: str, workflow: WorkflowDefinition) -> WorkflowDefinition:
        """Insert a new workflow definition."""
        data = workflow.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        
        try:
            await self._collection.insert_one(data)
        except DuplicateKeyError as exc:
            raise ValueError(f"Workflow '{workflow.id}' already exists.") from exc
            
        return workflow

    async def update(self, tenant_id: str, workflow_id: str, workflow: WorkflowDefinition) -> WorkflowDefinition:
        """Fully replace an existing workflow definition."""
        if workflow.id != workflow_id:
            raise ValueError("Workflow ID in body does not match path ID")
            
        data = workflow.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        
        result = await self._collection.replace_one(
            {"tenant_id": tenant_id, "id": workflow_id},
            data
        )
        
        if result.matched_count == 0:
            raise WorkflowNotFoundError(workflow_id)
            
        return workflow

    async def delete(self, tenant_id: str, workflow_id: str) -> bool:
        """Delete a workflow definition."""
        result = await self._collection.delete_one({"tenant_id": tenant_id, "id": workflow_id})
        return result.deleted_count > 0

    async def list(self, tenant_id: str, skip: int = 0, limit: int = 100) -> list[WorkflowDefinition]:
        """List workflows scoped to tenant."""
        cursor = self._collection.find({"tenant_id": tenant_id}).skip(skip).limit(limit)
        
        workflows = []
        async for doc in cursor:
            doc.pop("_id", None)
            workflows.append(WorkflowDefinition.model_validate(doc))
            
        return workflows
