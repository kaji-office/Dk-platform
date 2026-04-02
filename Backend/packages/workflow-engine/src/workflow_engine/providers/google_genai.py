from __future__ import annotations

import asyncio
from typing import Any

from google import genai
from google.genai import types

from workflow_engine.ports import LLMPort


class GoogleGenAIProvider(LLMPort):
    """
    Google GenAI SDK provider — supports both Gemini API and Vertex AI.

    Gemini API (local dev):
        GoogleGenAIProvider(api_key="AIza...")

    Vertex AI (staging/prod):
        GoogleGenAIProvider(vertexai=True, project="my-project", location="us-central1")
        Requires ADC: GOOGLE_APPLICATION_CREDENTIALS or `gcloud auth application-default login`.
    """

    def __init__(
        self,
        api_key: str | None = None,
        vertexai: bool = False,
        project: str | None = None,
        location: str = "us-central1",
        model: str = "gemini-2.0-flash",
    ) -> None:
        self.model = model

        if vertexai:
            self.client = genai.Client(vertexai=True, project=project, location=location)
        elif api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            # Falls back to GOOGLE_API_KEY environment variable if set
            self.client = genai.Client()

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        def _generate() -> str:
            response = self.client.models.generate_content(
                model=kwargs.get("model", self.model),
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=kwargs.get("temperature", 0.0),
                ),
            )
            return response.text

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _generate)

    async def complete_with_usage(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """
        Generate a completion using Google GenAI with native token counting.

        Uses response.usage_metadata for output token counts and
        client.models.count_tokens() for input token counts (native API, no estimation).
        """
        model_id = kwargs.get("model", self.model)

        def _generate() -> dict[str, Any]:
            response = self.client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=kwargs.get("temperature", 0.0),
                ),
            )
            usage = response.usage_metadata
            return {
                "text": response.text,
                "input_tokens": usage.prompt_token_count or 0,
                "output_tokens": usage.candidates_token_count or 0,
                "thoughts_tokens": getattr(usage, "thoughts_token_count", None) or 0,
            }

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _generate)

    def count_tokens(self, content: str, model_id: str | None = None) -> int:
        """
        Count tokens for a prompt without generating a completion.
        Uses Google GenAI native count_tokens() API — no tiktoken estimation.
        """
        try:
            return self.client.models.count_tokens(
                model=model_id or self.model, contents=content
            ).total_tokens
        except Exception:
            return 0

    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        def _embed() -> list[float]:
            response = self.client.models.embed_content(
                model=kwargs.get("model", "text-embedding-004"),
                contents=text,
            )
            return response.embeddings[0].values

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _embed)
