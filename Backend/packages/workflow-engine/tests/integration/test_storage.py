import asyncio
import pytest
from testcontainers.mongodb import MongoDbContainer
from testcontainers.postgres import PostgresContainer
import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient

from workflow_engine.storage.postgres.tenant_repo import PostgresTenantRepository
from workflow_engine.storage.mongo.execution_repo import MongoExecutionRepository
from workflow_engine.models.tenant import TenantConfig, PlanTier
from workflow_engine.models.execution import ExecutionRun, RunStatus

@pytest.fixture(scope="module")
def mongo_container():
    with MongoDbContainer("mongo:6.0") as mongo:
        yield mongo

@pytest.fixture(scope="module")
def postgres_container():
    with PostgresContainer("postgres:15-alpine") as postgres:
        yield postgres

@pytest.fixture
async def asyncpg_pool(postgres_container):
    conn_str = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql")
    pool = await asyncpg.create_pool(conn_str)
    
    # Initialize basic schema for testing
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                plan_tier VARCHAR NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                api_keys JSONB DEFAULT '{}',
                integration_credentials JSONB DEFAULT '{}',
                quotas JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    yield pool
    await pool.close()

@pytest.fixture
def motor_db(mongo_container):
    client = AsyncIOMotorClient(mongo_container.get_connection_url())
    return client.get_database("test_db")

@pytest.mark.asyncio
async def test_postgres_tenant_crud(asyncpg_pool):
    repo = PostgresTenantRepository(asyncpg_pool)
    
    # Create tenant should be mocked here if `create` doesn't exist, but we insert directly for now
    async with asyncpg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO tenants (tenant_id, name, plan_tier) VALUES ($1, $2, $3)",
            "tenant-1", "Test Tenant", "STARTER"
        )
        
    tenant = await repo.get("tenant-1")
    assert tenant is not None
    assert tenant.tenant_id == "tenant-1"
    assert tenant.plan_tier == PlanTier.STARTER

@pytest.mark.asyncio
async def test_mongo_execution_crud(motor_db):
    repo = MongoExecutionRepository(motor_db)
    
    # Create
    run_id = await repo.create("tenant-1", "wf-1", {"trigger": "manual"})
    assert run_id is not None
    
    # Get
    run = await repo.get("tenant-1", run_id)
    assert run is not None
    assert run.run_id == run_id
    assert run.status == RunStatus.PENDING
    
    # Update State
    run.status = RunStatus.RUNNING
    await repo.update_state("tenant-1", run_id, run)
    
    updated_run = await repo.get("tenant-1", run_id)
    assert updated_run.status == RunStatus.RUNNING
    
    # List
    runs = await repo.list("tenant-1")
    assert len(runs) == 1
    assert runs[0].run_id == run_id
