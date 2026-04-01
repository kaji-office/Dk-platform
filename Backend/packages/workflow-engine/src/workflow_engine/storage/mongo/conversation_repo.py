import uuid
from datetime import datetime, timezone
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from workflow_engine.ports import ConversationRepository
from workflow_engine.chat.models import (
    ChatSession,
    ChatMessage,
    RequirementSpec,
    ConversationPhase,
)

logger = logging.getLogger(__name__)

from typing import Any

class MongoConversationRepository(ConversationRepository):
    def __init__(self, db: AsyncIOMotorDatabase[Any]):
        self.db = db
        self.collection = db["conversations"]

    async def initialize_indexes(self) -> None:
        """Create tenant indexes and TTL index on updated_at."""
        await self.collection.create_index([("tenant_id", 1), ("session_id", 1)], unique=True)
        # 30 days TTL on updated_at
        await self.collection.create_index("updated_at", expireAfterSeconds=30 * 24 * 60 * 60)

    async def create_session(self, tenant_id: str, user_id: str) -> ChatSession:
        session_id = f"cs_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        
        session = ChatSession(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            phase=ConversationPhase.GATHERING,
            messages=[],
            requirement_spec=None,
            generated_workflow_id=None,
            clarification_round=0,
            created_at=now,
            updated_at=now
        )
        
        doc = session.model_dump()
        await self.collection.insert_one(doc)
        return session

    async def get_session(self, session_id: str, tenant_id: str) -> ChatSession | None:
        doc = await self.collection.find_one({"session_id": session_id, "tenant_id": tenant_id})
        if not doc:
            return None
        return ChatSession(**doc)

    async def append_message(self, session_id: str, message: ChatMessage) -> None:
        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": message.model_dump()},
                "$set": {"updated_at": now}
            }
        )

    async def update_spec(self, session_id: str, spec: RequirementSpec) -> None:
        now = datetime.now(timezone.utc)
        import dataclasses
        await self.collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "requirement_spec": dataclasses.asdict(spec),
                    "updated_at": now
                }
            }
        )

    async def update_phase(self, session_id: str, phase: ConversationPhase) -> None:
        now = datetime.now(timezone.utc)
        update_doc = {
            "phase": phase.value,
            "updated_at": now
        }
        if phase == ConversationPhase.CLARIFYING:
            # Increment clarification round when we enter clarification
            update_doc["$inc"] = {"clarification_round": 1} # type: ignore
            await self.collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {"phase": phase.value, "updated_at": now},
                    "$inc": {"clarification_round": 1}
                }
            )
        else:
            await self.collection.update_one(
                {"session_id": session_id},
                {"$set": update_doc}
            )

    async def list_sessions(self, tenant_id: str) -> list[ChatSession]:
        cursor = self.collection.find({"tenant_id": tenant_id}).sort("updated_at", -1)
        sessions = []
        async for doc in cursor:
            sessions.append(ChatSession(**doc))
        return sessions

    async def record_workflow_id(self, session_id: str, workflow_id: str) -> None:
        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "generated_workflow_id": workflow_id,
                    "updated_at": now
                }
            }
        )
