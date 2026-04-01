from enum import StrEnum

from pydantic import BaseModel, Field


class PlanTier(StrEnum):
    FREE = "FREE"
    STARTER = "STARTER"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"

class PIIPolicy(StrEnum):
    SCAN_WARN = "SCAN_WARN"
    SCAN_MASK = "SCAN_MASK"
    SCAN_BLOCK = "SCAN_BLOCK"

class IsolationModel(StrEnum):
    SHARED = "SHARED"
    DEDICATED = "DEDICATED"

class TenantConfig(BaseModel):
    tenant_id: str = Field(...)
    plan_tier: PlanTier = Field(default=PlanTier.FREE)
    isolation_model: IsolationModel = Field(default=IsolationModel.SHARED)
    pii_policy: PIIPolicy = Field(default=PIIPolicy.SCAN_WARN)
    quotas: dict[str, int] = Field(default_factory=dict, description="Generic dictionary for exact quotas")

class UsageRecord(BaseModel):
    run_id: str = Field(...)
    tenant_id: str = Field(...)
    base_execution_charge: float = Field(default=0.0)
    node_charge: float = Field(default=0.0)
    llm_tokens_used: int = Field(default=0)
    compute_seconds: float = Field(default=0.0)
    storage_mb: float = Field(default=0.0)
