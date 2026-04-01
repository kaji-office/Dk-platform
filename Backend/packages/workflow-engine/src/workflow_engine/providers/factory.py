import logging
from .google_genai import GoogleGenAIProvider
from .openai import OpenAIProvider
from .mock import MockLLMProvider
from workflow_engine.ports import LLMPort
from workflow_engine.config import LLMProvidersConfig

logger = logging.getLogger(__name__)


class ProviderFactory:
    """
    Constructs LLMPort implementations from config.

    Provider selection via provider_name:
      "google"  — Gemini API (AI Studio). Requires GOOGLE_API_KEY.
      "vertex"  — Vertex AI. Requires VERTEX_AI_PROJECT + ADC credentials
                  (GOOGLE_APPLICATION_CREDENTIALS or `gcloud auth application-default login`).
      "openai"  — OpenAI API. Requires OPENAI_API_KEY.
      "mock"    — In-memory stub for tests and local dev without API keys.
    """

    @classmethod
    def from_config(cls, config: LLMProvidersConfig, provider_name: str = "google") -> LLMPort:
        if provider_name == "mock":
            logger.info("Using MockLLMProvider")
            return MockLLMProvider()

        if provider_name == "google":
            if not config.google_api_key:
                raise RuntimeError(
                    "GOOGLE_API_KEY is required for provider 'google'. "
                    "Get a key at https://aistudio.google.com or set LLM_PROVIDER=mock for local dev."
                )
            logger.info("Initializing GoogleGenAIProvider (Gemini API)")
            return GoogleGenAIProvider(api_key=config.google_api_key)

        if provider_name == "vertex":
            if not config.vertex_ai_project:
                raise RuntimeError(
                    "VERTEX_AI_PROJECT is required for provider 'vertex'. "
                    "Also ensure ADC credentials are configured "
                    "(GOOGLE_APPLICATION_CREDENTIALS or `gcloud auth application-default login`)."
                )
            logger.info(
                "Initializing GoogleGenAIProvider (Vertex AI) project=%s location=%s",
                config.vertex_ai_project, config.vertex_ai_location,
            )
            return GoogleGenAIProvider(
                vertexai=True,
                project=config.vertex_ai_project,
                location=config.vertex_ai_location,
            )

        if provider_name == "openai":
            if not config.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is required for provider 'openai'.")
            logger.info("Initializing OpenAIProvider")
            return OpenAIProvider(api_key=config.openai_api_key)

        raise ValueError(
            f"Unknown provider: '{provider_name}'. Valid options: google, vertex, openai, mock"
        )
