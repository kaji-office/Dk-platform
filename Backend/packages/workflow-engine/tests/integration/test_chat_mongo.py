import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from testcontainers.mongodb import MongoDbContainer

from workflow_engine.storage.mongo.conversation_repo import MongoConversationRepository
from workflow_engine.chat.models import ConversationPhase, ChatMessage

@pytest.fixture(scope="module")
def mongo_container():
    with MongoDbContainer("mongo:6.0") as mongo:
        yield mongo

@pytest.fixture
def motor_db(mongo_container):
    client = AsyncIOMotorClient(mongo_container.get_connection_url())
    return client.get_database("test_chat_db")

@pytest.fixture
def chat_repo(motor_db) -> MongoConversationRepository:
    return MongoConversationRepository(motor_db)

@pytest.mark.asyncio
async def test_mongo_conversation_repo_lifecycle(chat_repo):
    tenant_id = "tenant-xyz"
    user_id = "user-123"
    
    # Create Session
    session = await chat_repo.create_session(tenant_id, user_id)
    assert session.session_id is not None
    assert session.tenant_id == tenant_id
    assert session.phase == ConversationPhase.GATHERING
    
    # Get Session
    fetched = await chat_repo.get_session(session.session_id, tenant_id)
    assert fetched is not None
    assert fetched.session_id == session.session_id
    
    # Append Message
    from datetime import datetime
    msg = ChatMessage(id="m1", role="user", content="Hello, build me a workflow", ts=datetime.now())
    await chat_repo.append_message(session.session_id, tenant_id, msg)
    
    updated = await chat_repo.get_session(session.session_id, tenant_id)
    assert len(updated.messages) == 1
    assert updated.messages[0].content == "Hello, build me a workflow"

    # Update Phase
    await chat_repo.update_phase(session.session_id, tenant_id, ConversationPhase.CLARIFYING)
    updated = await chat_repo.get_session(session.session_id, tenant_id)
    assert updated.phase == ConversationPhase.CLARIFYING

    # Cross-Tenant isolation check
    alien_fetch = await chat_repo.get_session(session.session_id, "other-tenant")
    assert alien_fetch is None
