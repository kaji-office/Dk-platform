"""
CacheKeyBuilder — deterministic, collision-safe cache key generator.

Key structure:
    dk:cache:{tenant_id}:{model}:{param_hash}:{prompt_hash}

Design:
- Stable across restarts (SHA-256 is deterministic)
- Namespace-safe — tenant_id scoped; cross-tenant collisions impossible
- Params normalised: keys sorted before hashing (dict order-independent)
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


class CacheKeyBuilder:
    """
    Builds deterministic Redis/pgvector cache keys.

    Usage:
        builder = CacheKeyBuilder(tenant_id="t-abc", namespace="llm")
        key = builder.build(
            model="gpt-4o",
            prompt="Summarise this document.",
            params={"temperature": 0.2, "max_tokens": 512},
        )
        # → "dk:llm:t-abc:gpt-4o:<param_hash>:<prompt_hash>"
    """

    PREFIX = "dk"

    def __init__(self, tenant_id: str, namespace: str = "cache") -> None:
        self.tenant_id = tenant_id
        self.namespace = namespace

    # ── Public API ────────────────────────────────────────────────────────

    def build(
        self,
        model: str,
        prompt: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """
        Return a deterministic cache key for a given (model, prompt, params) triple.

        Args:
            model:  LLM model identifier, e.g. "gemini-1.5-pro".
            prompt: The exact prompt string.
            params: Optional inference parameters (temperature, max_tokens, ...).
                    Dict key order is normalised before hashing.

        Returns:
            A colon-delimited string key safe for use as a Redis key.
        """
        prompt_hash = self._sha256(prompt)
        param_hash = self._sha256(json.dumps(params or {}, sort_keys=True))
        # Sanitise model name (remove slashes, colons)
        safe_model = model.replace("/", "-").replace(":", "-")
        return f"{self.PREFIX}:{self.namespace}:{self.tenant_id}:{safe_model}:{param_hash}:{prompt_hash}"

    def build_semantic(self, model: str, prompt: str) -> str:
        """
        Shorter key variant used for semantic cache lookups (no params dimension).
        Enables pgvector similarity search by prompt embedding only.
        """
        prompt_hash = self._sha256(prompt)
        safe_model = model.replace("/", "-").replace(":", "-")
        return f"{self.PREFIX}:semantic:{self.tenant_id}:{safe_model}:{prompt_hash}"

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _sha256(text: str) -> str:
        """Return first 16 hex chars of SHA-256 (collision-safe for cache keys)."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
