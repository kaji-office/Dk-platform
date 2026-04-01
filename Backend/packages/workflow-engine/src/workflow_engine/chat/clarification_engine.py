import json
import logging
from typing import Any
from jinja2 import Environment, select_autoescape, FileSystemLoader
import os

from workflow_engine.chat.models import RequirementSpec, ChatMessage
from workflow_engine.cache.cached_llm import CachedLLMProvider

logger = logging.getLogger(__name__)

class MaxClarificationRoundsError(Exception):
    pass

class LLMOutputParseError(Exception):
    pass

class ClarificationEngine:
    def __init__(self, llm_provider: CachedLLMProvider):
        self.llm_provider = llm_provider
        self.env = Environment(
            loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "prompts")),
            autoescape=select_autoescape()
        )
    
    async def get_questions(self, spec: RequirementSpec, round_num: int, messages: list[ChatMessage]) -> list[str]:
        """
        Sends RequirementSpec.missing_fields() + conversation to LLM.
        Returns 1–3 targeted questions.
        Returns empty list when spec is complete or all required fields are present.
        Raises MaxClarificationRoundsError after 5 rounds.
        """
        missing = spec.missing_fields()
        if not missing:
            return []
            
        if round_num > 5:
            raise MaxClarificationRoundsError("Exceeded maximum clarification rounds limit (5)")
            
        template = self.env.get_template("clarification.jinja2")
        
        # Serialize history for prompt
        history_text = ""
        for msg in messages:
            history_text += f"{msg.role.upper()}: {msg.content}\n"
            
        import dataclasses
        spec_dict = dataclasses.asdict(spec)
        prompt = template.render(
            spec=json.dumps(spec_dict, indent=2),
            missing_fields=", ".join(missing),
            messages=history_text
        )
        
        try:
            raw_response = await self.llm_provider.complete(prompt, temperature=0.2)
            
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            questions = json.loads(cleaned)
            if not isinstance(questions, list):
                raise LLMOutputParseError("LLM response did not contain a JSON array of strings.")
                
            # Limit to 3 questions naturally if LLM was too verbose
            return questions[:3]
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM clarification output: {e}\nRaw Output: {raw_response}")
            raise LLMOutputParseError("LLM response was not valid JSON array for ClarificationEngine") from e
        except Exception as e:
            raise e
