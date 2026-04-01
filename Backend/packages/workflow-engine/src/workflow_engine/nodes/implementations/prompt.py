"""PromptNode — Jinja2 prompt template → LLM call → semantic cache → token tracking."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from jinja2 import Template

from workflow_engine.errors import WorkflowValidationError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices


def _cache_key(model: str, rendered: str) -> str:
    raw = json.dumps({"model": model, "prompt": rendered}, sort_keys=True)
    return "prompt:" + hashlib.sha256(raw.encode()).hexdigest()


def _count_tokens(text: str) -> int:
    import tiktoken  # lazy import
    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


class PromptNode(BaseNodeType):
    """
    Renders a Jinja2 prompt template, calls LLMPort, applies semantic cache.

    Config:
        provider, model, prompt_template, system_prompt,
        temperature, max_tokens, use_cache
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        if services.llm is None:
            raise WorkflowValidationError("PromptNode requires a configured LLMPort")

        model: str = config.get("model", "gemini-2.0-flash")
        system_prompt: str = config.get("system_prompt", "")
        prompt_template: str = str(config.get("prompt_template", "{{ prompt }}"))
        temperature: float = float(config.get("temperature", 0.7))
        max_tokens: int = int(config.get("max_tokens", 1024))
        use_cache: bool = bool(config.get("use_cache", False))

        rendered_prompt = Template(prompt_template).render(**context.input_data)
        full_prompt = f"{system_prompt}\n\n{rendered_prompt}" if system_prompt else rendered_prompt

        # Cache lookup
        if use_cache and services.cache:
            key = _cache_key(model, full_prompt)
            cached = await services.cache.get(key)
            if cached:
                return NodeOutput(
                    outputs={"text": cached, "tokens_used": 0},
                    metadata={"cached": True},
                )

        response = await services.llm.complete(
            full_prompt, model=model, temperature=temperature, max_tokens=max_tokens
        )
        tokens = _count_tokens(full_prompt) + _count_tokens(response)

        if use_cache and services.cache:
            await services.cache.set(_cache_key(model, full_prompt), response, ttl_seconds=3600)

        return NodeOutput(
            outputs={"text": response, "tokens_used": tokens},
            metadata={"cached": False, "model": model},
        )
