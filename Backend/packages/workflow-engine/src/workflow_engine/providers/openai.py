from typing import Any
import openai
from workflow_engine.ports import LLMPort

class OpenAIProvider(LLMPort):
    """
    OpenAI provider wrapper.
    """
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o"):
        self.api_key = api_key
        self.client = openai.AsyncOpenAI(api_key=api_key) if api_key else openai.AsyncOpenAI()
        self.model = model

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        response = await self.client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.0),
        )
        return response.choices[0].message.content or ""

    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        response = await self.client.embeddings.create(
            model=kwargs.get("model", "text-embedding-3-small"),
            input=text
        )
        return response.data[0].embedding
