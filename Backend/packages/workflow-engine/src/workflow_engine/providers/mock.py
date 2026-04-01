from typing import Any
from workflow_engine.ports import LLMPort

class MockLLMProvider(LLMPort):
    """
    Deterministic mock provider for unit tests.
    """
    async def complete(self, prompt: str, **kwargs: Any) -> str:
        return f"[MOCK] Response to: {prompt[:80]}"
        
    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        return [0.1] * 1536
