from __future__ import annotations

import abc
import builtins
from typing import Any, TYPE_CHECKING

from .models import ExecutionRun, ScheduleModel, TenantConfig, UserModel, WorkflowDefinition

if TYPE_CHECKING:
    from .chat.models import ChatSession, ChatMessage, RequirementSpec, ConversationPhase

class WorkflowRepository(abc.ABC):
    @abc.abstractmethod
    async def get(self, tenant_id: str, workflow_id: str) -> WorkflowDefinition | None:
        pass

    @abc.abstractmethod
    async def create(self, tenant_id: str, workflow: WorkflowDefinition) -> WorkflowDefinition:
        pass

    @abc.abstractmethod
    async def update(self, tenant_id: str, workflow_id: str, workflow: WorkflowDefinition) -> WorkflowDefinition:
        pass

    @abc.abstractmethod
    async def delete(self, tenant_id: str, workflow_id: str) -> bool:
        pass

    @abc.abstractmethod
    async def list(self, tenant_id: str, skip: int = 0, limit: int = 100) -> list[WorkflowDefinition]:
        pass

class ExecutionRepository(abc.ABC):
    @abc.abstractmethod
    async def get(self, tenant_id: str, run_id: str) -> ExecutionRun | None:
        pass

    @abc.abstractmethod
    async def create(self, tenant_id: str, execution: ExecutionRun) -> ExecutionRun:
        pass

    @abc.abstractmethod
    async def update_state(self, tenant_id: str, run_id: str, execution: ExecutionRun) -> ExecutionRun:
        pass

    @abc.abstractmethod
    async def list(self, tenant_id: str, workflow_id: str | None = None, skip: int = 0, limit: int = 100) -> builtins.list["ExecutionRun"]:
        pass

    @abc.abstractmethod
    async def get_node_states(self, tenant_id: str, run_id: str) -> builtins.list[dict[str, Any]]:
        pass

    @abc.abstractmethod
    async def list_runs_by_tenant(self, tenant_id: str, skip: int = 0, limit: int = 50) -> builtins.list["ExecutionRun"]:
        pass

class UserRepository(abc.ABC):
    @abc.abstractmethod
    async def get(self, user_id: str) -> UserModel | None:
        pass

    @abc.abstractmethod
    async def get_by_email(self, email: str) -> UserModel | None:
        pass

    @abc.abstractmethod
    async def create_user(self, tenant_id: str, user_data: dict[str, Any]) -> UserModel:
        pass

    @abc.abstractmethod
    async def update_user(self, tenant_id: str, user_id: str, payload: dict[str, Any]) -> UserModel:
        pass

    @abc.abstractmethod
    async def list_users(self, tenant_id: str, skip: int = 0, limit: int = 50) -> list["UserModel"]:
        pass

class TenantRepository(abc.ABC):
    @abc.abstractmethod
    async def get(self, tenant_id: str) -> TenantConfig | None:
        pass

class ScheduleRepository(abc.ABC):
    @abc.abstractmethod
    async def get(self, tenant_id: str, schedule_id: str) -> ScheduleModel | None:
        pass

    @abc.abstractmethod
    async def create(self, tenant_id: str, schedule: ScheduleModel) -> ScheduleModel:
        pass

    @abc.abstractmethod
    async def update(self, tenant_id: str, schedule_id: str, schedule: ScheduleModel) -> ScheduleModel:
        pass

    @abc.abstractmethod
    async def get_due_schedules(self, timestamp: float) -> list[ScheduleModel]:
        pass

class CachePort(abc.ABC):
    @abc.abstractmethod
    async def get(self, key: str) -> str | None:
        pass

    @abc.abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        pass

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        pass

    async def smembers(self, key: str) -> set[str]:
        """Return all members of a Redis set. Default: empty set (non-Redis caches)."""
        return set()

    async def sadd(self, key: str, *members: str, ttl_seconds: int | None = None) -> None:
        """Add members to a Redis set. Default: no-op (non-Redis caches)."""
        pass

class StoragePort(abc.ABC):
    @abc.abstractmethod
    async def upload(self, tenant_id: str, path: str, data: bytes) -> str:
        """Upload data and return standard URI"""
        pass

    @abc.abstractmethod
    async def download(self, tenant_id: str, path: str) -> bytes:
        pass

    @abc.abstractmethod
    async def presign_url(self, tenant_id: str, path: str, expires_in: int = 3600) -> str:
        pass

class NotificationPort(abc.ABC):
    @abc.abstractmethod
    async def send(self, tenant_id: str, channel: str, message: str, **kwargs: Any) -> bool:
        pass

class LLMPort(abc.ABC):
    @abc.abstractmethod
    async def complete(self, prompt: str, **kwargs: Any) -> str:
        pass

    @abc.abstractmethod
    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        pass

    async def complete_with_usage(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """
        Return completion with native token usage metadata.

        Returns:
            {
                "text": str,           — the completion text
                "input_tokens": int,   — prompt token count
                "output_tokens": int,  — completion token count
                "thoughts_tokens": int — reasoning/thought tokens (Gemini only, 0 otherwise)
            }

        Default implementation wraps complete() with zero token counts.
        Override in concrete providers for native counting.
        """
        text = await self.complete(prompt, **kwargs)
        return {"text": text, "input_tokens": 0, "output_tokens": 0, "thoughts_tokens": 0}


class BillingRepository(abc.ABC):
    """Port ABC for billing data access — QuotaChecker depends on this, not the Postgres impl."""

    @abc.abstractmethod
    async def get_monthly_run_count(self, tenant_id: str, year: int, month: int) -> int:
        """Return the number of workflow runs for a tenant in a given month."""
        pass

    @abc.abstractmethod
    async def record_usage(
        self,
        tenant_id: str,
        run_id: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> None:
        """Persist a usage record for billing aggregation."""
        pass

    @abc.abstractmethod
    async def get_usage_summary(self, tenant_id: str, year: int, month: int) -> dict[str, Any]:
        """Return aggregated usage totals for a tenant/period."""
        pass

class ConversationRepository(abc.ABC):
    @abc.abstractmethod
    async def create_session(self, tenant_id: str, user_id: str) -> "ChatSession":
        pass

    @abc.abstractmethod
    async def get_session(self, session_id: str, tenant_id: str) -> "ChatSession | None":
        pass

    @abc.abstractmethod
    async def append_message(self, session_id: str, message: "ChatMessage") -> None:
        pass

    @abc.abstractmethod
    async def update_spec(self, session_id: str, spec: "RequirementSpec") -> None:
        pass

    @abc.abstractmethod
    async def update_phase(self, session_id: str, phase: "ConversationPhase") -> None:
        pass

    @abc.abstractmethod
    async def list_sessions(self, tenant_id: str) -> list["ChatSession"]:
        pass

    @abc.abstractmethod
    async def record_workflow_id(self, session_id: str, workflow_id: str) -> None:
        pass
