"""
EngineConfig — injected by consumers at startup.
The SDK never reads environment variables directly.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """
    Configuration for storage backends.
    """
    mongodb_url: str = Field(description="MongoDB connection string")
    postgres_url: str = Field(description="PostgreSQL asyncpg connection string")
    redis_url: str = Field(description="Redis connection string")
    s3_bucket: str = Field(description="S3 bucket name for large outputs")
    aws_region: str = Field(default="us-east-1")


class TenantContextConfig(BaseSettings):
    """
    Per-request tenant context.
    """
    tenant_id: str = Field(description="Current tenant ID")
    pii_policy: str = Field(default="SCAN_MASK")  # SCAN_WARN | SCAN_MASK | SCAN_BLOCK


class LLMProvidersConfig(BaseSettings):
    """
    API keys and settings for LLM providers.
    """
    google_api_key: str | None = Field(default=None)        # Gemini API (AI Studio) — for local dev
    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    vertex_ai_project: str | None = Field(default=None)     # Vertex AI — for staging/prod
    vertex_ai_location: str = Field(default="us-central1")
    bedrock_region: str = Field(default="us-east-1")


class SandboxConfig(BaseSettings):
    """
    Configuration for the code execution sandbox.
    """
    sandbox_timeout_seconds: int = Field(default=30)
    sandbox_max_memory_mb: int = Field(default=512)
    sandbox_max_iterations: int = Field(default=10_000)
    sandbox_tier1_timeout_seconds: int = Field(default=2)


class EngineConfig(BaseSettings):
    """
    Root configuration object for the workflow engine SDK.
    """
    storage: StorageConfig
    tenant: TenantContextConfig
    providers: LLMProvidersConfig
    sandbox: SandboxConfig

    context_inline_threshold_kb: int = Field(default=64)
    context_redis_ttl_seconds: int = Field(default=86_400)
    provider_rate_limit_window_seconds: int = Field(default=60)
    semantic_cache_similarity_threshold: float = Field(default=0.92)
    semantic_cache_enabled: bool = Field(default=True)
    platform_margin_percent: float = Field(default=20.0)

    model_config = {"extra": "ignore"}
