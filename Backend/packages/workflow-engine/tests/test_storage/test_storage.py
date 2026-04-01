import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from workflow_engine.models import (
    WorkflowDefinition,
    ExecutionRun,
    RunStatus,
    ScheduleModel,
    UserModel,
    TenantConfig,
    PlanTier,
)
from workflow_engine.errors import WorkflowNotFoundError

from workflow_engine.storage.mongo.workflow_repo import MongoWorkflowRepository
from workflow_engine.storage.mongo.execution_repo import MongoExecutionRepository
from workflow_engine.storage.mongo.schedule_repo import MongoScheduleRepository
from workflow_engine.storage.postgres.user_repo import PostgresUserRepository
from workflow_engine.storage.postgres.tenant_repo import PostgresTenantRepository
from workflow_engine.storage.postgres.billing_repo import PostgresBillingRepository
from workflow_engine.storage.s3_storage import S3StorageService

# --- MOCKS ---

class MockCollection(AsyncMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class MockDatabase(dict):
    def __init__(self):
        super().__init__()
        self.collections = {}

    def __getitem__(self, key):
        if key not in self.collections:
            self.collections[key] = MockCollection()
        return self.collections[key]

class MockPool(AsyncMock):
    pass


# --- MONGO REPOSITORIES ---

@pytest.mark.asyncio
async def test_mongo_workflow_create():
    db = MockDatabase()
    repo = MongoWorkflowRepository(db)
    
    wf = WorkflowDefinition(id="w1", nodes={}, edges=[])
    db["workflow_definitions"].insert_one.return_value = AsyncMock()
    
    res = await repo.create("t1", wf)
    assert res.id == "w1"
    
    db["workflow_definitions"].insert_one.assert_called_once()
    args, kwargs = db["workflow_definitions"].insert_one.call_args
    inserted_doc = args[0]
    
    assert inserted_doc["id"] == "w1"
    assert inserted_doc["tenant_id"] == "t1" # Crucial tenant isolation check

@pytest.mark.asyncio
async def test_mongo_workflow_get():
    db = MockDatabase()
    repo = MongoWorkflowRepository(db)
    
    db["workflow_definitions"].find_one.return_value = {
        "_id": "ignoreme",
        "id": "w1",
        "tenant_id": "t1",
        "nodes": {},
        "edges": []
    }
    
    wf = await repo.get("t1", "w1")
    assert wf.id == "w1"
    
    db["workflow_definitions"].find_one.assert_called_once_with({"tenant_id": "t1", "id": "w1"})

@pytest.mark.asyncio
async def test_mongo_execution_update():
    db = MockDatabase()
    repo = MongoExecutionRepository(db)
    
    run = ExecutionRun(run_id="r1", workflow_id="w1", tenant_id="t1", status=RunStatus.RUNNING)
    db["execution_runs"].replace_one.return_value = AsyncMock()
    
    await repo.update_state("t1", "r1", run)
    
    db["execution_runs"].replace_one.assert_called_once()
    args, kwargs = db["execution_runs"].replace_one.call_args
    query = args[0]
    doc = args[1]
    
    assert query == {"tenant_id": "t1", "run_id": "r1"}
    assert doc["tenant_id"] == "t1"
    assert doc["status"] == "RUNNING"

@pytest.mark.asyncio
async def test_mongo_schedule_get_due():
    db = MockDatabase()
    repo = MongoScheduleRepository(db)
    
    # Mocking cursor async for loop is tricky, let's substitute find return
    class MockCursor:
        def __init__(self, *args, **kwargs):
            self.query = args[0] if args else {}
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not getattr(self, "done", False):
                self.done = True
                return {
                    "schedule_id": "s1",
                    "workflow_id": "w1",
                    "tenant_id": "t1",
                    "cron_expression": "* * * * *",
                    "next_fire_at": 1000.0,
                    "is_active": True
                }
            raise StopAsyncIteration
    
    db["schedules"].find = lambda *a, **kw: MockCursor(*a, **kw)
    
    due = await repo.get_due_schedules(1005.0)
    
    assert len(due) == 1
    assert due[0].schedule_id == "s1"
    
    # We can't use assert_called_once() on the lambda, but the assert len(due) validates the loop ran


# --- POSTGRES REPOSITORIES ---

@pytest.mark.asyncio
async def test_postgres_user_get():
    pool = MockPool()
    repo = PostgresUserRepository(pool)
    
    pool.fetchrow.return_value = {
        "id": "u1",
        "email": "test@test.com",
        "role": "VIEWER",
        "mfa_enabled": False
    }
    
    u = await repo.get("u1")
    assert u.id == "u1"
    assert u.role == "VIEWER"
    assert u.email == "test@test.com"
    
    pool.fetchrow.assert_called_once()
    query = pool.fetchrow.call_args[0][0]
    assert "WHERE id = $1" in query

@pytest.mark.asyncio
async def test_postgres_tenant_update():
    pool = MockPool()
    repo = PostgresTenantRepository(pool)
    
    tc = TenantConfig(tenant_id="t1", plan_tier=PlanTier.PRO)
    
    await repo.update("t1", tc)
    
    pool.execute.assert_called_once()
    query = pool.execute.call_args[0][0]
    args = pool.execute.call_args[0][1:]
    
    assert "UPDATE tenants SET config_json =" in query
    assert args[1] == "t1"
    assert "PRO" in args[0] # The json string


@pytest.mark.asyncio
async def test_postgres_billing_record():
    pool = MockPool()
    repo = PostgresBillingRepository(pool)
    
    await repo.record_llm_tokens("t1", "r1", "gemini-pro", 100, 200, 0.05)
    
    pool.execute.assert_called_once()
    query = pool.execute.call_args[0][0]
    
    assert "INSERT INTO llm_cost_records" in query
    args = pool.execute.call_args[0][1:]
    assert args == ("t1", "r1", "gemini-pro", 100, 200, 0.05)


# --- S3 STORAGE ---

@pytest.mark.asyncio
async def test_s3_upload(monkeypatch):
    class MockS3Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def put_object(self, *args, **kwargs): pass
        async def generate_presigned_url(self, *args, **kwargs): return "http://presigned"
    
    class MockSession:
        def client(self, *args, **kwargs): return MockS3Client()
        
    s3 = S3StorageService("my-bucket")
    
    # Patch session inside s3
    monkeypatch.setattr(s3, "_session", MockSession())
    
    uri = await s3.upload("tenant-123", "folder/file.txt", b"hello")
    # Must enforce tenant isolation prefix
    assert uri == "s3://my-bucket/tenant-123/folder/file.txt"
    
    presigned = await s3.presign_url("tenant-123", "folder/file.txt")
    assert presigned == "http://presigned"

@pytest.mark.asyncio
async def test_s3_tenant_isolation_download(monkeypatch):
    class MockS3Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get_object(self, Bucket, Key):
            # Intercept key for assertion
            self.last_key = Key
            mock_body = AsyncMock()
            mock_body.read.return_value = b"success"
            return {"Body": mock_body}
            
    s3_client_instance = MockS3Client()
    
    class MockSession:
        def client(self, *args, **kwargs): return s3_client_instance

    s3 = S3StorageService("test-bucket")
    monkeypatch.setattr(s3, "_session", MockSession())
    
    # Try an attempt to escape the tenant scope globally
    await s3.download("t-isolated", "t-other/top-secret.pdf")
    # The SDK must force prefixing `t-isolated/` causing the malicious request to fail securely
    assert s3_client_instance.last_key == "t-isolated/t-other/top-secret.pdf"
