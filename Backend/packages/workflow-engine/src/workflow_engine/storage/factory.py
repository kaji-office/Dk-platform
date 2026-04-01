"""
RepositoryFactory — centralizing the instantiation of storage backends.

Constructs connection pools to Postgres and Motor async client for MongoDB.
"""
from __future__ import annotations

from dataclasses import dataclass

import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient

from workflow_engine.config import EngineConfig

from workflow_engine.storage.mongo.workflow_repo import MongoWorkflowRepository
from workflow_engine.storage.mongo.execution_repo import MongoExecutionRepository
from workflow_engine.storage.mongo.schedule_repo import MongoScheduleRepository
from workflow_engine.storage.mongo.conversation_repo import MongoConversationRepository

from workflow_engine.storage.postgres.user_repo import PostgresUserRepository
from workflow_engine.storage.postgres.tenant_repo import PostgresTenantRepository
from workflow_engine.storage.postgres.billing_repo import PostgresBillingRepository

from workflow_engine.storage.s3_storage import S3StorageService


@dataclass
class RepositoryBundle:
    """Contains initialized repository instances for injection into services."""
    workflows: MongoWorkflowRepository
    executions: MongoExecutionRepository
    schedules: MongoScheduleRepository
    users: PostgresUserRepository
    tenants: PostgresTenantRepository
    billing: PostgresBillingRepository
    storage: S3StorageService
    chat_sessions: MongoConversationRepository


class RepositoryFactory:
    """Factory builder for initialized Repository bundles."""

    @staticmethod
    async def create_all(config: EngineConfig) -> RepositoryBundle:
        """
        Creates connection pools and return all initialized storage ports.
        Must be called recursively from an async context (FastAPI lifespan, Celery worker init).
        """
        # MongoDB Client - singleton behavior in motor
        mongo_client: AsyncIOMotorClient = AsyncIOMotorClient(config.mongodb_url)
        # Parse db name from DSN, or default to dk_platform
        db_name = mongo_client.get_database().name or "dk_platform"
        mongo_db = mongo_client[db_name]

        # PostgreSQL Pool
        pg_pool = await asyncpg.create_pool(dsn=config.postgres_url, min_size=1, max_size=5)
        if not pg_pool:
            raise RuntimeError("Failed to initialize PostgreSQL pool")

        # Create components
        return RepositoryBundle(
            workflows=MongoWorkflowRepository(mongo_db),
            executions=MongoExecutionRepository(mongo_db),
            schedules=MongoScheduleRepository(mongo_db),
            users=PostgresUserRepository(pg_pool),
            tenants=PostgresTenantRepository(pg_pool),
            billing=PostgresBillingRepository(pg_pool),
            storage=S3StorageService(bucket_name=config.s3_bucket, region_name=config.aws_region),
            chat_sessions=MongoConversationRepository(mongo_db),
        )
