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

    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        def _embed() -> list[float]:
            response = self.client.models.embed_content(
                model=kwargs.get("model", "text-embedding-004"),
                contents=text,
            )
            return response.embeddings[0].values

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _embed)
